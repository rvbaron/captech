"""The SPEC-1 notation validator: twenty-eight checks over `gr.statement`.

Milestone 1, Step 4 of `docs/exec-plans/active/reqs-to-data-store.md`. The
checks themselves are `NORMATIVE SPEC-1` in
`docs/exec-plans/pending/reqs-to-data-store-plan-draft.md` (§S1.0 - §S1.12,
lines 5526-5917), and that section is implemented **literally** here: same
identifiers, same severities, same seed terms. Do not paraphrase it, re-derive
it, or improve it.

**It validates `statement` only.** `as_built` is deliberately exempt (§S1.7
item 5): it records what the code does in whatever words fit, and forcing it
into a normative template would destroy the distinction that having two fields
exists to create.

**Severity has exactly two values** (§S1.6). `ERROR` blocks the
`draft -> approved` transition and nothing else; `WARN` is recorded and never
blocks. **Nothing gates `draft` itself** — a bad extraction must still land,
because the data is the point. No check may be added, removed, or have its
severity changed without amending SPEC-1, so `CHECK_IDS` below is a closed
twenty-eight-value tuple breaking down as `V-CLASS` 2, `V-KW` 7, `V-SLOT` 3,
`V-VAG` 9, `V-SING` 1, `V-STY` 3, `V-ENF` 3.

Three amendments stand (§S1.12) and all three are implemented here:

* **A1** rescopes `V-STY-03` to items 2, 3 and 5 of the Baxter & Hendryx
  rubric, and exempts the `[Value]` slot of `D-CONST`/`D-INFER` from item 5.
* **A2** supplies `V-VAG-09`'s seed list, which the check previously lacked
  entirely — before A2 it could not be written at all.
* **A3** records that `V-VAG-04`'s `or` prohibition and `V-SING-01`'s
  conjoined-action test have **no site** on `D-COMPUTE`, `D-CONST` and
  `D-INFER`, whose post-keyword region is a `[Value]` rather than an
  `[Action]`.
* **A4** gives `V-VAG-03` a site: the `[Subject]` slot, firing only when the
  subject **is** `it`, `this` or `that`. Read as a seed list over the whole
  statement it fired on determiners and relative pronouns -- 26 findings on
  20% of the first real corpus, none of them a pronoun lacking an antecedent.

## How the slot-dependent checks get at 29148's slots

Five checks are written against Figure 1's slots and nothing stores slots, so
`split_slots` derives them from `statement` on every validation — which is the
point: a reviewer's edit is validated *as edited*, and the edited records are
exactly the ones review cares about. It is a **table lookup keyed on
`pattern`**, not a parser: §S1.4 gives an exact template per pattern, and
§S1.4 also says outright that `[Object]` is *absorbed into* `[Action]` in the
short construct, so a five-slot parser mis-parses the commonest sentence
shape. Two superseded designs, named so neither is reintroduced:

* A five-slot parser. Rejected: the `[Action]`/`[Object]` boundary is not a
  real boundary.
* A keyword-anchored two-part split ("everything after the keyword is the
  action"). Rejected because it is wrong for half the enum — the restricted
  keywords are *discontinuous* (`may ... only`), three patterns carry a
  *trailing* `[Condition]`, and three more do not follow Figure 1 at all. It
  fires two `ERROR`s on §S1.10 #3, which SPEC-1 marks conformant.

**Degradation is deliberate and is what stops one defect being reported four
times.** Where the split cannot be trusted — `pattern` is NULL, or the
statement does not match the pattern it claims — the three `V-SLOT` checks are
emitted **not evaluated** (`Finding.evaluated = False`) rather than as
passing, carrying the severity they would have had. A silent pass on the rows
where the extractor could not decide a `pattern` would make those checks look
verified when they were never run.

Two consequences of that rule are worth stating because they are easy to get
backwards:

* **A NULL `pattern` still yields an `[Action]` region when a keyword is
  present**, per A3, so `V-VAG-04`'s carve-out and `V-SING-01` keep their site
  on the least-reviewed part of the corpus. `[Condition]` is located
  *structurally* there (a leading comma clause, or a trailing `only if` /
  ` if ` clause), because those two delimiters are syntactic and need no
  template.
* **A non-NULL `pattern` whose template keyword cannot be located
  unambiguously yields no `[Subject]`, `[Action]` or `[Value]` at all** — only
  the structural `[Condition]`. "Unambiguously" means exactly one rule-keyword
  occurrence, and that occurrence being one the pattern's template accepts.
  §S1.10 #5 (*The system shall validate the order*, no keyword at all) and #6
  (*An order always must have a customer*, one keyword from each class) are
  both this case: the `V-KW` `ERROR` already names the real defect precisely,
  and three more findings derived from a boundary that was never found would
  name the wrong problem three times over.

## `V-STY-03` takes its symbol list as a parameter, not a store handle

`symbols` lives in `index.sqlite` and the GR tables live in
`knowledge.sqlite`, so the lookup A1's items 2 and 5 need is a cross-database
read that this signature cannot make — the identical objection §S1.6 uses to
route rubric item 6 out of the check entirely. Handing the validator a
`SQLiteStore` was rejected: it would make a pure, cheaply-testable function
depend on two databases and a working tree, and every `V-*` test would then
need an index fixture. So the caller builds `leaked_terms` and passes it in.
**Empty is a supported state, not an error** — there is no index, or none was
resolved — under which `V-STY-03` runs on its morphological fallback alone,
which is a real check rather than a stub. `requirements stats` is required to
say when the symbol half was unavailable, because a silently weaker check
reads as a cleaner corpus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from .models import Finding, GRRecord

__all__ = [
    "CHECK_IDS",
    "CONDITION_REQUIRING_PATTERNS",
    "FIGURE1_PATTERNS",
    "KeywordMatch",
    "PATTERN_KEYWORDS",
    "StatementSpans",
    "VALUE_PATTERNS",
    "can_approve",
    "find_keywords",
    "format_span",
    "split_slots",
    "validate_statement",
]


# ----------------------------------------------------------------------
# The closed check set (SPEC-1 §S1.6)
# ----------------------------------------------------------------------

#: Every finding identifier this module can emit, in specification order.
#: **Twenty-eight**, breaking down 2/7/3/9/1/3/3. If an implementation emits a
#: different number of distinct identifiers, one is missing or invented.
CHECK_IDS: Final[tuple[str, ...]] = (
    "V-CLASS-01",
    "V-CLASS-02",
    "V-KW-01",
    "V-KW-02",
    "V-KW-03",
    "V-KW-04",
    "V-KW-05",
    "V-KW-06",
    "V-KW-07",
    "V-SLOT-01",
    "V-SLOT-02",
    "V-SLOT-03",
    "V-VAG-01",
    "V-VAG-02",
    "V-VAG-03",
    "V-VAG-04",
    "V-VAG-05",
    "V-VAG-06",
    "V-VAG-07",
    "V-VAG-08",
    "V-VAG-09",
    "V-SING-01",
    "V-STY-01",
    "V-STY-02",
    "V-STY-03",
    "V-ENF-01",
    "V-ENF-02",
    "V-ENF-03",
)

#: The six `enforcement_level` values, in decreasing severity (§S1.5). An
#: **example set given by SBVR, derived from BMM** — cite them that way in any
#: client deliverable, never as a normative SBVR enum.
ENFORCEMENT_LEVELS: Final[frozenset[str]] = frozenset(
    {"strict", "deferred", "pre-authorized", "post-justified", "override", "guideline"}
)

#: The SEVEN patterns that follow 29148 Figure 1's slot skeleton, i.e. the ones
#: whose post-keyword region is an `[Action]`. **Seven, not six** -- SS1.4
#: carries ten patterns of which three are the D5 deviations
#: (`VALUE_PATTERNS`), and `7 + 3 == 10` is asserted. The ExecPlan's interface
#: sketch says "six" in two places and is the stale copy; a literal six would
#: leave one pattern in neither set.
FIGURE1_PATTERNS: Final[frozenset[str]] = frozenset(
    {"B-COND", "B-UNCOND", "B-PROHIB", "B-RESTRICT", "D-NEC", "D-IMPOSS", "D-RESTRICT"}
)

#: The three patterns §S1.4 says do **not** follow Figure 1 (deviation D5):
#: their post-keyword region is a `[Formula]` or `[Value]`, which is why
#: amendment A3 gives `V-VAG-04`'s `or` prohibition and `V-SING-01` no site on
#: them.
VALUE_PATTERNS: Final[frozenset[str]] = frozenset({"D-COMPUTE", "D-INFER", "D-CONST"})

#: The five patterns `V-SLOT-03` requires a `[Condition]` on.
CONDITION_REQUIRING_PATTERNS: Final[frozenset[str]] = frozenset(
    {"B-COND", "B-PROHIB", "B-RESTRICT", "D-RESTRICT", "D-INFER"}
)

#: The canonical keyword(s) each `pattern`'s §S1.4 template anchors on. Two
#: patterns accept two keywords rather than one, and that is D4 rather than
#: looseness: `should` / `should not` are legal behavioral keywords under the
#: condition `V-KW-05` states, and they take the same templates `must` /
#: `must not` do.
PATTERN_KEYWORDS: Final[dict[str, frozenset[str]]] = {
    "B-COND": frozenset({"must", "should"}),
    "B-UNCOND": frozenset({"must", "should"}),
    "B-PROHIB": frozenset({"must not", "should not"}),
    "B-RESTRICT": frozenset({"may ... only"}),
    "D-NEC": frozenset({"always"}),
    "D-IMPOSS": frozenset({"never", "not always"}),
    "D-RESTRICT": frozenset({"can ... only"}),
    "D-COMPUTE": frozenset({"is to be computed as"}),
    "D-INFER": frozenset({"is to be considered"}),
    "D-CONST": frozenset({"is to be fixed at"}),
}

#: The four literals `V-SLOT-02` rejects. **All four are `ERROR`s**, so a
#: subject that reaches for "the application" to avoid "the system" has gained
#: nothing.
BANNED_SUBJECTS: Final[frozenset[str]] = frozenset(
    {"the system", "the application", "the software", "the program"}
)


# ----------------------------------------------------------------------
# The shared keyword matcher (§S1.3)
# ----------------------------------------------------------------------
#
# **Written once because four consumers must agree on what an occurrence is.**
# `V-KW-01`, `V-KW-04`, `V-KW-06` and `split_slots` all ask the same question
# and two implementations of it will disagree. Two properties are load-bearing:
#
#   * The four restricted keywords match as a **pair** — the modal (`may` or
#     `can`) plus the first following `only` in the same sentence — and count
#     as **one** occurrence. Without that, *A branch manager may grant a spot
#     discount only if the rental is open* carries two keywords and `V-KW-04`
#     fires an `ERROR` on a conformant `B-RESTRICT`.
#   * **Longest candidate first**: `must not` and `should not` are tested
#     before `must` and `should`, or every prohibition is read as its positive
#     and the split table's "after keyword" boundary lands four characters
#     early, putting a stray `not` at the head of `[Action]`. Python's `re`
#     alternation is leftmost-*first*, not leftmost-longest, so the ordering
#     in the alternation below is the mechanism, not a formatting choice.

_KEYWORD_SCAN: Final = re.compile(
    r"\b(?:"
    r"is\s+to\s+be\s+computed\s+as"
    r"|is\s+to\s+be\s+considered"
    r"|is\s+to\s+be\s+fixed\s+at"
    r"|should\s+not"
    r"|must\s+not"
    r"|shall\s+not"
    r"|not\s+always"
    r"|need\s+not"
    r"|must|should|shall|will|always|never|sometimes|may|can|only"
    r")\b",
    re.IGNORECASE,
)

#: canonical literal -> (rule_class, kind). `kind` is one of `positive`,
#: `negative`, `restricted`, `special`, `advice`, `forbidden`. `forbidden` is
#: the three 29148 verbs SPEC-1 does not use (D1, D2) — they are what
#: `V-KW-03` catches and are **not** rule keywords.
_KEYWORD_CLASS: Final[dict[str, tuple[str | None, str]]] = {
    "must": ("behavioral", "positive"),
    "should": ("behavioral", "positive"),
    "must not": ("behavioral", "negative"),
    "should not": ("behavioral", "negative"),
    "always": ("definitional", "positive"),
    "never": ("definitional", "negative"),
    "not always": ("definitional", "negative"),
    "is to be computed as": ("definitional", "special"),
    "is to be considered": ("definitional", "special"),
    "is to be fixed at": ("definitional", "special"),
    "need not": ("behavioral", "advice"),
    "sometimes": ("definitional", "advice"),
    "shall": (None, "forbidden"),
    "shall not": (None, "forbidden"),
    "will": (None, "forbidden"),
}

#: The kinds that make an occurrence a **rule** keyword. Advice is explicitly
#: not one — SBVR cl. 12.1.4's Necessity is "No business rule is an advice."
RULE_KINDS: Final[frozenset[str]] = frozenset(
    {"positive", "negative", "restricted", "special"}
)


@dataclass(frozen=True)
class KeywordMatch:
    """One modal-keyword occurrence located in a `statement`.

    `canonical` is the §S1.3 literal in lower case, with a restricted pair
    written `"may ... only"` / `"can ... only"` so the pair has one name.
    `parts` carries one span for a contiguous keyword and **two** for a
    restricted pair; `span` is the full extent from the first part's start to
    the last part's end.
    """

    canonical: str
    rule_class: str | None
    kind: str
    span: tuple[int, int]
    parts: tuple[tuple[int, int], ...]

    @property
    def is_rule_keyword(self) -> bool:
        return self.kind in RULE_KINDS


def _sentence_end(text: str, pos: int) -> int:
    """Index of the sentence terminator at or after `pos`, else `len(text)`.

    A terminator is `.`, `;`, `!` or `?` followed by whitespace or the end of
    the string — so a decimal literal such as `1000.00` is not one, and a
    statement's own trailing full stop is.
    """
    for m in re.finditer(r"[.;!?]", text[pos:]):
        i = pos + m.start()
        if i + 1 >= len(text) or text[i + 1].isspace():
            return i
    return len(text)


def find_keywords(statement: str) -> list[KeywordMatch]:
    """Locate every §S1.3 keyword occurrence in `statement`, in order.

    Returns rule keywords, advice keywords and the three forbidden 29148
    modals. A bare `can` with no following `only` is **not** a keyword in any
    row of §S1.3's table and is dropped; so is an `only` no modal claimed.
    """
    raw: list[tuple[str, int, int]] = []
    for m in _KEYWORD_SCAN.finditer(statement):
        canonical = re.sub(r"\s+", " ", m.group(0)).lower()
        raw.append((canonical, m.start(), m.end()))

    out: list[KeywordMatch] = []
    consumed: set[int] = set()
    for i, (canonical, start, end) in enumerate(raw):
        if i in consumed:
            continue
        if canonical in ("may", "can"):
            limit = _sentence_end(statement, start)
            paired = None
            for j in range(i + 1, len(raw)):
                if raw[j][0] == "only" and raw[j][1] < limit:
                    paired = j
                    break
            if paired is not None:
                consumed.add(paired)
                only_start, only_end = raw[paired][1], raw[paired][2]
                rule_class = "behavioral" if canonical == "may" else "definitional"
                out.append(
                    KeywordMatch(
                        canonical=f"{canonical} ... only",
                        rule_class=rule_class,
                        kind="restricted",
                        span=(start, only_end),
                        parts=((start, end), (only_start, only_end)),
                    )
                )
            elif canonical == "may":
                # `may` with no following `only` is advice, not a rule
                # (§S1.3 footnote ‡), and is also `V-KW-07`'s whole heuristic.
                out.append(
                    KeywordMatch(
                        canonical="may",
                        rule_class="behavioral",
                        kind="advice",
                        span=(start, end),
                        parts=((start, end),),
                    )
                )
            continue
        if canonical == "only":
            continue
        rule_class, kind = _KEYWORD_CLASS[canonical]
        out.append(
            KeywordMatch(
                canonical=canonical,
                rule_class=rule_class,
                kind=kind,
                span=(start, end),
                parts=((start, end),),
            )
        )
    return out


# ----------------------------------------------------------------------
# The template-driven slot split (§S1.4)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class StatementSpans:
    """Character offsets of 29148's slots within one `statement`.

    Offsets rather than substrings, because `gr_finding.span` stores
    `"start-end"` into `statement` and a reviewer needs to see *which words*
    tripped a check.

    `action` and `value` are **mutually exclusive** rather than two names for
    one region: §S1.4 says `D-COMPUTE`, `D-CONST` and `D-INFER` do not follow
    Figure 1's slot structure. A check that reads `action` on one of those
    three gets `None` and must not fire — that is amendment A3.

    `degraded` is `True` when no template could be applied, and it is what
    makes the three `V-SLOT` checks emit as not-evaluated. It is not in the
    ExecPlan's sketch of this class because that sketch predates the rule; the
    state has to be carried somewhere, and a caller re-deriving it from
    `subject is None` would conflate "no template" with "an empty subject",
    which `V-SLOT-01` exists to distinguish.
    """

    subject: tuple[int, int] | None = None
    keyword: tuple[tuple[int, int], ...] | None = None
    condition: tuple[int, int] | None = None
    action: tuple[int, int] | None = None
    value: tuple[int, int] | None = None
    degraded: bool = False


def format_span(span: tuple[int, int] | None) -> str:
    """Render a span the way `gr_finding.span` stores it.

    `''` for a record-level finding — **never `None`**: `span` is inside that
    table's `UNIQUE` tuple and SQLite treats NULLs as distinct, so a NULL
    would let the same finding insert repeatedly.
    """
    if span is None:
        return ""
    return f"{span[0]}-{span[1]}"


def _trim(statement: str, start: int, end: int) -> tuple[int, int] | None:
    """Narrow a raw span past surrounding whitespace and edge punctuation."""
    while start < end and (statement[start].isspace() or statement[start] in ",;"):
        start += 1
    while end > start and (statement[end - 1].isspace() or statement[end - 1] in ".,;"):
        end -= 1
    if start >= end:
        return None
    return (start, end)


_ONLY_IF: Final = re.compile(r"\bonly\s+if\b", re.IGNORECASE)
_BARE_IF: Final = re.compile(r"\s+if\b", re.IGNORECASE)


def _structural_condition(statement: str) -> tuple[int, int] | None:
    """Locate `[Condition]` with no template, using §S1.4's two delimiters.

    A leading comma clause, or a trailing `only if` / ` if ` clause — both
    syntactic, so neither needs a `pattern`. Take whichever is present, the
    leading form first. Skipping this would silently lose `V-VAG-04`'s
    carve-out on exactly the rows nobody has classified yet, turning a
    conformant `or` inside a condition into an `ERROR` on the least-reviewed
    part of the corpus.
    """
    comma = statement.find(",")
    if comma != -1:
        return _trim(statement, 0, comma)
    m = _ONLY_IF.search(statement)
    if m:
        return _trim(statement, m.end(), len(statement))
    m = _BARE_IF.search(statement)
    if m:
        return _trim(statement, m.end(), len(statement))
    return None


def split_slots(
    statement: str, rule_class: str | None, pattern: str | None
) -> StatementSpans:
    """Split `statement` into 29148 slots by looking up `pattern`'s template.

    `rule_class` is accepted for signature stability with the ExecPlan's
    `Interfaces and Dependencies` contract and for callers that pass a record
    straight through; the boundaries themselves come from `pattern`, which
    already determines the class through §S1.4's partition.

    Returns a `StatementSpans` whose `degraded` flag is `True` whenever the
    template's keyword could not be located **unambiguously** — absent, or
    competing with a second rule keyword, or not one the pattern accepts.
    """
    rules = [m for m in find_keywords(statement) if m.is_rule_keyword]
    accepted = PATTERN_KEYWORDS.get(pattern or "", frozenset())
    determinate = (
        pattern is not None and len(rules) == 1 and rules[0].canonical in accepted
    )

    if not determinate:
        condition = _structural_condition(statement)
        if pattern is None and rules:
            # Amendment A3: with no pattern the two `[Action]`-bound checks
            # still run, over the post-keyword region. The first rule keyword
            # anchors it — with two of them `V-KW-04` already fires, and the
            # choice only has to be deterministic.
            kw = rules[0]
            if kw.kind == "restricted":
                raw = (kw.parts[0][1], kw.parts[1][0])
            else:
                raw = (kw.span[1], len(statement))
            if condition is not None and condition[0] >= raw[0]:
                raw = (raw[0], min(raw[1], condition[0]))
            return StatementSpans(
                keyword=kw.parts,
                condition=condition,
                action=_trim(statement, *raw),
                degraded=True,
            )
        return StatementSpans(condition=condition, degraded=True)

    kw = rules[0]
    subject: tuple[int, int] | None = None
    condition = None
    action: tuple[int, int] | None = None
    value: tuple[int, int] | None = None

    if pattern in ("B-COND", "B-PROHIB"):
        comma = statement.find(",")
        if 0 <= comma < kw.span[0]:
            condition = _trim(statement, 0, comma)
            subject = _trim(statement, comma + 1, kw.span[0])
        else:
            subject = _trim(statement, 0, kw.span[0])
        action = _trim(statement, kw.span[1], len(statement))
    elif pattern in ("B-UNCOND", "D-NEC", "D-IMPOSS"):
        subject = _trim(statement, 0, kw.span[0])
        action = _trim(statement, kw.span[1], len(statement))
    elif pattern in ("B-RESTRICT", "D-RESTRICT"):
        modal, only = kw.parts
        subject = _trim(statement, 0, modal[0])
        action = _trim(statement, modal[1], only[0])
        m = _ONLY_IF.match(statement, only[0])
        if m:
            condition = _trim(statement, m.end(), len(statement))
    elif pattern == "D-INFER":
        subject = _trim(statement, 0, kw.span[0])
        m = _BARE_IF.search(statement, kw.span[1])
        if m:
            value = _trim(statement, kw.span[1], m.start())
            condition = _trim(statement, m.end(), len(statement))
        else:
            value = _trim(statement, kw.span[1], len(statement))
    else:  # D-COMPUTE, D-CONST
        subject = _trim(statement, 0, kw.span[0])
        value = _trim(statement, kw.span[1], len(statement))

    return StatementSpans(
        subject=subject,
        keyword=kw.parts,
        condition=condition,
        action=action,
        value=value,
        degraded=False,
    )


# ----------------------------------------------------------------------
# Vagueness seed terms (§S1.6, 29148 cl. 5.2.7's nine classes)
# ----------------------------------------------------------------------
#
# **The seed terms are extensible; the nine classes are not.** Every list here
# is the standard's own examples, except `V-VAG-09`'s, which is amendment A2's
# — before A2 that class had no operative test at all, because "a reference"
# was never defined.

_VAG_TERMS: Final[dict[str, tuple[str, ...]]] = {
    "V-VAG-01": ("best", "most"),
    "V-VAG-02": ("user friendly", "easy to use", "cost effective"),
    "V-VAG-05": (
        "provide support",
        "but not limited to",
        "as a minimum",
        "etc.",
    ),
    "V-VAG-06": ("better than", "higher quality"),
    "V-VAG-07": ("if possible", "as appropriate", "as applicable"),
    "V-VAG-08": ("all", "always", "never", "every"),
}

#: Amendment A4's site for `V-VAG-03`. The check is **not** in `_VAG_TERMS`,
#: because its class is *vague pronouns* and a seed-list match over the whole
#: statement fires on words that are not pronouns at all: `that` as a
#: determiner (`that short name`) or a relative pronoun (`types that do not
#: allow ...`). Its site is the `[Subject]` slot, and it fires only when the
#: subject **is** one of these -- a bare pronoun where 29148 cl. 5.2.4 requires
#: a named subject. Measured on the first real corpus before A4: 26 findings on
#: 20% of the rules, at a severity that blocks approval, and none of the 26 was
#: a pronoun without an antecedent in its own sentence.
_VAG03_SUBJECT_PRONOUNS: Final[frozenset[str]] = frozenset({"it", "this", "that"})

#: `V-VAG-04` has two halves with different scopes. The adverbs and adjectives
#: are ambiguous wherever they appear; the **logical** terms are the ones
#: §S1.6's mandatory carve-out scopes to `[Action]`, because cl. 5.2.5
#: *Singular* NOTE 2 permits multiple conditions.
_VAG04_TERMS: Final[tuple[str, ...]] = ("almost always", "significant", "minimal")
_VAG04_LOGICAL: Final[tuple[str, ...]] = ("or", "and/or")

#: Amendment A2's seed list for `V-VAG-09`.
_VAG09_TERMS: Final[tuple[str, ...]] = (
    "ISO",
    "IEEE",
    "RFC",
    "ANSI",
    "NIST",
    "CFR",
    "the standard",
    "the specification",
    "the policy",
    "the manual",
    "the regulation",
    "the agreement",
)

#: Words that discharge `V-VAG-09` without carrying a number themselves.
_PART_DESIGNATORS: Final[frozenset[str]] = frozenset(
    {"part", "rev", "revision", "version", "edition", "annex", "clause", "section"}
)


def _term_regex(terms: tuple[str, ...]) -> re.Pattern[str]:
    """Compile a seed list into one whole-word alternation.

    Longest first, so `almost always` is not read as `always`; and the word
    boundaries are dropped at an edge that is not alphanumeric, because `\\b`
    after the `.` of `etc.` would never match.
    """
    parts = []
    for term in sorted(terms, key=len, reverse=True):
        core = r"\s+".join(re.escape(w) for w in term.split())
        prefix = r"\b" if term[0].isalnum() else ""
        suffix = r"\b" if term[-1].isalnum() else ""
        parts.append(prefix + core + suffix)
    return re.compile("|".join(parts), re.IGNORECASE)


_VAG_REGEX: Final[dict[str, re.Pattern[str]]] = {
    k: _term_regex(v) for k, v in _VAG_TERMS.items()
}
_VAG04_REGEX: Final = _term_regex(_VAG04_TERMS)
_VAG04_LOGICAL_REGEX: Final = _term_regex(_VAG04_LOGICAL)
_VAG09_REGEX: Final = _term_regex(_VAG09_TERMS)


# ----------------------------------------------------------------------
# Style checks (§S1.6)
# ----------------------------------------------------------------------

_STY01_PATTERNS: Final = (
    re.compile(r"\bit\s+is\s+required\s+that\b", re.IGNORECASE),
    re.compile(r"\bit\s+shall\s+be\s+possible\s+to\b", re.IGNORECASE),
    re.compile(r"\bis\s+to\s+be\s+\w+(?:ed|en)\s+by\b", re.IGNORECASE),
)
_STY02_REGEX: Final = re.compile(r"\b(?:shall|must)\s+be\s+able\s+to\b", re.IGNORECASE)

#: The three special-purpose definitional keywords are **required passives**
#: (deviation D5) and are exempt from `V-STY-01`. Without this carve-out every
#: computation rule fails.
_STY01_EXEMPT: Final = re.compile(
    r"\bis\s+to\s+be\s+(?:computed\s+as|considered|fixed\s+at)\b", re.IGNORECASE
)

#: `V-STY-03`, rubric item 5's morphological fallback — the half that works
#: with no index. These catch most of what §S1.10 #10 is about.
_STY03_MORPHOLOGY: Final = (
    re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b"),  # ALL-CAPS-WITH-HYPHENS
    re.compile(r"\b\w*_\w+\b"),  # snake_case / any token with an underscore
    re.compile(r"\b[a-z][a-z0-9]*[A-Z]\w*\b"),  # camelCase
    re.compile(r"\b[A-Z][a-z0-9]+[A-Z]\w*\b"),  # PascalCase with an internal cap
)

#: `V-STY-03`, rubric item 3 — implementation technology used as business
#: vocabulary. A seed list on the same convention as the nine `V-VAG` classes,
#: seeded from what a real corpus produces: exception type names, dotted
#: lowercase message keys, and framework vocabulary.
_STY03_ITEM3: Final = (
    re.compile(r"\b\w+Exception\b"),
    re.compile(r"\b[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){2,}\b"),
)
_STY03_FRAMEWORK: Final = _term_regex(
    (
        "servlet",
        "jsp",
        "jdbc",
        "hibernate",
        "struts",
        "ejb",
        "dao",
        "dto",
        "pojo",
        "resultset",
        "stored procedure",
        "http request",
        "http response",
        "null pointer",
        "database table",
        "foreign key",
    )
)


# ----------------------------------------------------------------------
# Singularity (§S1.6 `V-SING-01`)
# ----------------------------------------------------------------------
#
# Determiners and function words, used to decide whether the token after an
# `and` heads a second *action* or merely a second object. The bias is
# deliberately toward under-firing: `V-SING-01` is an `ERROR`, and a false
# `ERROR` on conformant text makes a record permanently un-approvable, which
# is the failure §S1.6's carve-outs exist to prevent arriving by another door.

_DETERMINERS: Final[frozenset[str]] = frozenset(
    {
        "the", "a", "an", "its", "their", "his", "her", "this", "that",
        "these", "those", "each", "every", "all", "any", "no", "both",
        "either", "one", "two", "three",
    }
)
_ACTION_STOPWORDS: Final[frozenset[str]] = _DETERMINERS | frozenset(
    {
        "of", "to", "in", "on", "for", "with", "by", "from", "at", "as",
        "into", "over", "under", "within", "across", "not", "then", "if",
        "when", "only", "or", "and", "is", "are", "was", "were", "be",
        "been", "being", "it", "they", "he", "she",
    }
)
_WORD: Final = re.compile(r"[A-Za-z][A-Za-z0-9'-]*")


def _conjoined_action_spans(statement: str, action: tuple[int, int]) -> list[tuple[int, int]]:
    """Spans of each `and` inside `[Action]` that joins a second action.

    Heuristic, and deliberately conservative: the token after `and` heads a
    second action when it is not a function word **and** the token after
    *that* is a determiner or the region ends. So *recalculate the balance and
    notify the customer* fires (`notify` + `the`), while *record the vendor
    number and shipping address* does not (`shipping` + `address`).
    """
    hits: list[tuple[int, int]] = []
    start, end = action
    for m in re.finditer(r"\band\b", statement[start:end], re.IGNORECASE):
        rest = statement[start + m.end() : end]
        tokens = _WORD.findall(rest)
        if not tokens:
            continue
        head = tokens[0].lower()
        if head in _ACTION_STOPWORDS:
            continue
        following = tokens[1].lower() if len(tokens) > 1 else None
        if following is None or following in _DETERMINERS:
            hits.append((start + m.start(), start + m.end()))
    return hits


# ----------------------------------------------------------------------
# validate_statement
# ----------------------------------------------------------------------


def _add(
    findings: list[Finding],
    finding_id: str,
    severity: str,
    span: tuple[int, int] | None,
    message: str,
    evaluated: bool = True,
) -> None:
    findings.append(
        Finding(
            finding_id=finding_id,
            severity=severity,
            span=format_span(span),
            message=message,
            evaluated=evaluated,
        )
    )


def _overlaps(span: tuple[int, int], other: tuple[int, int]) -> bool:
    return span[0] < other[1] and other[0] < span[1]


def _inside(span: tuple[int, int], region: tuple[int, int] | None) -> bool:
    return region is not None and span[0] >= region[0] and span[1] <= region[1]


def validate_statement(
    gr: GRRecord, leaked_terms: frozenset[str] = frozenset()
) -> list[Finding]:
    """Run all twenty-eight SPEC-1 checks over `gr.statement`.

    Args:
        gr: The requirement. Only `statement`, `rule_class`, `pattern`,
            `category` and `enforcement_level` are read — the rest of the
            record is untouched, and `as_built` is exempt by §S1.7 item 5.
        leaked_terms: `symbols.name` and `qualified_name` values for the
            requirement's cited files, for `V-STY-03`'s rubric items 2 and 5.
            **Empty is a supported state** meaning no index was available, not
            an error: the check then runs on its morphological fallback alone.
            The caller builds this set (`refresh_gr_derived_sql`, Step 5) —
            `symbols` is in the other database, and giving this function a
            store would make every `V-*` test need an index fixture.

    Returns:
        Findings sorted by identifier then span, so two runs over one record
        produce the same list in the same order. A finding carrying
        `evaluated = False` is a check that **could not be decided**, never
        one that passed.
    """
    statement = gr.statement
    spans = split_slots(statement, gr.rule_class, gr.pattern)
    keywords = find_keywords(statement)
    rules = [k for k in keywords if k.is_rule_keyword]
    findings: list[Finding] = []

    # -- Class -------------------------------------------------------------
    if gr.rule_class is None:
        _add(
            findings,
            "V-CLASS-01",
            "ERROR",
            None,
            "rule_class is NULL. SPEC-1 §S1.2 step 4: it must never be "
            "guessed, and a NULL blocks approval.",
        )
    if (gr.category == "Calculation" and gr.rule_class == "behavioral") or (
        gr.category == "Validation" and gr.rule_class == "definitional"
    ):
        _add(
            findings,
            "V-CLASS-02",
            "WARN",
            None,
            f"category {gr.category!r} usually correlates with the other "
            f"rule_class; {gr.rule_class!r} is often still correct.",
        )

    # -- Keywords ----------------------------------------------------------
    if gr.rule_class is None:
        # Both checks are written against "its rule_class's set", and with no
        # class there is no set. Not evaluated rather than passing: a check
        # nobody could run and a check that ran clean are different facts.
        _add(
            findings,
            "V-KW-01",
            "ERROR",
            None,
            "not evaluated: rule_class is NULL, so there is no keyword set "
            "to test membership against (see V-CLASS-01).",
            evaluated=False,
        )
        _add(
            findings,
            "V-KW-02",
            "ERROR",
            None,
            "not evaluated: rule_class is NULL, so neither the keyword nor "
            "the pattern partition has a class to disagree with.",
            evaluated=False,
        )
    else:
        own = [k for k in rules if k.rule_class == gr.rule_class]
        if not own:
            _add(
                findings,
                "V-KW-01",
                "ERROR",
                None,
                f"statement contains no {gr.rule_class} keyword (SPEC-1 §S1.3).",
            )
        for k in rules:
            if k.rule_class != gr.rule_class:
                _add(
                    findings,
                    "V-KW-02",
                    "ERROR",
                    k.span,
                    f"{k.canonical!r} is a {k.rule_class} keyword on a "
                    f"{gr.rule_class} rule. The two sets are disjoint "
                    "(SPEC-1 §S1.3).",
                )
        if gr.pattern is not None:
            expected_prefix = "B-" if gr.rule_class == "behavioral" else "D-"
            if not gr.pattern.startswith(expected_prefix):
                _add(
                    findings,
                    "V-KW-02",
                    "ERROR",
                    None,
                    f"pattern {gr.pattern!r} is from the other class's "
                    f"partition; rule_class is {gr.rule_class!r} (§S1.4).",
                )

    for k in keywords:
        if k.kind == "forbidden":
            _add(
                findings,
                "V-KW-03",
                "ERROR",
                k.span,
                f"{k.canonical!r} is a 29148 modal verb that SPEC-1 does not "
                "use (deviations D1, D2).",
            )

    if len(rules) > 1:
        for k in rules[1:]:
            _add(
                findings,
                "V-KW-04",
                "ERROR",
                k.span,
                "more than one rule keyword present; a requirement states one "
                "rule (29148 cl. 5.2.5 Singular). A restricted keyword "
                "('may ... only') counts as one.",
            )

    should = [k for k in rules if k.canonical in ("should", "should not")]
    if should and (
        gr.enforcement_level is None or gr.enforcement_level in ("strict", "deferred")
    ):
        for k in should:
            _add(
                findings,
                "V-KW-05",
                "ERROR",
                k.span,
                f"{k.canonical!r} needs an enforcement_level consistent with "
                "it (e.g. 'override' or 'guideline'); it is "
                f"{gr.enforcement_level!r}. Only a human can set one "
                "(enforcement_level is extractor-forbidden).",
            )

    advice = [k for k in keywords if k.kind == "advice"]
    if advice and not rules:
        _add(
            findings,
            "V-KW-06",
            "ERROR",
            advice[0].span,
            f"the only keyword is the advice keyword {advice[0].canonical!r}. "
            "SBVR cl. 12.1.4: 'No business rule is an advice.' Route this to "
            "a non-rule disposition rather than storing it with a pattern.",
        )
    for k in advice:
        if k.canonical == "may":
            _add(
                findings,
                "V-KW-07",
                "WARN",
                k.span,
                "'may' with no following 'only' reads as possibility rather "
                "than permission (RuleSpeak usage rule 2). Heuristic.",
            )

    # -- Slots -------------------------------------------------------------
    if spans.degraded:
        reason = (
            "pattern is NULL, so no template locates [Subject]"
            if gr.pattern is None
            else f"the {gr.pattern} template's keyword is not unambiguously "
            "present in statement, so no template locates [Subject]"
        )
        for check in ("V-SLOT-01", "V-SLOT-02", "V-SLOT-03"):
            _add(
                findings,
                check,
                "ERROR",
                None,
                f"not evaluated: {reason}.",
                evaluated=False,
            )
    else:
        if spans.subject is None:
            _add(
                findings,
                "V-SLOT-01",
                "ERROR",
                None,
                "no [Subject]. 29148 cl. 5.2.4: a requirement shall state its "
                "subject.",
            )
        else:
            subject_text = statement[spans.subject[0] : spans.subject[1]]
            if subject_text.strip().lower() in BANNED_SUBJECTS:
                _add(
                    findings,
                    "V-SLOT-02",
                    "ERROR",
                    spans.subject,
                    f"[Subject] is the placeholder {subject_text.strip()!r}. "
                    "All four placeholders are ERRORs; name the business "
                    "subject.",
                )
        if gr.pattern in CONDITION_REQUIRING_PATTERNS and spans.condition is None:
            _add(
                findings,
                "V-SLOT-03",
                "ERROR",
                None,
                f"pattern {gr.pattern} requires a [Condition] and none is "
                "present (§S1.4).",
            )

    # -- Vagueness ---------------------------------------------------------
    definitional_keyword_spans = [
        k.span for k in rules if k.rule_class == "definitional"
    ]
    for check, regex in _VAG_REGEX.items():
        for m in regex.finditer(statement):
            span = (m.start(), m.end())
            if check == "V-VAG-08" and gr.rule_class == "definitional":
                # MANDATORY carve-out (deviation D6): `always` and `never` are
                # SBVR's structural keywords. Without it the validator rejects
                # every well-formed definitional rule.
                if any(_overlaps(span, k) for k in definitional_keyword_spans):
                    continue
            _add(
                findings,
                check,
                "ERROR",
                span,
                f"{m.group(0)!r} is a vague or general term "
                "(29148 cl. 5.2.7).",
            )
    # `V-VAG-03` fires from its A4 site rather than from the loop above. When
    # no template locates `[Subject]` the check has no site, so it is emitted
    # **not evaluated** rather than silently passing -- the same rule A3 set
    # for the `[Action]`-bound checks, and for the reason this module's
    # docstring gives: a silent pass makes a check that never ran look
    # verified.
    if spans.degraded or spans.subject is None:
        _add(
            findings,
            "V-VAG-03",
            "ERROR",
            None,
            "not evaluated: no template locates [Subject], which is this "
            "check's only site (A4).",
            evaluated=False,
        )
    else:
        vag03_subject = statement[spans.subject[0] : spans.subject[1]].strip()
        if vag03_subject.lower() in _VAG03_SUBJECT_PRONOUNS:
            _add(
                findings,
                "V-VAG-03",
                "ERROR",
                spans.subject,
                f"[Subject] is the bare pronoun {vag03_subject!r}. 29148 "
                "cl. 5.2.4 requires a requirement to name its subject; "
                "cl. 5.2.7 lists vague pronouns among the terms to avoid.",
            )

    for m in _VAG04_REGEX.finditer(statement):
        _add(
            findings,
            "V-VAG-04",
            "ERROR",
            (m.start(), m.end()),
            f"{m.group(0)!r} is an ambiguous adverb or adjective "
            "(29148 cl. 5.2.7).",
        )
    if spans.action is not None:
        # §S1.6's mandatory carve-out: `or` is permitted inside [Condition]
        # (cl. 5.2.5 Singular NOTE 2) and is an ERROR inside [Action] or
        # [Object]. Amendment A3: no site at all on D-COMPUTE/D-CONST/D-INFER,
        # which is why this is keyed on `action` being populated.
        for m in _VAG04_LOGICAL_REGEX.finditer(
            statement[spans.action[0] : spans.action[1]]
        ):
            span = (spans.action[0] + m.start(), spans.action[0] + m.end())
            _add(
                findings,
                "V-VAG-04",
                "ERROR",
                span,
                f"{m.group(0)!r} inside [Action] is an ambiguous logical "
                "statement; it is permitted only inside [Condition].",
            )
    for m in _VAG09_REGEX.finditer(statement):
        if not _reference_is_resolvable(statement, m.end()):
            _add(
                findings,
                "V-VAG-09",
                "ERROR",
                (m.start(), m.end()),
                f"{m.group(0)!r} is an incomplete reference — no adjacent "
                "number, date or part designator (29148 cl. 5.2.7; seed list "
                "from SPEC-1 §S1.12 amendment A2).",
            )

    # -- Singularity -------------------------------------------------------
    if spans.action is not None:
        for span in _conjoined_action_spans(statement, spans.action):
            _add(
                findings,
                "V-SING-01",
                "ERROR",
                span,
                "'and' joins two actions inside [Action]; conditions may be "
                "conjoined, actions may not (29148 cl. 5.2.5 Singular). Split "
                "into two requirements.",
            )

    # -- Style -------------------------------------------------------------
    for regex in _STY01_PATTERNS:
        for m in regex.finditer(statement):
            if _STY01_EXEMPT.match(statement, m.start()):
                continue  # D5: the three special definitional keywords
            _add(
                findings,
                "V-STY-01",
                "ERROR",
                (m.start(), m.end()),
                f"{m.group(0)!r} is a passive construction (29148 cl. 5.2.4).",
            )
    for m in _STY02_REGEX.finditer(statement):
        _add(
            findings,
            "V-STY-02",
            "ERROR",
            (m.start(), m.end()),
            f"{m.group(0)!r} states a capability, not a requirement "
            "(29148 cl. 5.2.4).",
        )
    for span, token in _leakage_spans(statement, spans, gr.pattern, leaked_terms):
        _add(
            findings,
            "V-STY-03",
            "WARN",
            span,
            f"{token!r} is implementation leakage — a program symbol, "
            "framework term or unabstracted literal used as business "
            "vocabulary (Baxter & Hendryx items 2, 3 and 5; SPEC-1 §S1.12 "
            "amendment A1). It belongs in implementation_notes.",
        )

    # -- Enforcement -------------------------------------------------------
    if gr.enforcement_level is not None and gr.rule_class == "definitional":
        _add(
            findings,
            "V-ENF-01",
            "ERROR",
            None,
            "enforcement_level is legal only on a behavioral rule (SBVR "
            "cl. 12.1.3): a definitional rule cannot be violated at all.",
        )
    if (
        gr.enforcement_level is not None
        and gr.enforcement_level not in ENFORCEMENT_LEVELS
    ):
        _add(
            findings,
            "V-ENF-02",
            "ERROR",
            None,
            f"enforcement_level {gr.enforcement_level!r} is not one of the six "
            f"§S1.5 values {sorted(ENFORCEMENT_LEVELS)}.",
        )
    if gr.rule_class == "behavioral" and gr.enforcement_level is None:
        _add(
            findings,
            "V-ENF-03",
            "WARN",
            None,
            "behavioral rule with no enforcement_level. This is review "
            "progress, not a defect — only an SME can supply one.",
        )

    findings.sort(key=lambda f: (f.finding_id, _span_sort_key(f.span)))
    return findings


def _span_sort_key(span: str) -> tuple[int, int]:
    if not span:
        return (-1, -1)
    start, _, end = span.partition("-")
    return (int(start), int(end))


def _reference_is_resolvable(statement: str, end: int) -> bool:
    """True when a `V-VAG-09` seed term carries a number or part designator.

    Looks only inside the same clause and only thirty characters ahead, which
    is a heuristic and is documented as one: the class is closed, the test is
    not, and biasing toward under-firing keeps an `ERROR` off text that names
    its reference perfectly well a few words later.
    """
    window = statement[end : end + 30]
    clause = re.split(r"[,;.]", window, maxsplit=1)[0]
    if any(ch.isdigit() for ch in clause):
        return True
    return any(tok.lower() in _PART_DESIGNATORS for tok in _WORD.findall(clause))


def _leakage_spans(
    statement: str,
    spans: StatementSpans,
    pattern: str | None,
    leaked_terms: frozenset[str],
) -> list[tuple[tuple[int, int], str]]:
    """Spans of `V-STY-03`'s rubric items 2, 3 and 5, deduplicated.

    Items 2 and 5 reduce to "a code-shaped token appears in `statement`", and
    Layer 0 already knows which tokens those are — so `leaked_terms` is
    literally the check rather than a proxy for it, backed by a morphological
    fallback for symbols the parser missed. Item 3 takes a seed list on the
    same convention as the nine `V-VAG` classes.

    **Amendment A1's mandatory carve-out**: item 5 does not apply to the
    `[Value]` slot of `D-CONST` or `D-INFER`, which legitimately carry a
    literal. §S1.10 #3 is a conformant `D-INFER` containing *category 87* and
    *1000.00*.
    """
    exempt = spans.value if pattern in ("D-CONST", "D-INFER") else None
    hits: dict[tuple[int, int], str] = {}

    def record(span: tuple[int, int], token: str) -> None:
        if _inside(span, exempt):
            return
        hits.setdefault(span, token)

    for term in leaked_terms:
        if len(term) < 3:
            continue
        for m in re.finditer(rf"\b{re.escape(term)}\b", statement):
            record((m.start(), m.end()), m.group(0))
    for regex in _STY03_MORPHOLOGY:
        for m in regex.finditer(statement):
            record((m.start(), m.end()), m.group(0))
    for regex in _STY03_ITEM3:
        for m in regex.finditer(statement):
            record((m.start(), m.end()), m.group(0))
    for m in _STY03_FRAMEWORK.finditer(statement):
        record((m.start(), m.end()), m.group(0))

    return sorted(hits.items())


def can_approve(findings: list[Finding]) -> bool:
    """True when no *evaluated* `ERROR` finding stands (SPEC-1 §S1.9).

    The `evaluated` clause is defence in depth rather than load-bearing, and
    it is worth knowing why: the only condition that produces a not-evaluated
    row is an undecidable slot split, and the approval gate already refuses
    `approved` while `pattern IS NULL` as a schema precondition — so by the
    time a record is approvable every check is decidable. Write it anyway: a
    gate that reads correctly on its own is worth more than one that is
    correct only in combination with a precondition three paragraphs away.
    """
    return not any(f.severity == "ERROR" and f.evaluated for f in findings)
