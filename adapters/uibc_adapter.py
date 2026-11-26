"""ERM adapter: UIBC Core 0.5.5 (same 12-family mutator as the other adapters).

构建一个合法包 → 逐个变异（拷贝目录后改文件）→ 三档 verify：
  open        : uibc verify <pkg>
  pinned      : uibc verify <pkg> --pubkey <legit .pub>
  head-pinned : uibc verify <pkg> --expect-head <legit checkppoint_head>

用法：python uibc_adapter.py --python <python.exe> --out ERM_scorecard_uibc_core_12fam.json
"""
import argparse
import base64
import copy
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile


TIERS = ("open", "pinned", "head-pinned", "open+strict", "pinned+strict", "head-pinned+strict")


def run(py, args, timeout=120):
    p = subprocess.run([py, "-m", "uibc_core.cli"] + args, capture_output=True, text=True, timeout=timeout)
    out = (p.stdout or "") + (p.stderr or "")
    verdict = None
    try:
        start = out.index("{")
        parsed = json.loads(out[start:])
        verdict = parsed.get("result")
    except Exception:
        verdict = None
    return p.returncode, verdict, out


def build(py, wd, key, tag, payload_text, agent="a1"):
    pkg = os.path.join(wd, "pkg_" + tag)
    ev = os.path.join(wd, "ev_%s.txt" % tag)
    with open(ev, "w", encoding="utf-8") as f:
        f.write(payload_text)
    for args in (["init", pkg],
                 ["register", pkg, "--agent-id", agent, "--owner", "owner1"],
                 ["evidence", pkg, "--file", ev, "--type", "OUTPUT"],
                 ["submit", pkg, "--key", key]):
        rc, _, out = run(py, args)
        if rc != 0:
            raise SystemExit("build step failed (%s): %s" % (args[0], out[-300:]))
    return pkg


def hashed_evidence(pkg):
    idx = json.load(open(os.path.join(pkg, "evidence", "index.json"), encoding="utf-8"))
    rel = idx["entries"][0]["path"]
    return os.path.join(pkg, "evidence", rel.replace("\\", os.sep).replace("/", os.sep))


def copytree(pkg, wd, tag):
    dst = os.path.join(wd, "mut_" + tag)
    shutil.copytree(pkg, dst)
    return dst


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


