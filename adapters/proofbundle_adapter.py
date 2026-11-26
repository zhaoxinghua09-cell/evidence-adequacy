"""ERM adapter: proofbundle 6.6.1 (cross-tool measurement).

思路：用对方自己的 CLI 造一个合法 bundle，再按变异族改写 JSON，逐档跑它的 verify。
只读、不改对方仓库；输出 ERM scorecard v0.1。

用法：
  python pb_adapter.py --exe <proofbundle.exe> --out ERM_scorecard_proofbundle.json
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

LEGIT_PAYLOAD = b'{"claim":"baseline eval run","score":0.81}'


def run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def emit(exe, workdir, payload_bytes, tag):
    pf = os.path.join(workdir, "payload_%s.bin" % tag)
    with open(pf, "wb") as f:
        f.write(payload_bytes)
    out = os.path.join(workdir, "bundle_%s.json" % tag)
    key = os.path.join(workdir, "key_%s.bin" % tag)
    rc, out_s = run([exe, "emit", "--payload-file", pf, "--out", out, "--new-key", key])
    if rc != 0 or not os.path.exists(out):
        raise SystemExit("emit failed for %s: %s" % (tag, out_s[-400:]))
    return json.load(open(out, encoding="utf-8"))


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def grade(rate):
    return "A" if rate >= 0.95 else "B" if rate >= 0.80 else "C" if rate >= 0.50 else "D"


def b64d(s):
    return base64.b64decode(s)


def b64e(b):
    return base64.b64encode(b).decode()


# 每个变异体返回 (新 bundle dict 或 None, 说明)；None 表示该族在单叶 bundle 上 N/A
def m01_payload_tamper(b, ctx):
    x = copy.deepcopy(b)
    raw = b64d(x["payload_b64"])
    x["payload_b64"] = b64e(raw[:-1] + bytes([raw[-1] ^ 0x01]))
    return x, "payload 末字节翻转"


def m02_sig_flip(b, ctx):
    x = copy.deepcopy(b)
    raw = b64d(x["signature"]["sig_b64"])
    x["signature"]["sig_b64"] = b64e(raw[:-1] + bytes([raw[-1] ^ 0x01]))
    return x, "签名字节翻转"


def m03_key_swap(b, ctx):
    # 攻击者用自己钥匙对同一 payload 出包（自签有效）
    return copy.deepcopy(ctx["attacker_bundle"]), "换钥重签（攻击者自签）"


def m04_rollback(b, ctx):
    return None, "单叶 bundle 无历史，N/A"


def m05_truncate(b, ctx):
    x = copy.deepcopy(b)
    x["merkle"]["tree_size"] = max(0, int(x["merkle"]["tree_size"]) - 1)
    return x, "tree_size 减一（截断）"


def m06_inject(b, ctx):
    x = copy.deepcopy(b)
    x["extra_entry"] = {"claim": "injected"}
    return x, "注入未知顶层字段"


def m07_reorder(b, ctx):
    return None, "单叶无可重排条目，N/A"


def m08_metadata_edit(b, ctx):
    x = copy.deepcopy(b)
    x["schema"] = "proofbundle/v0.1 "  # 尾随空格
    return x, "schema 串改动（不改字节）"


def m09_root_swap(b, ctx):
    x = copy.deepcopy(b)
    n = len(b64d(x["merkle"]["root_b64"]))
    x["merkle"]["root_b64"] = b64e(b"\x00" * n)
    return x, "根换全 0"


def m10_replay(b, ctx):
    # 用另一份合法 bundle（不同 payload）冒充
    return copy.deepcopy(ctx["other_legit"]), "整包重放（另一合法包）"


def m11_alias(b, ctx):
    x = copy.deepcopy(b)
    s = x["payload_b64"]
    x["payload_b64"] = s.rstrip("=")  # base64 去 padding
    return x, "base64 去 padding（编码别名）"


def m12_proof_missing(b, ctx):
    x = copy.deepcopy(b)
    x["merkle"].pop("root_b64", None)
    return x, "删除 root 字段（证明缺失）"


MUTANTS = [
    ("M01", "payload_tamper", m01_payload_tamper),
    ("M02", "sig_flip", m02_sig_flip),
    ("M03", "key_swap", m03_key_swap),
    ("M04", "rollback", m04_rollback),
    ("M05", "truncate", m05_truncate),
    ("M06", "inject", m06_inject),
    ("M07", "reorder", m07_reorder),
    ("M08", "metadata_edit", m08_metadata_edit),
    ("M09", "root_swap", m09_root_swap),
    ("M10", "replay", m10_replay),
    ("M11", "b64_alias", m11_alias),
    ("M12", "proof_missing", m12_proof_missing),
]


def verify(exe, path, tier, ctx):
    args = [exe, "verify", path]
    if tier == "pinned":
        args += ["--expected-root", ctx["legit_root"]]
    return run(args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--out", default="ERM_scorecard_proofbundle.json")
    a = ap.parse_args()

    workdir = tempfile.mkdtemp(prefix="erm_pb_")
    try:
        legit = emit(a.exe, workdir, LEGIT_PAYLOAD, "legit")
        attacker = emit(a.exe, workdir, LEGIT_PAYLOAD, "attacker")
        other = emit(a.exe, workdir, b'{"claim":"other run","score":0.42}', "other")
        ctx = {
            "attacker_bundle": attacker,
            "other_legit": other,
            "legit_root": legit["merkle"]["root_b64"],
        }

        # 基线（合法包必须通过）
        base_rc_open, base_out_open = verify(a.exe, os.path.join(workdir, "bundle_legit.json"), "open", ctx)
        base_rc_pin, _ = verify(a.exe, os.path.join(workdir, "bundle_legit.json"), "pinned", ctx)

        rows = []
        for mid, name, fn in MUTANTS:
            mut, note = fn(legit, ctx)
            if mut is None:
                rows.append({"id": mid, "family": name, "note": note, "status": "N/A"})
                continue
            path = os.path.join(workdir, "mut_%s.json" % mid)
            json.dump(mut, open(path, "w", encoding="utf-8"), ensure_ascii=False)
            per = {}
            for tier in ("open", "pinned"):
                rc, out = verify(a.exe, path, tier, ctx)
                per[tier] = {"rc": rc, "accepted": rc == 0,
                             "out": out.strip().splitlines()[-1][:160] if out.strip() else ""}
            rows.append({"id": mid, "family": name, "note": note, "status": "OK", "modes": per})

        score = {
            "schema": "erm-scorecard/v0.1",
            "subject": {"tool": "proofbundle verify (CLI)", "package": "proofbundle", "package_version": "6.6.1"},
            "corpus": {"source": "ERM 12-family mutator (adapter-generated)", "mutants": 12},
            "tiers": {},
            "false_reject_on_legit": {
                "legit_rc_open": base_rc_open, "legit_rc_pinned": base_rc_pin,
                "false_reject_on_legit": int(base_rc_open != 0) + int(base_rc_pin != 0),
            },
            "not_applicable": [{"id": r["id"], "family": r["family"], "why": r["note"]}
                               for r in rows if r["status"] == "N/A"],
            "rows": rows,
            "caveats": [
                "单叶 bundle：rollback/reorder 两族不适用，已从分母剔除",
                "head-pinned 档位需要 checkpoint 文件，本轮未取到，标 N/A（不等于不支持）",
                "变异体由评估者构造，不代表完整攻击面",
            ],
        }

        for tier in ("open", "pinned"):
            eligible = [r for r in rows if r["status"] == "OK"]
            killed = [r for r in eligible if not r["modes"][tier]["accepted"]]
            n = len(eligible)
            p, lo, hi = wilson(len(killed), n)
            score["tiers"][tier] = {
                "mutants": n, "killed": len(killed), "accepted": n - len(killed),
                "kill_rate": round(p, 4), "kill_rate_pct": round(p * 100, 2),
                "wilson95": [round(lo, 4), round(hi, 4)],
                "grade": grade(p),
                "escaped": [r["id"] + " " + r["family"] for r in eligible if r["modes"][tier]["accepted"]],
            }

        score["tiers"]["head-pinned"] = {
            "mutants": 0, "killed": 0, "accepted": 0, "kill_rate": None,
            "grade": "N/A", "escaped": [], "note": "需要 trusted-checkpoint 文件，未获取"
        }
        score["overall"] = {
            "weakest_tier": "open", "strongest_tier": "pinned",
            "headline": "open %s%% -> pinned %s%%" % (
                score["tiers"]["open"]["kill_rate_pct"], score["tiers"]["pinned"]["kill_rate_pct"]),
        }

        json.dump(score, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(json.dumps(score["tiers"], ensure_ascii=False, indent=2))
        print("escaped(open):", ", ".join(score["tiers"]["open"]["escaped"]) or "none")
        print("escaped(pinned):", ", ".join(score["tiers"]["pinned"]["escaped"]) or "none")
        print("false reject on legit:", score["false_reject_on_legit"]["false_reject_on_legit"], "/ 2")
        print("scorecard ->", os.path.abspath(a.out))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
