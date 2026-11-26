# Cross-tool comparison (results as of 2026-11-27)

All three runs: Windows 11 / Python 3.13.18, same evaluator, same 12-family mutator where the bundle format allows.

| Verifier | version | eligible mutants | `open` | `pinned` | `head-pinned` | false reject |
|---|---|---|---|---|---|---|
| UIBC Core | 0.5.5 | 21 | **90.5%** (19/21) [71.1, 97.4] · B | **95.2%** (20/21) [77.3, 99.2] · A | **100%** (21/21) [84.5, 100] · A | 0/2 |
| proofbundle | 6.6.1 | 10 | **70.0%** (7/10) [39.7, 89.2] · C | **80.0%** (8/10) [49.0, 94.3] · B | N/A (no checkpoint fixture) | 0/2 |
| proofline | 0.4.0 | 9 | **77.8%** (7/9) [45.3, 93.7] · C | **88.9%** (8/9) [56.5, 98.0] · B | N/A (no checkpoint/sequence interface) | 0/2 |

## Escapes, named

| Tier | UIBC Core | proofbundle | proofline |
|---|---|---|---|
| `open` | `M17 key swap`, `M20 whole-bundle rollback` | `M03 key swap`, `M10 replay`, `M11 base64 alias` | `M03 key swap`, `M10 replay` |
| `pinned` | `M20 whole-bundle rollback` | `M03 key swap`, `M11 base64 alias` | `M10 replay` |
| `head-pinned` | none | not measured | not measurable (no interface) |

## What each row actually teaches

**1. `open` always leaks key substitution — that is correct.** With no anchor, a self-signed bundle verifies against its own key. A tool that claims otherwise is lying.

**2. proofbundle: pinning the content root does not pin the signer.** Re-sign the same payload with an attacker key → RFC 6962 leaf unchanged → `--expected-root` still matches → accepted. The verifier exposes no key-pin flag. Lesson: **for evidence, pin the key, not just the root.**

**3. proofline: integrity is tight, freshness is absent.** Output tampering, signature flip, metadata edit, step truncation, digest zeroing and an *empty signature array* are all rejected (`signatures must be a non-empty array when present` — fail-closed, good). But a whole-bundle replay of an older run signed by the same key is accepted **at both tiers**, because nothing binds recency or sequence. Lesson: **integrity ≠ freshness**; a verifier can pass every "was this tampered with?" question and still say yes to "is this the latest run?"

**4. UIBC Core is the only tool here whose escape set collapses to zero at `head-pinned`.** Its remaining escape at `pinned` is whole-bundle rollback (`M20`), which is exactly what the log-head tier exists for.

## Operational gotcha found while measuring

`proofline sign` **appends** a signature instead of replacing it. A naive "key-substitution" mutant therefore kept the legitimate signature and passed the key-pinned tier — producing a false accusation. The adapter now clears the signature set first and signs only with the attacker key. **Any cross-implementation test on multi-signature bundles must mutate the whole signature set, not a single entry.** This is recorded rather than silently fixed, because that class of mistake is exactly what makes external measurements untrustworthy.

## Why totals are still not comparable

- UIBC Core: 21 families from its own author's corpus (includes rollback and whole-bundle replay).
- proofbundle / proofline: only families applicable to a single-step bundle (rollback/reorder structurally `N/A`).
- Compare **rates within a tier**, never 90.5% vs 70.0% as a ranking. Both scorecards list their `not_applicable` set.

## Reproduction

```bash
python tools/erm_scorecard.py mutation_benchmark.json out_uibc.json
python adapters/proofbundle_adapter.py --exe "$(command -v proofbundle)" --out out_pb.json
python adapters/proofline_adapter.py  --exe "$(command -v proofline)"  --out out_pl.json
```

## Conflict disclosure

UIBC Core is maintained in the same ecosystem as this repo's author; proofbundle and proofline are independent third-party projects. All numbers are reproducible with the commands above. Deltas should be filed as issues and recorded, not folded into the table.
