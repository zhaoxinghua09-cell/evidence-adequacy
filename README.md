# evidence-adequacy

**A meter, not another verifier.**

Every evidence tool claims "I can verify". Almost none answers *"how much forgery does your verification actually catch, tier by tier?"* This repo answers that, with reproducible scorecards.

It is **not** a certification. It measures; it does not endorse.

---

## What is measured

For a verifier V and a corpus of known-bad bundles, for each **trust configuration**:

| Tier | Client holds | Designed to catch |
|---|---|---|
| `open` | nothing | byte tampering, root edits, metadata edits |
| `pinned` | signer key or expected content root | key substitution, wrong payload |
| `head-pinned` | log head + monotonic sequence | rollback, truncation, history replacement |

Output per tier: `killed / n`, **95% Wilson interval**, letter grade (A ≥95%, B 80–95%, C 50–80%, D <50%). Plus `false_reject_on_legit` — a verifier that kills everything is not good, it is useless.

## Results so far (both run on 2026-11-26, Windows 11 / Python 3.13.18)

| Verifier | open | pinned | head-pinned | false reject |
|---|---|---|---|---|
| **UIBC Core 0.5.5** (21 mutants) | 19/21 = **90.5%** [71.1, 97.4] · B | 20/21 = **95.2%** [77.3, 99.2] · A | 21/21 = **100%** [84.5, 100] · A | 0/2 |
| **proofbundle 6.6.1** (10 eligible mutants) | 7/10 = **70.0%** [39.7, 89.2] · C | 8/10 = **80.0%** [49.0, 94.3] · B | N/A (no checkpoint) | 0/2 |

Read the full comparison and the caveats in [`results/COMPARISON.md`](results/COMPARISON.md). Two findings worth the whole exercise:

1. **Both verifiers let a key-substitution escape at `open`.** Expected — with no anchor there is no identity.
2. **`proofbundle` still lets it escape at `pinned`**, because pinning the *content root* does not pin the *signer key*: an attacker re-signs the same payload, the Merkle root is identical, the pin matches. **For evidence, pin the key, not just the root.** That is a measurement result, not a defect claim — read their [NON_CLAIMS](https://pypi.org/project/proofbundle/) before quoting it.

## Reproduce

```bash
pip install uibc-core==0.5.5 proofbundle==6.6.1

# UIBC Core: use its own mutation benchmark output
python tools/erm_scorecard.py path/to/mutation_benchmark.json out.json

# proofbundle: drive its CLI, mutate, verify per tier
python adapters/proofbundle_adapter.py \
  --exe "$(python -c 'import shutil;print(shutil.which("proofbundle"))')" \
  --out out.json
```

The adapter only reads the target's CLI; it never edits the target repo. Bundles are created in a temp dir and deleted.

## Why this exists (the gap)

- **Conformance is crowded.** `tuf-conformance` (official TUF client suite, published pass-rate table), `sigstore-conformance` (`verify-bundle` CLI protocol), `agent-evidence-vectors` (62 corpora, 288-vector default corpus, differential external-verifier mode), Aqta `attestation-spec` vectors, TIBET evidence kit — all answer *"does it follow the spec"*.
- **Adequacy is not.** None of the above publishes *"at tier T, this verifier lets N of M known-bad inputs through"* with an interval. That is the one column this repo adds.

So the design borrows deliberately: the adapter protocol is modeled on `tuf-conformance`'s client-under-test CLI and on `agent-evidence-vectors --verifier`; the vectors are mutants, not spec cases.

## Layout

```
ERM.md                       spec v0.1: tiers, families, metrics, schema, conformance requirements
tools/erm_scorecard.py       reads a tool's own mutation output → scorecard
adapters/proofbundle_adapter.py   12-family mutator + per-tier CLI driver
results/ERM_scorecard_*.json scorecards (machine-readable)
results/COMPARISON.md        cross-tool table + interpretation + caveats
```

## Honest limits

- Mutants are constructed by the evaluator; **the evaluator's imagination is the ceiling**.
- Small n (10–21): intervals are wide; grades are coarse bins, not verdicts.
- It measures *evidence recognition*, not whether the evidence content is true. A passing verifier says nothing about whether the claim is correct.
- Not covered: implementation bugs (memory safety, dependency poisoning), which are a different audit.
- Cross-tool totals are **not** comparable (different corpora, different family coverage). Compare rates within a tier, and read the `not_applicable` list.

## Conflicts of interest

UIBC Core is maintained in the same ecosystem as this repo's author; proofbundle is not. Both were run with the same mutator where possible, and every number can be reproduced by the commands above. If a number here looks wrong, reproduce it and open an issue — we will record the delta, not edit the scorecard.

## License

MIT.
