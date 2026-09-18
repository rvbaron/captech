# A content-based credential gate for the indexer

**Status: PENDING — designed enough to start, not started.** The *gate* has no branch and no code.
The **notice** shipped 2026-09-14 (`src/legacylift_search/credential_notice.py`, wired into
`Indexer.run` after discovery): it scans the discovered `.properties` set for credential-shaped keys
with literal values and prints a warning naming the files, the key names, and — when
`embedding.provider` is `api` — that the values will be transmitted. It **excludes nothing, redacts
nothing and refuses nothing**, so every decision below stands untouched and this plan is still the
work. It exists because the pre-v4.0.0 review found the exposure documented in three places and
surfaced in none, and because a warning needs none of the five open questions answered.

Written 2026-09-08, as the deferred half of a decision recorded in
[`active/layer0-extraction-gap-detection.md`](../active/layer0-extraction-gap-detection.md)'s
Decision Log ("`.properties` files are indexed despite carrying real cleartext credentials").

**This file is the definitive record of its own state.** Measurements, open questions and next
action live here.

---

## Purpose / Big Picture

Layer 0 indexes source files into `chunks`, mirrors their text into FTS5, and — with
`embedding.provider: "api"` — sends that text to Amazon Bedrock for embedding. **It has no concept
of a secret.** Nothing in the pipeline looks at what a file contains before storing and transmitting
it.

That was survivable while `include_globs` named only programming-language extensions. The 2026-09-08
coverage widening added `**/*.properties`, which in a Java application is precisely where
credentials live.

The gap detector has the concept and the indexer does not, and the two are not interchangeable:

| | `gaps.walk_repository` | `discover_source_files` |
|---|---|---|
| credential concept | a `credential` **tier**, outranking every other tier including `indexed` | none |
| how it decides | extension in `.p12 .jks .keystore .pfx .pem`, or filename/stem in `sstruststore`, `cacerts` | — |
| reads contents | **never** — deliberate, and stated in its docstring | reads the whole file for its SHA-256 |
| what it does | reports that the file exists, emits no content | stores the text, mirrors to FTS5, embeds it |

So the walk would not have caught NNG's exposure either: not one of the 15 affected files is a
keystore. The walk's rule is filename-shaped because its job is to *report without reading*; a gate
that protects the index has to be content-shaped, because that is where the secret is.

**What this is not.** Not a secret scanner, not a remediation tool, and not a replacement for
`/modernize-assess`'s `SECRETS.local.md` step, which owns telling a human what to rotate. This is
one narrow question asked at one point in the pipeline: *should this file's text be stored and
transmitted?*

---

## The measurement that motivates the work

Measured 2026-09-08 against `repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app`, by
key-name pattern over non-comment `key=value` lines. **Values were characterized by length,
distinctness and encryption prefix; they were never recorded, and must not be.**

- 44 first-party `.properties` files (excluding `bin/`, `target/`, `build/`).
- **15 of them carry 22 credential-shaped keys with literal, non-placeholder values.**
- `application-prod1.properties` is among them.

| key | files | distinct values | value length | encrypted |
|---|---|---|---|---|
| `spring.cloud.config.password` | 3 | 3 | 25, 50 | no |
| `hazelcast.group.password` | 13 | 1 | 11 | no |
| `server.ssl.key-store-password` | 2 | 1 | 8 | no |
| `server.ssl.trust-store-password` | 2 | 1 | 8 | no |
| `javax.net.ssl.trustStorePassword` | 2 | 1 | 8 | no |

Five further keys held `${...}` interpolations and are correctly *not* secrets.

Read the table carefully, because it argues against the crudest possible gate. The three 8-char
keystore passwords are almost certainly the Java default `changeit` — public knowledge, not a
secret. The `spring.cloud.config.password` values (25 and 50 chars, three distinct) are the real
exposure. **A gate that treats every `*password*` key as a secret has a false-positive rate of
roughly 8-in-22 on this corpus**, and each false positive silently removes a file from the index —
the exact failure mode the coverage widening exists to end.

### Re-measured 2026-09-14 — the `changeit` hypothesis did not hold, and the exposure is larger

The notice's scanner was run over the same corpus as its first real-corpus check. It classifies a
value as a publicly-documented default by comparing it against a denylist (`changeit`, `changeme`,
`password`, `admin`, …); the classifier is unit-tested and does fire on `changeit`. Values were not
printed, recorded or otherwise read out — only the classification was.

| | 2026-09-08 (by hand) | 2026-09-14 (scanner) |
|---|---|---|
| first-party `.properties` | 44 | 44 |
| files with findings | 15 | **17** |
| credential-shaped keys | 22 | **24** |
| matching a known public default | ~8 assumed | **0** |

Two corrections follow, and the second is the one that matters:

1. **Two keys were missed by hand.** `app.b2c.policyCertFile.secret` appears in 2 files and is in no
   row of the table above — it accounts for the whole +2 files / +2 keys delta. The hand
   measurement enumerated `*password*` keys; `*secret*` was not in its net.
2. **None of the 24 values is `changeit`.** The paragraph above inferred the Java default from an
   8-character length, and `changeit` is itself 8 characters — so the length matched and the
   inference did not. The estimated 8-in-22 false-positive rate is **0-in-24** as measured. That
   removes this section's strongest argument against a key-name gate, and it means the real
   exposure is 24 live credentials rather than ~14.

**This does not make a crude gate right**, and open question 2 stands: a rule validated on one
corpus is exactly what the gap plan's methodology exists to distrust, and ctcm-api has not been
measured at all. What it does change is the cost side — the argument for deferring can no longer
lean on a false-positive rate that was assumed rather than measured.

