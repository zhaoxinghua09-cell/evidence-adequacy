"""One command a stranger can run: re-measure all three verifiers and diff against the published tables.

    python tools/reproduce.py --python <python.exe> [--skip-uibc] [--skip-pb] [--skip-pl]

Exit 0 only when every published tier figure reproduces exactly (kill counts, not percentages).
Exit 1 on any drift, with the cell named. Nothing here is allowed to "roughly match".
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run(args, timeout=900):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def tiers_of(path):
    d = json.load(open(path, encoding="utf-8"))
    out = {}
    for name, t in d.get("tiers", {}).items():
        if isinstance(t, dict) and "killed" in t:
            out[name] = (t["killed"], t.get("mutants"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", required=True)
    ap.add_argument("--exe-dir", default=None,
                    help="directory holding proofbundle/proofline executables (default: alongside --python)")
    ap.add_argument("--skip-uibc", action="store_true")
    ap.add_argument("--skip-pb", action="store_true")
    ap.add_argument("--skip-pl", action="store_true")
    ap.add_argument("--uibc-out", default="ERM_scorecard_uibc_core_12fam.json")
    a = ap.parse_args()

    exe_dir = a.exe_dir or os.path.dirname(os.path.abspath(a.python))
    tmp = tempfile.mkdtemp(prefix="erm_repro_")
    rows, drift = [], 0

    jobs = []
    if not a.skip_uibc:
        jobs.append(("UIBC Core", "uibc_adapter.py", None,
                     os.path.join(ROOT, "results", "ERM_scorecard_uibc_core_12fam.json"),
                     os.path.join(tmp, "uibc.json")))
    if not a.skip_pb:
        jobs.append(("proofbundle", "proofbundle_adapter.py", os.path.join(exe_dir, "proofbundle.exe"),
                     os.path.join(ROOT, "results", "ERM_scorecard_proofbundle.json"),
                     os.path.join(tmp, "pb.json")))
    if not a.skip_pl:
        jobs.append(("proofline", "proofline_adapter.py", os.path.join(exe_dir, "proofline.exe"),
                     os.path.join(ROOT, "results", "ERM_scorecard_proofline.json"),
                     os.path.join(tmp, "pl.json")))

    for name, script, exe, published, fresh in jobs:
        cmd = [a.python, os.path.join(HERE, "..", "adapters", script), "--out", fresh]
        cmd += ["--exe", exe] if exe else ["--python", a.python]
        rc, out = run(cmd)
        if rc != 0 or not os.path.exists(fresh):
            print(f"{name:<14} ADAPTER FAILED (rc={rc})\n{out[-400:]}")
            drift += 1
            continue
        old, new = tiers_of(published), tiers_of(fresh)
        bad = []
        for tier, val in old.items():
            got = new.get(tier)
            if got != val:
                bad.append(f"{tier}: published {val} vs fresh {got}")
        # a tier that vanished is drift too
        for tier in new:
            if tier not in old:
                bad.append(f"{tier}: unpublished tier appeared")
        rows.append((name, "MATCH" if not bad else "DRIFT", "; ".join(bad)))
        drift += 1 if bad else 0

    print()
    width = max((len(r[0]) for r in rows), default=8)
    for name, status, note in rows:
        print(f"{name:<{width}}  {status:<6}  {note}")
    print()
    print("REPRODUCED" if drift == 0 else f"{drift} DRIFT(S)")
    sys.exit(0 if drift == 0 else 1)


if __name__ == "__main__":
    main()
