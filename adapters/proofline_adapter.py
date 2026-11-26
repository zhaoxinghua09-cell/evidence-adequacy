"""ERM adapter: proofline 0.4.0.

用它的 CLI 生成合法 bundle（run + sign），再按变异族改 JSON，逐档 verify。
只读不改目标仓；输出 erm-scorecard/v0.1。

用法：
  python proofline_adapter.py --exe <proofline.exe> --out ERM_scorecard_proofline.json
"""
import argparse
import base64
import copy
import json
import math
import os
import shutil
import subprocess
import tempfile


def run(cmd, cwd=None, timeout=120):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def make_bundle(exe, workdir, tag, keydir, args):
    out = os.path.join(workdir, "b_%s.json" % tag)
    rc, s = run([exe, "run", "--out", out, "--"] + args)
    if rc != 0 or not os.path.exists(out):
        raise SystemExit("run failed (%s): %s" % (tag, s[-300:]))
    rc, s = run([exe, "sign", out, "--key", os.path.join(keydir, "proofline-signing.pem")])
    if rc != 0:
        raise SystemExit("sign failed (%s): %s" % (tag, s[-300:]))
    return json.load(open(out, encoding="utf-8")), out


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def grade(r):
    return "A" if r >= 0.95 else "B" if r >= 0.80 else "C" if r >= 0.50 else "D"


def flip_b64(s):
    raw = base64.b64decode(s)
    return base64.b64encode(raw[:-1] + bytes([raw[-1] ^ 0x01])).decode()


def m01(b, ctx):
    x = copy.deepcopy(b)
    st = x["steps"][0]["output"]
    if "stdout" in st:
        st["stdout"]["text"] = (st["stdout"].get("text") or "") + "TAMPERED"
    else:
        st["returncode"] = 1
    return x, "篡改步骤输出"


def m02(b, ctx):
    x = copy.deepcopy(b)
    x["signatures"][0]["signature"] = flip_b64(x["signatures"][0]["signature"])
    return x, "签名字节翻转"


def m03(b, ctx):
    return copy.deepcopy(ctx["attacker"]), "换钥重签（攻击者钥匙）"


def m04(b, ctx):
    return None, "无历史序列，N/A"


def m05(b, ctx):
    x = copy.deepcopy(b)
    x["steps"] = x["steps"][:-1]
    return x, "删除最后一步（截断）"


def m06(b, ctx):
    x = copy.deepcopy(b)
    x["extra_step"] = {"step_id": "step-99", "kind": "process", "status": "ok"}
    return x, "注入未知字段/步骤"


def m07(b, ctx):
    return None, "单步运行无可重排条目，N/A"


def m08(b, ctx):
    x = copy.deepcopy(b)
    x["actor"]["name"] = "someone-else"
    return x, "改元数据（actor.name）"


def m09(b, ctx):
    x = copy.deepcopy(b)
    x["bundle_digest"] = "0" * len(str(x.get("bundle_digest") or "0" * 64))
    return x, "bundle_digest 换全 0"


def m10(b, ctx):
    return copy.deepcopy(ctx["other"]), "整包重放（同钥匙、另一运行）"


def m11(b, ctx):
    return None, "JSON 编码别名不构成安全逃逸，N/A"


def m12(b, ctx):
    x = copy.deepcopy(b)
    x["signatures"] = []
    return x, "删除全部签名（证明缺失）"


MUTANTS = [("M01", "output_tamper", m01), ("M02", "sig_flip", m02), ("M03", "key_swap", m03),
           ("M04", "rollback", m04), ("M05", "truncate", m05), ("M06", "inject", m06),
           ("M07", "reorder", m07), ("M08", "metadata_edit", m08), ("M09", "digest_swap", m09),
           ("M10", "replay", m10), ("M11", "encoding_alias", m11), ("M12", "proof_missing", m12)]


