"""ERM scorecard 生成器 — 把变异基准结果转成 Escape-Rate Matrix v0.1 记分卡。

输入：uibc-core tools/out/mutation_benchmark.json
输出：ERM_scorecard_uibc_core.json + 控制台 markdown 表

为什么要有这个东西：
  现有生态里到处是"验证器"，但没人给验证器本身打"分档漏网率"。
  ERM 把这个数字变成可复跑、可对比、带区间的记分卡。
"""
import json
import math
import os
import sys

TIERS = ["open", "pinned", "head-pinned"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def grade(kill_rate):
    if kill_rate >= 0.95:
        return "A"
    if kill_rate >= 0.80:
        return "B"
    if kill_rate >= 0.50:
        return "C"
    return "D"


def family(mid):
    return mid.split()[0] if " " in mid else mid


def main(path, out):
    src = json.load(open(path, encoding="utf-8"))
    rows = src["rows"]
    meta = src["meta"]

    tiers = {}
    for t in TIERS:
        n = len(rows)
        accepted = 0
        missed = []
        for r in rows:
            m = r["modes"].get(t) or {}
            if m.get("accepted"):
                accepted += 1
                missed.append(r["id"])
        killed = n - accepted
        p, lo, hi = wilson(killed, n)
        tiers[t] = {
            "mutants": n,
            "killed": killed,
            "accepted": accepted,
            "kill_rate": round(p, 4),
            "kill_rate_pct": round(p * 100, 2),
            "wilson95": [round(lo, 4), round(hi, 4)],
            "grade": grade(p),
            "escaped": missed,
        }

    legit = {
        "base_open": meta.get("base_open"),
        "base_pinned": meta.get("base_pinned"),
        "false_reject_on_legit": sum(
            1 for v in (meta.get("base_open"), meta.get("base_pinned")) if v != "PASS"
        ),
    }

    scorecard = {
        "schema": "erm-scorecard/v0.1",
        "subject": {
            "tool": src["meta"].get("verifier"),
            "package": src["meta"].get("package"),
            "package_version": src["meta"].get("package_version") or "uibc-core (git 79811e13)",
        },
        "corpus": {
            "source": os.path.basename(path),
            "mutants": len(rows),
            "generated_at_utc": meta.get("generated_at_utc"),
        },
        "tiers": tiers,
        "false_reject_on_legit": legit,
        "overall": {
            "weakest_tier": min(TIERS, key=lambda t: tiers[t]["kill_rate"]),
            "strongest_tier": max(TIERS, key=lambda t: tiers[t]["kill_rate"]),
            "headline": "open %s%% -> pinned %s%% -> head-pinned %s%%" % (
                tiers["open"]["kill_rate_pct"],
                tiers["pinned"]["kill_rate_pct"],
                tiers["head-pinned"]["kill_rate_pct"],
            ),
        },
        "caveats": [
            "以 PASS 作为'被接受'；INCONCLUSIVE/FAIL 记未接受（按原基准口径）",
            "21 个变异体是作者自建，非同分布抽样，不能外推为通用漏网率",
            "未含'合法包被误杀'的样本量（仅有 2 个基线包）",
            "head-pinned 档位的强依赖是锚点/日志头，该档位在无锚点时不可用",
        ],
    }

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(scorecard, f, ensure_ascii=False, indent=2)

    print("| tier | killed | total | kill rate | 95% Wilson | grade |")
    print("|---|---|---|---|---|---|")
    for t in TIERS:
        s = tiers[t]
        print("| %s | %d | %d | %.1f%% | [%.1f%%, %.1f%%] | %s |" % (
            t, s["killed"], s["mutants"], s["kill_rate_pct"],
            s["wilson95"][0] * 100, s["wilson95"][1] * 100, s["grade"]))
    print("\nfalse reject on legit: %d/%d" % (
        legit["false_reject_on_legit"], 2))
    print("escaped at open: %s" % ", ".join(tiers["open"]["escaped"]))
    print("escaped at pinned: %s" % ", ".join(tiers["pinned"]["escaped"]))
    print("escaped at head-pinned: %s" % (", ".join(tiers["head-pinned"]["escaped"]) or "none"))
    print("\nscorecard -> %s" % os.path.abspath(out))


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else r"tools\out\mutation_benchmark.json"
    out = sys.argv[2] if len(sys.argv) > 2 else r"ERM_scorecard_uibc_core.json"
    main(src, out)
