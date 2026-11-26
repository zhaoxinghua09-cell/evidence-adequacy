"""Second pre-registered batch: M16 event reorder, M17 index path traversal (UIBC only).

Registered 2026-11-27T03:2xZ in PRE-REGISTRATION.md before this script existed.
"""
import argparse, json, os, shutil, subprocess, tempfile


def run(py, args, timeout=120):
    p = subprocess.run([py, "-m", "uibc_core.cli"] + args, capture_output=True, text=True, timeout=timeout)
    out = (p.stdout or "") + (p.stderr or "")
    try:
        v = json.loads(out[out.index("{"):]).get("result")
    except Exception:
        v = None
    return p.returncode, v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", required=True)
    ap.add_argument("--out", default="prereg2_uibc.json")
    a = ap.parse_args()
    wd = tempfile.mkdtemp(prefix="prereg2_")
    try:
        key = os.path.join(wd, "k")
        run(a.python, ["keygen", "--ed25519", "--out", key])
        pkg = os.path.join(wd, "pkg")
        for args in (["init", pkg], ["register", pkg, "--agent-id", "a1", "--owner", "owner1"]):
            if run(a.python, args)[0] != 0:
                raise SystemExit("build fail " + args[0])
        ev = os.path.join(wd, "ev.txt")
        open(ev, "w", encoding="utf-8").write("evidence")
        if run(a.python, ["evidence", pkg, "--file", ev, "--type", "OUTPUT"])[0] != 0:
            raise SystemExit("evidence fail")
        if run(a.python, ["submit", pkg, "--key", key])[0] != 0:
            raise SystemExit("submit fail")
        ctx = {"pub": key + ".pub",
               "head": json.load(open(os.path.join(pkg, "manifest.json"), encoding="utf-8"))["checkpoint_head"]}

        # M16 reorder: swap the first two lifecycle events (needs >= 2 events)
        p16 = os.path.join(wd, "m16")
        shutil.copytree(pkg, p16)
        lc = json.load(open(os.path.join(p16, "lifecycle.json"), encoding="utf-8"))
        n = len(lc["events"])
        if n < 2:
            print("M16: only %d event(s), family not constructible" % n)
            p16 = None
        else:
            lc["events"][0], lc["events"][1] = lc["events"][1], lc["events"][0]
            json.dump(lc, open(os.path.join(p16, "lifecycle.json"), "w", encoding="utf-8"), indent=2)

        # M17 traversal: point an index entry at ../../escape.txt
        p17 = os.path.join(wd, "m17")
        shutil.copytree(pkg, p17)
        idx = json.load(open(os.path.join(p17, "evidence", "index.json"), encoding="utf-8"))
        idx["entries"][0]["path"] = "../../escape.txt"
        json.dump(idx, open(os.path.join(p17, "evidence", "index.json"), "w", encoding="utf-8"), indent=2)

        out = {"subject": "uibc verify CLI 0.5.5", "families": {}}
        for name, path in (("M16 event reorder", p16), ("M17 index path traversal", p17)):
            if path is None:
                out["families"][name] = {"note": "not constructible on this package"}
                continue
            out["families"][name] = {t: (lambda rc, v: {"rc": rc, "verdict": v, "accepted": v == "PASS"})(*verify_t(py=a.python, path=path, tier=t, ctx=ctx))
                                     for t in ("open", "pinned", "head-pinned")}
        json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(json.dumps(out["families"], ensure_ascii=False, indent=1))
    finally:
        shutil.rmtree(wd, ignore_errors=True)


def verify_t(py, path, tier, ctx):
    a = ["verify", path]
    if tier == "pinned":
        a += ["--pubkey", ctx["pub"]]
    elif tier == "head-pinned":
        a += ["--expect-head", ctx["head"]]
    return run(py, a)


if __name__ == "__main__":
    main()
