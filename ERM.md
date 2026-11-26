# ERM — Escape-Rate Matrix, spec v0.1

Status: draft. Not submitted to any standards body. Not a certification scheme.

## 1. Problem

"Verifiable evidence" tools report a binary: valid / invalid. A binary says nothing about **how much forgery the verifier actually catches**, nor about which trust configuration it needs to catch what. Buyers and reviewers have no comparable number.

Existing suites answer conformance, not adequacy:
- `tuf-conformance` — official TUF client conformance suite; measures spec compliance, publishes a pass-rate table.
- `sigstore-conformance` — `verify-bundle` CLI protocol; per-implementation pass / xfail counts.
- `agent-evidence-vectors` — 62 corpora, 288-vector default corpus, accept/reject vectors, `--verifier` differential mode.
- Aqta `attestation-spec` vectors — "a conformant verifier MUST return valid:false for every invalid vector".

All of them: pass/fail per vector. None: kill rate per trust tier with an interval. ERM supplies that column.

## 2. Tiers

| Tier | Trusted state | Required ability |
|---|---|---|
| `T0 open` | none | full self-verification only |
| `T1 pinned` | signer public key OR expected content root | bind identity or content |
| `T2 head-pinned` | log head / root + monotonic sequence | detect rollback, truncation, history replacement |

Rules:
- Every scorecard MUST state which tier it measured.
- Tiers MUST NOT be merged into one "detection rate".
- A tool lacking a tier's prerequisite is `N/A` for that tier, listed explicitly.

## 3. Mutant families (minimum 12)

| ID | Family | Mutation |
|---|---|---|
| M01 | payload tamper | flip a byte/field in payload |
| M02 | signature flip | alter signature bytes |
| M03 | key substitution | re-sign with attacker key (self-signed bundle) |
| M04 | rollback | present an older valid bundle as current |
| M05 | truncation | drop trailing entries / shrink size |
| M06 | injection | add an unknown field or entry |
| M07 | reorder | swap entries in a sequence |
| M08 | metadata edit | change claims/time/version fields |
| M09 | root swap | replace Merkle/evidence root |
| M10 | whole-bundle replay | replay a different valid bundle |
| M11 | encoding alias | base64 padding, unicode normalisation, case |
| M12 | proof omission | delete the proof field |

Families structurally inapplicable to a given bundle shape (e.g. single-leaf bundles have no rollback/reorder) are recorded as `N/A` and removed from the denominator, with the exclusion listed.

## 4. Metrics

Per tier t:

- `kill_rate(t) = killed / n`, reported with a **95% Wilson interval** (small-n safe; Wald is not).
- `false_reject_on_legit` = legitimate bundles rejected / legitimate bundles tested. A verifier that rejects everything must score 0 here.
- Grade: A ≥ 0.95, B ≥ 0.80, C ≥ 0.50, D < 0.50. **Overall grade = min over measured tiers** (weakest tier governs).

## 5. Scorecard schema (`erm-scorecard/v0.1`)

```json
{
  "schema": "erm-scorecard/v0.1",
  "subject": {"tool": "...", "package": "...", "package_version": "..."},
  "corpus": {"source": "...", "mutants": 21},
  "tiers": {
    "open": {"mutants": 21, "killed": 19, "kill_rate_pct": 90.5,
             "wilson95": [0.711, 0.974], "grade": "B", "escaped": ["M17", "M20"]},
    "pinned": {...},
    "head-pinned": {...}
  },
  "false_reject_on_legit": {"legit_rc_open": 0, "legit_rc_pinned": 0, "false_reject_on_legit": 0},
  "not_applicable": [{"id": "M04", "family": "rollback", "why": "single-leaf bundle"}],
  "overall": {"weakest_tier": "open", "strongest_tier": "head-pinned", "headline": "..."},
  "caveats": ["..."]
}
```

## 6. Eligibility (a verifier must satisfy these to be measured)

1. machine-readable verdict (accept / reject / inconclusive) **with a reason code**;
2. explicit tier declaration in its own interface (key pin, root pin, checkpoint);
3. **fail-closed on missing proof** — absence of a proof field must not mean "pass";
4. stable exit-code contract distinguishing pass / reject / error;
5. runnable offline (isolated re-measurement).

Violating 1, 3 or 4 → `unrated`. That verdict is itself a finding.

## 7. Adapter protocol

Modeled on `tuf-conformance`'s client-under-test CLI and `agent-evidence-vectors --verifier`:

```
adapter verify <bundle> [--expected-root <b64>] [--expected-key <b64>] [--checkpoint <file>]
  exit 0 = accepted
  exit 1 = rejected
  exit 2 = error / unreadable input
```

Any tool that can expose this thin surface can be scored. Adapters live in `adapters/`; each is read-only against the target.

## 8. Limits (must be printed in every scorecard)

- Mutants are evaluator-constructed: **evaluator imagination is the ceiling**.
- Small n → wide intervals; grades are coarse bins.
- Measures *recognition of tampering*, not *truth of the claim*.
- Does not cover implementation bugs, dependency poisoning, or trust-anchor compromise.
- Conformance and adequacy are orthogonal: a tool can be fully conformant and still let a family through at a given tier.

## 9. Roadmap

1. Expand the mutator to 12 families for every adapter; add multi-leaf/rollback fixtures.
2. Add adapters: `proofline`, `agent-evidence-vectors` reference verifier, AIVS reference implementation.
3. Publish a rolling cross-tool table with dates, versions, and reproduction commands.
4. Offer the harness to tool authors as a CI step (scorecard per release, rate drift visible).
