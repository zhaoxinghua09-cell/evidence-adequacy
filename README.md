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

## The interface a verifier needs to be measurable at all

Six properties, each checkable in one command, with a compliance table for the three tools measured here: [`VERIFIER-INTERFACE.md`](VERIFIER-INTERFACE.md). Short version — P1 one entry point, P2 pin the signer, P3 pin the head, P4 machine-readable verdict, P5 exit code agreeing with it, P6 a PASS that names what it ignored. Two of three current subjects cannot meet P3, so that column is empty for them because the test could not be run.

## Prior art — read this before claiming the ground is empty

Adequacy measurement is **not** unoccupied. Mendmark (`mendmark-evals`, 2026-08-12) does mutation testing of agent *evaluation suites* with a release gate; arXiv 2610.02928 does mutation analysis of a *verification suite* with a pre-registered repair, 5/10 killed by externally specified mutants; arXiv 2610.09142 audits shipped AppWorld/WorkArena oracles for PASS-on-wrong-effect. What this repo adds is narrower: **one foreign mutator, three published verifiers, three tiers each** — and the only one of the four that measures somebody else's release rather than its own suite. Details, including what they do better, in [`PRIOR-ART.md`](PRIOR-ART.md).

## Results so far (one mutator, three tools — 2026-11-27, Windows 11 / Python 3.13.18)

| Verifier | open | pinned | head-pinned | false reject |
|---|---|---|---|---|
| **UIBC Core 0.5.5** (9 eligible) | 6/9 = **66.7%** · C | 7/9 = **77.8%** · C | 8/9 = **88.9%** · B | 0/3 |
| **proofbundle 6.6.1** (10 eligible) | 7/10 = **70.0%** · C | 8/10 = **80.0%** · B | N/A (no checkpoint) | 0/2 |
| **proofline 0.4.0** (9 eligible) | 7/9 = **77.8%** · C | 8/9 = **88.9%** · B | N/A (no sequence interface) | 0/2 |

Full intervals, escape names and methodology in [`results/COMPARISON.md`](results/COMPARISON.md). Four findings worth the whole exercise:

1. **With one shared mutator nobody is A-grade at `open`.** Each tool leaks a different subset; "strong detection" without a named corpus is unfalsifiable.
2. **UIBC Core scores better on its own 21-mutant benchmark (90.5/95.2/100) than on this shared mutator (66.7/77.8/88.9).** That gap is the argument for this repo: *a tool's own corpus flatters it*.
3. **UIBC Core leaks `inject` at all three tiers**: a file dropped into `evidence/` that the index never declared is tolerated in the default (lenient) mode — only `--strict` fails it. Reported against our own tool on purpose; the fix is pending approval.
4. **Rollback only dies at `head-pinned`**, and only UIBC exposes that tier with a working fixture path; proofbundle needs a checkpoint fixture, proofline has no sequence interface at all.

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


