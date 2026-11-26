# Pre-registration · three new families (2026-11-27T03:11Z, before any run)

Why this file exists: arXiv 2610.02928 registered which fixtures would kill which survivors *before* adding them, and all five predictions held. ERM never did that — its 12 families were chosen after reading each tool's CLI. That is the bias the paper warns about. This is the smallest honest fix: freeze the spec, write down the predictions, then run.

## Frozen artefacts

| What | Value |
|---|---|
| Spec | `ERM.md` v0.1, sha256 `435cb5b3724a1765b5e319fa2bcf831e3ae5ee6640794af66efb90737a9656ef` (5396 bytes) |
| Repo state at freeze | `evidence-adequacy@c5c77dd` |
| Subject | UIBC Core 0.5.5, `python -m uibc_core.cli verify` |
| Registered at | 2026-11-27T03:11Z |
| Script written after this file, not before | `work/erm/uibc_prereg.py` |

## The three families

- **M13 alias** — strip base64 padding from `signatures/seal.json:signature`. The bytes are unchanged; only the encoding spelling differs. A lax decoder accepts it, a strict one does not.
- **M14 two-leaf drop** — build a package with two evidence files, then delete the last leaf from `evidence/index.json` *and* from `evidence/files/`. The remaining tree and chain are untouched.
- **M15 head truncation** — delete the last `lifecycle.json` event, leave the seal, manifest and head as they are.

## Predictions (registered before execution)

| Family | `open` | `pinned` | `head-pinned` | Why I expect this |
|---|---|---|---|---|
| M13 alias | **killed** | **killed** | **killed** | S11 strict serialisation runs before any parse and S14 is "strict base64"; the format was explicitly built to refuse two decoders disagreeing on one string. |
| M14 two-leaf drop | **killed** | **killed** | **killed** | the evidence root is over the declared set (S5); dropping a declared leaf changes the root even though every remaining hash is valid. |
| M15 head truncation | **survives** | **survives** | **killed** | with no external head there is nothing to compare a shorter chain against — this is the same structural reason `rollback` only dies at `head-pinned`. The S8 checkpoint is over the *manifest* head, which truncation does not move. |

Three predictions, nine cells. **Falsifiable**: if M15 dies at `open`, my model of where freshness lives is wrong; if M13 survives anywhere, base64 canonicalisation is weaker than the repo claims.

## What counts as a miss

A cell whose measured verdict differs from the prediction above, in either direction, is a miss and gets reported as one — including the case where a tool is *stronger* than predicted.

## What this does not fix

Nine cells is not a coverage study. The families were still chosen by a person who had read these CLIs; pre-registration removes the "chosen after seeing the result" bias, not the "chosen by an insider" bias. The 12-family set also stays as-is — this file adds three, it does not re-cut the set.

---

# Results (run 2026-11-27T03:16Z, after the predictions above were written)

| Family | `open` | `pinned` | `head-pinned` | Predicted | Verdict |
|---|---|---|---|---|---|
| M13 alias | FAIL, killed | FAIL, killed | FAIL, killed | killed ×3 | ✅ hit |
| M14 two-leaf drop | FAIL, killed | FAIL, killed | FAIL, killed | killed ×3 | ✅ hit |
| M15 head truncation | **FAIL, killed** | **FAIL, killed** | FAIL, killed | survives, survives, killed | ❌ **miss** |

Score: **8 of 9 cells as registered, 1 miss** in the direction of the tool being stronger than predicted.

## The miss, and what it costs my earlier claim

I predicted M15 would survive `open` and `pinned` because "with no external head there is nothing to compare a shorter chain against". That reasoning is wrong for truncation: the manifest's `checkpoint_head` is over the lifecycle it declares, so removing an event makes the declared head and the actual chain disagree **inside** the package. The verifier catches that with S3/S8 without any external anchor.

What survives the correction is a narrower claim, and it should replace the stronger one used in `COMPARISON.md`:

- **Rollback** (an older, fully valid package with a matching declared head) cannot be caught from inside — only `--expect-head` does it. That part stands.
- **Truncation** (a chain that no longer matches its own declared head) is caught at every tier. Saying "freshness only dies at head-pinned" overstated it.

So the capability gap is narrower than advertised: `head-pinned` buys **rollback detection**, not "freshness in general". Any doc that implied the latter should be read with this correction.

## Reproduce

```bash
python work/erm/uibc_prereg.py --python "$(command -v python)" --out prereg_uibc.json
```

Raw cells: `results/prereg_uibc.json`. Spec hash frozen above; the script was written after the predictions, which is the only ordering that makes them predictions.