def verify(exe, path, tier, ctx):
    args = [exe, "verify", path]
    if tier == "pinned":
        args += ["--signed-by", ctx["pubkey"]]
    return run(args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--out", default="ERM_scorecard_proofline.json")
    a = ap.parse_args()

    wd = tempfile.mkdtemp(prefix="erm_pl_")
    try:
        kdir = os.path.join(wd, "k1")
        rc, s = run([a.exe, "keygen", "--out", kdir])
        if rc != 0:
            raise SystemExit("keygen failed: " + s[-200:])
        adir = os.path.join(wd, "k2")
        run([a.exe, "keygen", "--out", adir])

        legit, legit_path = make_bundle(a.exe, wd, "legit", kdir, [os.environ.get("COMSPEC", "cmd.exe"), "/c", "echo legit"])
        other, other_path = make_bundle(a.exe, wd, "other", kdir, [os.environ.get("COMSPEC", "cmd.exe"), "/c", "echo other"])

        # 攻击者：把合法 bundle 的签名清空，只留攻击者自己的签名（否则 sign 会追加，pinned 档会因合法签名仍在而通过）
        src = copy.deepcopy(legit)
        src["signatures"] = []
        ap_path = os.path.join(wd, "b_attacker.json")
        json.dump(src, open(ap_path, "w", encoding="utf-8"), ensure_ascii=False)
        run([a.exe, "sign", ap_path, "--key", os.path.join(adir, "proofline-signing.pem")])
        attacker = json.load(open(ap_path, encoding="utf-8"))

        ctx = {"attacker": attacker, "other": other,
               "pubkey": os.path.join(kdir, "proofline-signing.pub.pem")}

        base_open = verify(a.exe, legit_path, "open", ctx)[0]
        base_pin = verify(a.exe, legit_path, "pinned", ctx)[0]

        rows = []
        for mid, fam, fn in MUTANTS:
            mut, note = fn(legit, ctx)
            if mut is None:
                rows.append({"id": mid, "family": fam, "note": note, "status": "N/A"})
                continue
            path = os.path.join(wd, "m_%s.json" % mid)
            json.dump(mut, open(path, "w", encoding="utf-8"), ensure_ascii=False)
            per = {}
            for t in ("open", "pinned"):
                rc, out = verify(a.exe, path, t, ctx)
                per[t] = {"rc": rc, "accepted": rc == 0,
                          "out": (out.strip().splitlines()[-1][:150] if out.strip() else "")}
            rows.append({"id": mid, "family": fam, "note": note, "status": "OK", "modes": per})

        sc = {"schema": "erm-scorecard/v0.1",
              "subject": {"tool": "proofline verify (CLI)", "package": "proofline", "package_version": "0.4.0"},
              "corpus": {"source": "ERM 12-family mutator (adapter-generated)", "mutants": 12},
              "tiers": {},
              "false_reject_on_legit": {"legit_rc_open": base_open, "legit_rc_pinned": base_pin,
                                        "false_reject_on_legit": int(base_open != 0) + int(base_pin != 0)},
              "not_applicable": [{"id": r["id"], "family": r["family"], "why": r["note"]}
                                 for r in rows if r["status"] == "N/A"],
              "rows": rows,
              "caveats": ["单步 bundle：rollback / reorder 不适用，已剔除",
                          "无日志头/序列接口，head-pinned 档 N/A（不等于不支持，而是接口未暴露）",
                          "变异体由评估者构造，不代表完整攻击面"]}

        for t in ("open", "pinned"):
            el = [r for r in rows if r["status"] == "OK"]
            killed = [r for r in el if not r["modes"][t]["accepted"]]
            p, lo, hi = wilson(len(killed), len(el))
            sc["tiers"][t] = {"mutants": len(el), "killed": len(killed), "accepted": len(el) - len(killed),
                              "kill_rate": round(p, 4), "kill_rate_pct": round(p * 100, 2),
                              "wilson95": [round(lo, 4), round(hi, 4)], "grade": grade(p),
                              "escaped": [r["id"] + " " + r["family"] for r in el if r["modes"][t]["accepted"]]}
        sc["tiers"]["head-pinned"] = {"mutants": 0, "killed": 0, "accepted": 0,
                                     "kill_rate": None, "grade": "N/A", "escaped": [],
                                     "note": "CLI 未暴露 checkpoint/序列接口"}
        sc["overall"] = {"weakest_tier": "open", "strongest_tier": "pinned",
                         "headline": "open %s%% -> pinned %s%%" % (
                             sc["tiers"]["open"]["kill_rate_pct"], sc["tiers"]["pinned"]["kill_rate_pct"])}

        json.dump(sc, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(json.dumps(sc["tiers"], ensure_ascii=False, indent=1))
        print("escaped(open):", ", ".join(sc["tiers"]["open"]["escaped"]) or "none")
        print("escaped(pinned):", ", ".join(sc["tiers"]["pinned"]["escaped"]) or "none")
        print("false reject:", sc["false_reject_on_legit"]["false_reject_on_legit"], "/2")
        print("scorecard ->", os.path.abspath(a.out))
    finally:
        shutil.rmtree(wd, ignore_errors=True)


if __name__ == "__main__":
    main()
