# Verifier interface contract — one page

Why this page exists: the measurement in this repo found that three of six candidate tools could not be scored at all, and not because they were weak. `agent-evidence-vectors` exposes forty modules named `verify_*`; `evalwarden` audits a different object; `mendmark` is a metre, not a subject. A willing outsider cannot audit an interface that does not exist.

So the first deliverable of an adequacy layer is not a score. It is the **shape a verifier must have to be measurable at all**. This page states that shape in six properties, each checkable in one command, and then reports who currently meets it.

## The six properties

| # | Property | Exact form | Why it is required |
|---|---|---|---|
| **P1** | one entry point | `<cli> verify <path>` — one positional path argument, no required side files | A metre must be able to hand over a package it built itself. If the verifier needs a companion payload/vkey file, the metre has to reverse-engineer the producer. |
| **P2** | identity pin | a flag that supplies a public key **from outside the package** | Without it, a passing signature proves internal consistency only. Measured: `open` leaks key substitution in all three tools, correctly. |
| **P3** | freshness pin | a flag that supplies an expected head/sequence **from outside the package** | Without it, an older but self-consistent package is accepted. Measured: rollback dies only where this exists. Truncation does not need it. |
| **P4** | machine-readable verdict | stdout JSON containing a verdict field (`result` / `verdict`) | Prose and exit codes diverge eventually; a metre needs a field it can read without parsing sentences. |
| **P5** | exit-code contract | accept → `0`, reject → non-zero, **consistent with P4** | Two channels that can disagree are two answers; the metre can only record one. |
| **P6** | a PASS names what it ignored | when the verdict is accept but something was skipped, name it in a field | Otherwise "PASS" silently means "PASS within a narrower boundary than you think". This is what PR #562 added to UIBC Core. |

P1–P5 are the **auditability floor**. P6 is the honesty property; a tool can be measurable without it, but a reader cannot tell what a PASS bought.

## Compliance table (checked 2026-11-27 against the shipped CLIs)

Legend: ✅ met · ⚠️ partial · ❌ absent · — not verified this round

| Tool | P1 | P2 | P3 | P4 | P5 | P6 |
|---|---|---|---|---|---|---|
| **UIBC Core 0.5.5** | ✅ `verify <path>` | ✅ `--pubkey` | ✅ `--expect-head` (+`--state-file`) | ✅ `result` | ✅ 0 / 1, consistent | ✅ `warnings[]` (since `35e6214`) |
| **proofline 0.4.0** | ✅ `verify <path>` | ✅ `--signed-by <PEM>` | ❌ no head/sequence argument | — not verified | — | ❌ |
| **proofbundle 6.6.1** | ❌ needs `--payload-file` beside the proof | ⚠️ `--log-vkey` pins the **log**, not the signer | ⚠️ `--expected-origin` constrains the origin string, not the head | ✅ `--json` | — not verified | ❌ |

Read the table as a statement about **adoption cost**, not about security:

- **P1 fails for proofbundle** in the strict sense used here: `verify-proof` cannot judge a proof alone. The metre must reconstruct the exact leaf bytes, which is a producer-side job. That is the same obstacle an outside evaluator hits.
- **P2 partial for proofbundle** is the sharpest measured case: pinning the log key leaves the signer unpinned, and the earlier run showed `pinned` still accepts a re-signed payload because the Merkle leaf is unchanged.
- **P3 absent for both** third-party tools: neither lets a caller say "the head I expect is X". proofline has no sequence interface at all; proofbundle constrains only the origin string.

## What compliance buys, stated as a testable sentence

> Any verifier that meets P1–P5 can be scored by ERM in under an hour, by a party that did not write it.

That is the claim this page makes, and it is falsifiable: hand ERM a binary and the same six rows decide whether it can be measured at all. Two of three current subjects cannot meet P3, which is why the `head-pinned` column is empty for them — not because they failed the test, but because the test could not be run.

## What UIBC Core still owes

P6 is met only in the tightened sense (warnings on undeclared evidence). **P3 has no default**: the safe configuration is opt-in, so the column is ✅ for the CLI and ❌ for the path most users take. Until `--strict` or an equivalent becomes default, the honest cell for "UIBC Core as shipped, as used" is ⚠️.

## Non-goals

This page does not define a bundle format, a trust model, or a scoring rubric. It defines only the shape an interface needs for a foreign party to be able to ask it a question and get an answer it can record.