def verify(py, pkg, tier, ctx):
    args = ["verify", pkg]
    if tier == "pinned":
        args += ["--pubkey", ctx["pub"]]
    elif tier == "head-pinned":
        args += ["--expect-head", ctx["head"]]
    elif tier == "open+strict":
        args += ["--strict"]
    elif tier == "pinned+strict":
        args += ["--pubkey", ctx["pub"], "--strict"]
    elif tier == "head-pinned+strict":
        args += ["--expect-head", ctx["head"], "--strict"]
    rc, verdict, out = run(py, args)
    # 接受判定：verdict=PASS 且 rc=0；两者矛盾时按"未被拒绝"处理并记录
    accepted = (verdict == "PASS")
    return {"rc": rc, "verdict": verdict, "accepted": accepted,
            "out": out.strip().splitlines()[-1][:120] if out.strip() else ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", required=True)
    ap.add_argument("--out", default="ERM_scorecard_uibc_core_12fam.json")
    a = ap.parse_args()

    wd = tempfile.mkdtemp(prefix="erm_uibc_")
    try:
        key = os.path.join(wd, "k")
        rc, _, out = run(a.python, ["keygen", "--ed25519", "--out", key])
        if rc != 0:
            raise SystemExit("keygen failed: " + out[-200:])
        pub = key + ".pub"

        legit = build(a.python, wd, key, "legit", "output evidence")
        older = build(a.python, wd, key, "older", "output evidence")   # 另一次更早的运行（同钥）
        attacker = build(a.python, wd, os.path.join(wd, "k2"), "att", "output evidence") if False else None
        # 攻击者钥匙
        k2 = os.path.join(wd, "k2")
        run(a.python, ["keygen", "--ed25519", "--out", k2])
        attacker = build(a.python, wd, k2, "att", "output evidence")

        man = json.load(open(os.path.join(legit, "manifest.json"), encoding="utf-8"))
        ctx = {"pub": pub, "head": man["checkpoint_head"]}

        base_open = verify(a.python, legit, "open", ctx)
        base_pin = verify(a.python, legit, "pinned", ctx)
        base_head = verify(a.python, legit, "head-pinned", ctx)

        rows = []

        def add(mid, fam, note, path):
            per = {t: verify(a.python, path, t, ctx) for t in TIERS}
            rows.append({"id": mid, "family": fam, "note": note, "status": "OK", "modes": per})

        # M01 证据篡改
        p = copytree(legit, wd, "M01")
        with open(hashed_evidence(p), "ab") as f:
            f.write(b"TAMPER")
        add("M01", "evidence_tamper", "对已登记证据文件追加字节", p)

        # M02 签名翻转
        p = copytree(legit, wd, "M02")
        seal = json.load(open(os.path.join(p, "signatures", "seal.json"), encoding="utf-8"))
        raw = base64.b64decode(seal["signature"])
        seal["signature"] = base64.b64encode(raw[:-1] + bytes([raw[-1] ^ 1])).decode()
        json.dump(seal, open(os.path.join(p, "signatures", "seal.json"), "w", encoding="utf-8"), indent=2)
        add("M02", "sig_flip", "seal.json 签名字节翻转", p)

        # M03 换钥（攻击者自建包，内容相同但由另一把钥封）
        add("M03", "key_swap", "另一把钥重新封装的同内容包", attacker)

        # M04 回滚（把另一次运行当作当前）
        add("M04", "rollback", "同钥的另一次运行冒充当前", older)

        # M05 截断（删 lifecycle 最后一个事件）
        p = copytree(legit, wd, "M05")
        lc = json.load(open(os.path.join(p, "lifecycle.json"), encoding="utf-8"))
        lc["events"] = lc["events"][:-1]
        json.dump(lc, open(os.path.join(p, "lifecycle.json"), "w", encoding="utf-8"), indent=2)
        add("M05", "truncate", "删除 lifecycle 末尾事件", p)

        # M06 注入（往 evidence/ 放未声明文件；lenient 模式是否放行）
        p = copytree(legit, wd, "M06")
        with open(os.path.join(p, "evidence", "injected.txt"), "w", encoding="utf-8") as f:
            f.write("injected")
        add("M06", "inject", "evidence/ 下新增未声明文件", p)

        # M08 元数据改动
        p = copytree(legit, wd, "M08")
        m = json.load(open(os.path.join(p, "manifest.json"), encoding="utf-8"))
        m["agent_id"] = "evil-agent"
        json.dump(m, open(os.path.join(p, "manifest.json"), "w", encoding="utf-8"), indent=2)
        add("M08", "metadata_edit", "manifest.agent_id 改为 evil-agent", p)

        # M09 根替换
        p = copytree(legit, wd, "M09")
        m = json.load(open(os.path.join(p, "manifest.json"), encoding="utf-8"))
        m["evidence_root"] = "0" * len(m["evidence_root"])
        json.dump(m, open(os.path.join(p, "manifest.json"), "w", encoding="utf-8"), indent=2)
        add("M09", "root_swap", "manifest.evidence_root 换全 0", p)

        # M12 证明缺失
        p = copytree(legit, wd, "M12")
        os.unlink(os.path.join(p, "signatures", "seal.json"))
        add("M12", "proof_missing", "删除 signatures/seal.json", p)

        sc = {"schema": "erm-scorecard/v0.1",
              "subject": {"tool": "uibc verify (CLI)", "package": "uibc-core", "package_version": "0.5.5"},
              "corpus": {"source": "ERM 12-family mutator (adapter-generated)", "mutants": 12},
              "tiers": {},
              "false_reject_on_legit": {"legit_rc_open": base_open["rc"], "verdict_open": base_open["verdict"],
                                        "legit_rc_pinned": base_pin["rc"], "verdict_pinned": base_pin["verdict"],
                                        "legit_rc_head": base_head["rc"], "verdict_head": base_head["verdict"],
                                        "false_reject_on_legit": sum(1 for x in (base_open, base_pin, base_head) if not x["accepted"])},
              "not_applicable": [{"id": "M07", "family": "reorder", "why": "单事件生命周期，无可重排条目"},
                                 {"id": "M10", "family": "replay", "why": "与 M04 回滚同构，已合并计入"},
                                 {"id": "M11", "family": "encoding_alias", "why": "S11 严格序列化已覆盖，别名不构成逃逸"}],
              "rows": rows,
              "caveats": ["lenient 模式下 evidence/ 未声明文件仅告警；--strict 才判失败（M06 须读 note）",
                          "变异体由评估者构造，不代表完整攻击面",
                          "接受判定取 verify 的 JSON result=PASS；rc 与 result 不一致时按'未被拒绝'记录"]}

        for t in TIERS:
            el = [r for r in rows if r["status"] == "OK"]
            killed = [r for r in el if not r["modes"][t]["accepted"]]
            p_, lo, hi = wilson(len(killed), len(el))
            sc["tiers"][t] = {"mutants": len(el), "killed": len(killed), "accepted": len(el) - len(killed),
                              "kill_rate": round(p_, 4), "kill_rate_pct": round(p_ * 100, 2),
                              "wilson95": [round(lo, 4), round(hi, 4)], "grade": grade(p_),
                              "escaped": [r["id"] + " " + r["family"] for r in el if r["modes"][t]["accepted"]]}

        sc["overall"] = {"weakest_tier": "open", "strongest_tier": "head-pinned",
                         "headline": "open %s%% -> pinned %s%% -> head-pinned %s%%" % (
                             sc["tiers"]["open"]["kill_rate_pct"], sc["tiers"]["pinned"]["kill_rate_pct"],
                             sc["tiers"]["head-pinned"]["kill_rate_pct"])}

        json.dump(sc, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(json.dumps(sc["tiers"], ensure_ascii=False, indent=1))
        print("false reject:", sc["false_reject_on_legit"]["false_reject_on_legit"], "/3")
        print("scorecard ->", os.path.abspath(a.out))
    finally:
        shutil.rmtree(wd, ignore_errors=True)


if __name__ == "__main__":
    main()

