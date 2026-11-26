"""Pre-registered families M13/M14/M15, measured only (does not touch the 12-family set).

Registered 2026-11-27 before any of these three was run; see PRE-REGISTRATION.md.
"""
import argparse, base64, json, os, shutil, subprocess, tempfile


def run(py, args, timeout=120):
    p = subprocess.run([py, "-m", "uibc_core.cli"] + args, capture_output=True, text=True, timeout=timeout)
    out = (p.stdout or "") + (p.stderr or "")
    try:
        v = json.loads(out[out.index("{"):]).get("result")
    except Exception:
        v = None
    return p.returncode, v


def build(py, wd, key, tag, texts, agent="a1"):
    pkg = os.path.join(wd, "pkg_" + tag)
    for args in (["init", pkg], ["register", pkg, "--agent-id", agent, "--owner", "owner1"]):
        if run(py, args)[0] != 0:
            raise SystemExit("build failed: " + args[0])
    for i, t in enumerate(texts):
        f = os.path.join(wd, "ev_%s_%d.txt" % (tag, i))
        open(f, "w", encoding="utf-8").write(t)
        if run(py, ["evidence", pkg, "--file", f, "--type", "OUTPUT"])[0] != 0:
            raise SystemExit("evidence failed")
    if run(py, ["submit", pkg, "--key", key])[0] != 0:
        raise SystemExit("submit failed")
    return pkg


def verify(py, pkg, tier, ctx):
    a = ["verify", pkg]
    if tier == "pinned":
        a += ["--pubkey", ctx["pub"]]
    elif tier == "head-pinned":
        a += ["--expect-head", ctx["head"]]
    rc, v = run(py, a)
    return {"rc": rc, "verdict": v, "accepted": v == "PASS"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", required=True)
    ap.add_argument("--out", default="prereg_uibc.json")
    a = ap.parse_args()
    wd = tempfile.mkdtemp(prefix="prereg_")
    try:
        key = os.path.join(wd, "k")
        run(a.python, ["keygen", "--ed25519", "--out", key])
        ctx = {"pub": key + ".pub"}

        # M13 alias: strip base64 padding from the seal signature (still decodes under a lax decoder)
        one = build(a.python, wd, key, "one", ["single evidence"])
        ctx["head"] = json.load(open(os.path.join(one, "manifest.json"), encoding="utf-8"))["checkpoint_head"]
        p = os.path.join(wd, "m13")
        shutil.copytree(one, p)
        seal = json.load(open(os.path.join(p, "signatures", "seal.json"), encoding="utf-8"))
        before = seal["signature"]
        seal["signature"] = before.rstrip("=")
        assert seal["signature"] != before, "no padding to strip; alias impossible"
        json.dump(seal, open(os.path.join(p, "signatures", "seal.json"), "w", encoding="utf-8"), indent=2)

        # M14 multi-leaf drop: two evidences, then delete one leaf from index + disk
        two = build(a.python, wd, key, "two", ["evidence one", "evidence two"])
        p14 = os.path.join(wd, "m14")
        shutil.copytree(two, p14)
        idx = json.load(open(os.path.join(p14, "evidence", "index.json"), encoding="utf-8"))
        victim = idx["entries"][-1]
        vpath = os.path.join(p14, "evidence", victim["path"].replace("/", os.sep))
        if os.path.exists(vpath):
            os.remove(vpath)
        idx["entries"] = idx["entries"][:-1]
        json.dump(idx, open(os.path.join(p14, "evidence", "index.json"), "w", encoding="utf-8"), indent=2)

        # M15 head truncation: drop the last lifecycle event, keep everything else
        p15 = os.path.join(wd, "m15")
        shutil.copytree(one, p15)
        lc = json.load(open(os.path.join(p15, "lifecycle.json"), encoding="utf-8"))
        lc["events"] = lc["events"][:-1]
        json.dump(lc, open(os.path.join(p15, "lifecycle.json"), "w", encoding="utf-8"), indent=2)

        out = {"subject": "uibc verify CLI 0.5.5", "families": {}}
        for name, path, expected_head in (("M13 alias (padding stripped)", p, ctx["head"]),
                                          ("M14 two-leaf drop", p14,
                                           json.load(open(os.path.join(two, "manifest.json"), encoding="utf-8"))["checkpoint_head"]),
                                          ("M15 head truncation", p15, ctx["head"])):
            c = dict(ctx); c["head"] = expected_head
            out["families"][name] = {t: verify(a.python, path, t, c) for t in ("open", "pinned", "head-pinned")}

        json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        for k, v in out["families"].items():
            print(k, {t: (m["verdict"], "accepted" if m["accepted"] else "killed") for t, m in v.items()})
    finally:
        shutil.rmtree(wd, ignore_errors=True)


if __name__ == "__main__":
    main()