---

## Decisions already settled

- **Decision: the index is not the place to *fix* a secret, only to avoid *spreading* it.** The gate
  decides storage and transmission. Rotation, `.gitignore`, and vaulting are someone else's job and
  are already owned by `/modernize-assess`.
  Rationale: an indexer that edited client source would be a far larger change than this and nobody
  has asked for it.

- **Decision: file-level exclusion is the wrong default; redaction at chunk level is the shape to
  aim for.** A `.properties` file is mostly configuration that is genuinely useful to retrieve —
  datasource URLs, cache sizes, feature flags, endpoint hostnames. Dropping
  `application-prod1.properties` entirely to hide one line costs the other forty.
  Rationale: measured — the 15 affected files hold 22 credential lines between them, out of
  ~1,900 lines total.

- **Decision: whatever the rule is, a suppressed value must leave a visible trace.** A redacted
  chunk keeps the key and replaces the value; a skipped file gets a `PARSE_NOTE`-shaped log line and
  a row somewhere countable.
  Rationale: this repository's whole gap-detection posture is that silent omission is the failure
  mode. A credential gate that silently shrinks the index would be the same defect wearing a
  security badge.

---

## Open questions — these need a design conversation, which is why this is a draft

1. **Where does the gate run?** Three candidates, and they are not equivalent:
   - In `discovery`, as a fourth gate beside include/exclude/language/size. Simplest, but it can
     only exclude whole files, which the second decision above rejects.
   - In `chunking`, redacting values as chunks are built. Right granularity. But the full text is
     also written to `repo_files`/`chunks` for `store_full_chunk_text_in_sqlite`, so the redaction
     has to happen upstream of *every* consumer or it leaks out the side.
   - In the read of the file itself, before anything sees the text. Most robust, and it means the
     SHA-256 no longer matches the file on disk — which breaks incremental reindex's change
     detection unless the hash is taken pre-redaction.
   The third is probably right with the hash carve-out, but that interaction is exactly why this is
   not a small item.

2. **What is the rule?** Key-name patterns alone are too crude (see the `changeit` false positives).
   Candidates to combine: key-name pattern **and** value entropy; a known-public-defaults denylist
   (`changeit`, `password`, `admin`); value length; `ENC(...)`/`{cipher}` prefixes meaning
   already-encrypted and therefore safe. **Do not hand-roll entropy scoring without measuring it on
   both reference corpora** — the gap plan's methodology exists because every rule fitted to one
   corpus broke on contact with the second.

3. **Which file types?** `.properties` is the motivating case, but `.xml` (Spring datasource beans),
   `.yaml`/`.yml` (not currently indexed) and `.json` all carry the same shape. Scoping to
   `.properties` first is defensible; pretending the others are safe is not.

4. **Is `hash` vs `api` embedding a factor?** With `provider: "hash"` nothing leaves the machine, so
   the transmission half of the risk disappears and only local storage remains. Should the gate be
   stricter when the provider is `api`? Arguments both ways: a config-dependent security posture is
   hard to reason about, but so is paying a false-positive cost for a risk that is not present.

5. **What does the existing `SECRETS.local.md` step already produce, and can this reuse it?**
   Unexamined. If `/modernize-assess` already enumerates credential locations, the gate may be able
   to consume that list rather than re-deriving it — which would also make the two agree, the same
   argument that drove sharing `provenance.py` between the walk and discovery.

---

## Why it was deferred

The maintainer's decision on 2026-09-08 was that the NNG analysis directory is laptop-local, so the
storage half of the exposure is acceptable, and that Step 10 Phase 1 should not wait for this.

**Two caveats survive that rationale and should be read before anyone concludes the risk is
handled.** The first is that the re-measurement above puts the live count at 24, not ~14. The
second: Phase 1 runs `embedding.provider: "api"` against Bedrock. The credential-bearing chunks
*do* leave the laptop. "Secure to my laptop" covers `index.sqlite`; it does not cover the embedding
call.

---

## Interfaces and Dependencies

- `credential_notice.py` — **the shipped notice.** `SCANNED_SUFFIXES` (today `.properties` only),
  the key-name pattern, the placeholder rule and the public-default denylist all live here, and the
  gate must either consume them or replace them outright — a second, disagreeing copy of "what looks
  like a credential" is the thing `provenance.py` was extracted to prevent between the walk and
  discovery. Note its standing invariant: no value is carried out of the module, and `index.log`
  gets counts and paths but never key names.
- `indexer.py` — `Indexer.run`, immediately after discovery, is where the notice is emitted and
  where a gate would have to intercept.
- `tests/test_credential_notice.py` — pins the invariants above, including that an empty result
  renders nothing rather than an all-clear.
- `discovery.py` — `discover_source_files`, and the SHA-256 read at its end.
- `chunking.py` — `CodeChunker.chunk_file`, and `_CHONKIE_SKIP_LANGUAGES`, which already treats
  `properties` as a fallback-only language.
- `gaps.py` — `CREDENTIAL_EXTENSIONS` / `CREDENTIAL_NAMES` and the `credential` tier, which is the
  prior art and the thing this must *not* silently diverge from. If both grow rules, they should
  share a module, exactly as `provenance.py` was extracted so the walk and discovery could not
  disagree about third-party.
- `.claude/skills/code-modernization/commands/modernize-assess.md` — the `SECRETS.local.md` step
  (open question 5).
- `config.py` — any new setting, and note that a manifest-level opt-out re-creates the "security
  guarantee conditional on a manifest nobody re-reads" objection the gap plan's Decision Log already
  rejected once, for the credential tier's precedence.
