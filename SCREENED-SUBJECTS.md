# Screened subjects — what could not be measured, and why

A measurement layer's real limit is not how many tools it can score but how many it must refuse. This file records the refusals, because a table that only lists what it measured hides the admission criteria.

Checked 2026-11-27. Six candidates were considered; three were measurable, three were not.

| Candidate | What it actually is | Measured? | Why not |
|---|---|---|---|
| **UIBC Core 0.5.5** | package verifier, `verify` with `--pubkey` / `--expect-head` / `--strict` | ✅ 12 + 2 families, 3 tiers (+ hardened mode) | — |
| **proofbundle 6.6.1** | bundle verifier, `verify-*` subcommands | ✅ 10 families, 2 tiers | no checkpoint fixture → `head-pinned` N/A |
| **proofline 0.4.0** | run verifier, `verify/diff/recover` | ✅ 9 families, 2 tiers | no sequence/checkpoint interface → `head-pinned` N/A |
| **evalwarden 0.14.1** | *linter for agent evaluations*: `audit` / `diff` / `trace` / `checks` / `explain` | ❌ | It audits an eval **artifact**, not a sealed evidence bundle. There is no entry point that takes (bundle, key, expected head) and returns accept/reject, so the three tiers have nothing to attach to. Scoring it with ERM would measure a different object and call the number comparable. |
| **agent-evidence-vectors 0.36.3** | 62 corpus families, 288 default vectors, 40 modules each named `verify_*` | ❌ (today) | No single `verify` entry point. A metre cannot enumerate mutants against an interface that is forty interfaces. It is a **corpus**, not a verifier — the right relationship is "they supply vectors, we supply the ruler", not a score. |
| **mendmark-evals** (2026-08-12) | *mutation engine for eval suites*: plants a controlled fault, reruns the evaluator, reports killed/survived, gates releases | ❌ | Incommensurable by construction: it is the same kind of object as ERM (a metre), not the object ERM measures. Running our mutator through it would produce a number about a different question. Its own golden-set numbers are the right thing to cite, not to re-measure. |

## The finding this table carries

Of six candidates, **three could not be scored at all**, and for three different reasons: wrong object (evalwarden), no single interface (agent-evidence-vectors), same kind of object as the metre (mendmark).

So the bottleneck in this space is **measurability**, not capability. A verification tool that exposes one `verify(bundle, key?, head?)` entry point can be audited by anyone; one that exposes forty modules, or none, cannot be audited even by a willing outsider. That is a concrete, checkable claim about adoption, and it costs nothing to state.

## Consequence for ERM's own claims

ERM scores 3 of 6 candidates. That is not a selection bias to apologise for — it is the honest denominator, and it should be printed next to any table: **"3 measurable of 6 screened; the other 3 are refused, with the reason."**
