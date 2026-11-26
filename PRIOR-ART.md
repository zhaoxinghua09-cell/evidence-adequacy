# Prior art (checked 2026-11-27)

This repo was built on a claim that turned out to be wrong, and it is cheaper to write that down than to be caught by a reviewer.

**The earlier claim**: "the adequacy of a verifier is unoccupied ground — nobody measures whether these things actually catch anything."

**Actual state**: at least two parties are already there, one commercial and one academic.

## Occupants

| Who | What they measure | Where |
|---|---|---|
| **Mendmark** (`mendmark-evals`, released 2026-08-12) | Agent **evaluation suites**: plants one controlled fault, reruns the same evaluators, counts killed/survived, gates releases on critical survivors. Ships an Enterprise Outcome Golden Set (8 workflows, 16 invariants, 64 mutations) and a multi-agent set (294 mutations), reports profile-by-profile kill rates (263/263 complete vs 87/263 response-only), delegates signatures to Sigstore Cosign. | https://pypi.org/project/mendmark-evals/ |
| **arXiv 2610.02928** "Discriminating Fixture Coverage in Agent-Infrastructure Verification Suites" (2026-10-02) | **Invariant suites** for an agent state-projection layer: a first-order mutant survives the standard correct/all-defects pair; after repair, ten mutants specified by an adversarial reader who designed none of the fixtures → 5 killed. Publishes the frozen suite hash, the mutants, the survivors, and separates the 5/10 post-freeze result from the 10/10 same-set repair result. | https://arxiv.org/pdf/2610.02928v1 |
| **arXiv 2610.09142** (AppWorld / WorkArena oracle audit) | **Task verifiers**: keeps the shipped checker unmodified, perturbs trajectories and effects, and counts a checker's PASS on a confirmed wrong effect as an inadequate oracle. Explicitly distinguishes its unit of mutation from classical mutation testing. | https://arxiv.org/html/2610.09142v1 |

## What this repo does that the three above do not

1. **Measures other people's published verifiers, not its own suite.** Mendmark writes and audits its own evaluator profiles; 2610.02928 audits its own invariant suite. ERM points at three shipped CLIs (UIBC Core 0.5.5, proofbundle 6.6.1, proofline 0.4.0) with one foreign mutator and reports what each one lets through. The object under test is somebody else's release.
2. **A three-tier aperture.** `open` / `pinned` / `head-pinned` are measured separately, so a tool can look strong or weak depending on which tier a user actually runs. Neither Mendmark nor the papers report tier-dependence; they report one configuration.
3. **It reports its own config-dependence against itself.** UIBC Core leaks `inject` in the default mode and kills it in `--strict` (6/9 vs 9/9). A metre that only measures others is not evidence of anything.

## What the others do better, stated plainly

- **Pre-registration.** 2610.02928 enumerates discriminating dimensions *in advance*, predicts which survivors each fixture will kill, then adds fixtures — all five predictions held. ERM has no pre-registered prediction; the families were chosen after seeing proofbundle's CLI, which is exactly the bias the paper guards against.
- **Scale and business framing.** Mendmark: 263 and 294 pinned mutations with profile breakdowns, plain-language risk headlines, release gates, tool-rollout hashes. ERM: 9–10 mutants per tool, n small enough that the Wilson interval is ±20 points.
- **Two modes of missing.** The paper separates "never activated" from "activated but unobservable". ERM only reports killed/survived, which collapses those two.

## Consequence for claims

Do not claim "first", "only", or "unoccupied" about adequacy measurement. The defensible sentence is narrower:

> One foreign mutator, three published verifiers, three tiers each, and the escape set of every tool named — including ours, in the configuration most users run.

## References

- Mendmark (PyPI, 2026-08-12): https://pypi.org/project/mendmark-evals/
- arXiv 2610.02928 (2026-10-02): https://arxiv.org/pdf/2610.02928v1
- arXiv 2610.09142 (2026-10-06): https://arxiv.org/html/2610.09142v1
