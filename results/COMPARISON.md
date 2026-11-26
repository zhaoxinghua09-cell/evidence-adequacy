# Cross-tool comparison (results as of 2026-11-27)

All runs: Windows 11 / Python 3.13.18, one evaluator, adapters in `adapters/`.

Two tables, because corpora must never be mixed:

- **Table A — same mutator.** All three verifiers are hit with the *same* 9–12 constructed families. This is the only apples-to-apples reading.
- **Table B — tool-native corpus.** UIBC Core's own 21-mutant benchmark (different families, includes multi-phase rollback). Kept for reference only; **not comparable** with A.

## Table A — same mutator, cross-tool

| Verifier | version | eligible mutants | `open` | `pinned` | `head-pinned` | false reject |
|---|---|---|---|---|---|---|
| **UIBC Core** | 0.5.5 | 9 | **66.7%** (6/9) [35.4, 87.9] · C | **77.8%** (7/9) [45.3, 93.7] · C | **88.9%** (8/9) [56.5, 98.0] · B | 0/3 |
| **proofbundle** | 6.6.1 | 10 | **70.0%** (7/10) [39.7, 89.2] · C | **80.0%** (8/10) [49.0, 94.3] · B | N/A (no checkpoint fixture) | 0/2 |
| **proofline** | 0.4.0 | 9 | **77.8%** (7/9) [45.3, 93.7] · C | **88.9%** (8/9) [56.5, 98.0] · B | N/A (no sequence interface) | 0/2 |

Escapes per tier:

| Tier | UIBC Core | proofbundle | proofline |
|---|---|---|---|
| `open` | key_swap, rollback, inject | key_swap, replay, b64 alias | key_swap, replay |
| `pinned` | rollback, inject | key_swap, b64 alias | replay |
| `head-pinned` | inject | — | — |

## Table B — tool-native corpus (not comparable with A)

| Verifier | mutants | open | pinned | head-pinned |
|---|---|---|---|---|
| UIBC Core (its own 21-mutant benchmark) | 21 | 90.5% (19/21) · B | 95.2% (20/21) · A | 100% (21/21) · A |

## What the numbers say

1. **With one shared mutator, no tool gets an A at `open`.** All three are C-level against constructed forgery, and each leaks its own subset. Any claim of "strong detection" without stating the corpus is unfalsifiable.
2. **Our own tool is the one whose escape set grows when measured with someone else's mutator.** The 21-mutant benchmark (Table B) hides two families the shared mutator exposes: `inject` and single-run `rollback`. Table B is not wrong — it is narrower. **A tool's own corpus flatters it; that is precisely why a third-party meter is needed.**
3. **`inject` escapes UIBC Core at all three tiers.** A file dropped into `evidence/` that the index never declared is *tolerated* in the default (lenient) mode; only `--strict` fails it. Practically: an attacker can append material to a sealed package and the default verifier still says PASS. This is a defect-level finding about our own tool, recorded rather than hidden. Recommended fix (needs approval, not yet made): make undeclared-evidence a non-PASS by default.
4. **`rollback` is caught only at `head-pinned`.** Both proofbundle and proofline accept an older-but-valid bundle at `pinned`; UIBC Core does too. Only the log-head pin (UIBC `--expect-head`, proofbundle `--trusted-checkpoint`) closes it — and only UIBC exposes a working fixture-free path today.
5. **`proofline` remains the tightest on tamper questions and the weakest on freshness.** `replay` escapes at both tiers it exposes.
6. **`proofbundle`'s `b64 alias` escape** shows encoding tolerance is a real family; UIBC's shared-mutator run marked alias `N/A` because its S11 strict-serialisation check normalises before comparison.

## Methodology notes (why these numbers are honest)

- **Same families, different bundle shapes**: multi-step vs single-step bundles make `rollback`/`reorder` structurally inapplicable for the latter; every scorecard lists its `not_applicable` set and the denominator is the eligible count.
- **Small n**: 9–10 mutants give ±20-point intervals. Grades are coarse; the escape *names* are the real output.
- **`proofline sign` appends signatures**: a naive key-substitution mutant keeps the legitimate signature and falsely passes the pinned tier. The adapter clears the signature set first. Recorded because such mistakes are what make external measurements untrustworthy.
- **UIBC verdict semantics**: acceptance is taken from the verifier's JSON `result=PASS`, not only the exit code (M12 returns `INCONCLUSIVE` with a non-zero code and is counted as not-accepted).

## Reproduction

```bash
python adapters/uibc_adapter.py      --python "$(command -v python)" --out out_uibc.json
python adapters/proofbundle_adapter.py --exe "$(command -v proofbundle)" --out out_pb.json
python adapters/proofline_adapter.py   --exe "$(command -v proofline)"  --out out_pl.json
python tools/erm_scorecard.py mutation_benchmark.json out_uibc_native.json   # Table B
```

## Conflict disclosure

UIBC Core is maintained in the same ecosystem as this repo's author; proofbundle and proofline are independent third-party projects. All numbers are reproducible with the commands above. Deltas should be filed as issues and recorded, not folded into the table.
