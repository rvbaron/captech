"""Citation parsing and anchor resolution: `gr_citation.anchor_key`'s source.

Milestone 1, Step 6a of `docs/exec-plans/active/reqs-to-data-store.md`.

Two functions live here and they are two halves of one job. `parse_citation`
turns the extractor's `path:line-line` strings into `(path, start, end)`
triples; `resolve_anchor` turns one such triple into the `AnchorResolution`
whose `primary` lands in `gr_citation.anchor_key`.

**Everything this module returns is a hash input**, and that is the whole
reason it is one module with its own tests rather than a few lines at the
ingest call site. `sorted(anchor_keys)` is the tier-1 input to *both*
`dedupe_key` and `dedupe_key_anchor_only`, so the anchors must exist at the
moment a `gr` row is keyed -- a later "resolution pass" arrives after stage
one has already decided what merged. Two implementations that break a tie
differently produce different `dedupe_key`s for the same rule, and the merge
then stops working with no error anywhere.

Three invariants carry the design, and each has a silent failure behind it:

* **`primary` is never the empty string.** The file-level anchor
  (`identity.file_anchor_key`) is a *total* floor. If unresolved anchors
  collapsed to `""`, `dedupe_key_anchor_only` would degenerate to
  ``'' ␟ rule_class ␟ pattern`` -- identical for every rule in the corpus
  sharing a class and a pattern -- and stage one would auto-merge them on the
  very first ingest.
* **The primary is exactly one symbol, the innermost one.** Not the set: a
  citation inside a method must not also pick up its class, or adding an
  unrelated sibling method to that class would re-key the rule. The full set
  is still recorded, in `AnchorResolution.all`, because "which symbols does
  this requirement touch?" is a first-class query -- but that set is not a
  key input and must never become one.
* **No key input may depend on whether the repository has been indexed.** The
  file-level floor is index-independent by construction: `file_anchor_key`
  fixes `language` at the empty string (`NORMATIVE SPEC-3` §S3.1.1). Do not
  "improve" it by resolving `repo_files.language` or calling
  `detect_language` -- the same citation would then key differently before
  and after an `index` run.

`resolution` records which of the three happened (`symbol`, `file`,
`unresolved`) and is stored on `gr_citation.anchor_resolution`. Without it, a
run against a repository with no index at all produces a full corpus of
file-level anchors that looks exactly like a healthy one.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final, MutableMapping, NamedTuple

from .identity import file_anchor_key, normalize_path
from .migrations import symbol_anchor_key
from .models import AnchorHit, AnchorResolution

if TYPE_CHECKING:  # pragma: no cover - typing only, and avoids an import cycle
    from .store import SQLiteStore

__all__ = [
    "WHOLE_FILE_END_LINE",
    "AnchorResolver",
    "CitationParseError",
    "FileState",
    "HashCache",
    "parse_citation",
    "resolve_anchor",
]


WHOLE_FILE_END_LINE: Final[int] = 2**31 - 1
"""The `end_line` `parse_citation` gives a citation with no line range.

A bare path means "the whole file", and Step 6a lists that among the cases
that take the **file-level** anchor. So the sentinel is a shared constant
rather than a magic number repeated in two places: `parse_citation` writes it
and `resolve_anchor` reads it.
"""


class CitationParseError(ValueError):
    """A malformed citation, raised only by `parse_citation(strict=True)`.

    Non-strict parsing skips a malformed entry, which is right for the
    coverage command's best-effort denominator and **wrong at ingest**, where
    Step 3 says do not drop the citation.
    """


_BARE_RANGE: Final = re.compile(r"\d+(?:-\d*)?")
"""A range with no path: the continuation shape `path:24-26,62-70` already had."""

_PATH_WITH_RANGE: Final = re.compile(r".+:\d+(?:-\d*)?(?:,\d+(?:-\d*)?)*")
"""A whole citation: a path, a colon, and one or more comma-separated ranges."""


def _split_citations(entry: str) -> list[str] | None:
    """Split one entry into several citations, or `None` if it is not a list.

    The extractor also writes **two files in one `source` string**
    (`A.java:96-118, B.java:44-51`) -- 30 citations on 29 of 186 rules in the
    first scoped two-round run, a third of them the same file twice with the
    path repeated rather than the `path:a-b,c-d` form `_parse_range_list`
    handles. Left unsplit, `rpartition(":")` takes the *last* colon, so the
    path becomes the whole comma-joined string and the line numbers belong to
    the **second** file: the first range is discarded and the citation
    resolves `unresolved`, exiting zero.

    **A list is recognized only when every piece is well formed** -- each
    either a whole `path:range` or a bare-range continuation of the piece
    before it. One piece that is neither returns `None`, and the caller keeps
    the pre-existing whole-entry behaviour for the entire entry. That is the
    same all-or-nothing rule `_parse_range_list` documents, kept at the entry
    grain on purpose: half a citation keys a rule on a subset of its evidence
    and looks healthy.

    Args:
        entry: One citation entry, list marker already stripped.

    Returns:
        Two or more citation strings, or `None` when the entry is not a
        citation list and must be parsed exactly as it always was.
    """
    if "," not in entry:
        return None
    pieces = entry.split(",")
    if not _PATH_WITH_RANGE.fullmatch(pieces[0].strip()):
        return None
    segments = [pieces[0].strip()]
    for piece in pieces[1:]:
        candidate = piece.strip()
        if _BARE_RANGE.fullmatch(candidate):
            segments[-1] = f"{segments[-1]},{candidate}"
        elif _PATH_WITH_RANGE.fullmatch(candidate):
            segments.append(candidate)
        else:
            return None
    return segments if len(segments) > 1 else None


def _parse_range_list(range_part: str) -> list[tuple[int, int]]:
    """Parse a citation's trailing range text into one `(start, end)` per range.

    A citation may name **several ranges in one file**, comma-separated
    (`path:24-26,62-70`), which the extractor emits legitimately -- 9 of 133
    confirmed rules did so on the first real NNG extraction. Each range
    becomes its own triple, so a two-range citation resolves two symbol
    anchors instead of degrading to a whole-file one.

    Single-range text takes exactly the path it always took: this is the same
    `split("-", 1)` body, run once per comma-separated piece.

    Args:
        range_part: The text after the citation's final colon, already known
            to contain nothing but digits, `-` and `,`.

    Returns:
        One `(start, end)` pair per range, in input order. A bare line number
        (`7`) yields `(7, 7)`, as does a half-open `7-`.

    Raises:
        ValueError: For a piece that is not a parseable `start-end` pair --
            `1-2-3`, `--`, or the empty piece a trailing comma leaves behind.
            The caller decides whether that raises or is skipped.
    """
    ranges: list[tuple[int, int]] = []
    for piece in range_part.split(","):
        lo_hi = piece.split("-", 1)
        start = int(lo_hi[0])
        end = int(lo_hi[1]) if len(lo_hi) > 1 and lo_hi[1] else start
        ranges.append((start, end))
    return ranges


def parse_citation(raw: str, strict: bool = False) -> list[tuple[str, int, int]]:
    """Parse `path:start-end` citation strings into `(path, start, end)` tuples.

    **This is the parser promoted out of `cli.py`**, so that the coverage
    denominator and the ingest anchor resolution cannot disagree about what a
    citation is. `cli._parse_claimed_citations` delegates here with
    `strict=False`. Do not write a second parser beside this one -- and note
    that being the single parser means any change here moves the coverage
    denominator and the ingest anchor set together, which is the point.

    Accepts either a JSON array of strings or newline-delimited strings. A
    citation with no line range (`path` only) is treated as covering the whole
    file (lines 1..`WHOLE_FILE_END_LINE`). A trailing range may be a
    **comma-separated list** (`path:24-26,62-70`), and one entry may carry
    **several whole citations** (`A.java:96-118, B.java:44-51`) -- the
    extractor emits both shapes legitimately, and each range of each citation
    becomes its own triple. A multi-citation entry is recognized only when
    *every* comma-separated piece is well formed; one piece that is neither a
    whole `path:range` nor a bare-range continuation leaves the entire entry
    parsed exactly as it was before, which is `_split_citations`'s contract.
    A leading list marker
    (`- `, `* `, `• `) is tolerated and stripped, so callers that hand us a
    bulleted list don't turn the marker into part of the path. The path itself
    may contain colons, so the range is split from the right.

    Args:
        raw: A JSON array of citation strings, or newline-delimited ones.
        strict: When false (the default, and the coverage command's mode),
            malformed entries are skipped silently. When true, the first
            malformed entry raises `CitationParseError` instead: at ingest a
            dropped citation is a dropped `anchor_key`, which changes a
            `dedupe_key` without anything reporting it.

    Returns:
        One `(relative_path, start_line, end_line)` triple **per range of
        each citation**, in input order. A citation naming a single range
        yields one triple, as it always has; `path:24-26,62-70` yields two
        triples sharing a path, and `A.java:1-2, B.java:5-9` yields two with
        different paths. **The list length is therefore not the number of
        citation strings** -- a caller counting citations must count entries,
        not triples.

    Raises:
        CitationParseError: Only when `strict` is true -- for text that opens
            like a JSON array but does not parse, for a JSON payload that is
            not a list of strings, for an entry that is nothing but a list
            marker, and for a trailing `:range` that looks numeric but is not
            a parseable `start-end` pair -- including one piece of a
            comma-separated list, which fails the whole entry rather than
            silently keeping the pieces that parsed.

    **What strict mode deliberately does NOT catch, and where it surfaces
    instead.** An entry carrying no colon at all is indistinguishable from
    "a bare path meaning the whole file", which is a citation shape Step 6a
    requires this parser to accept -- so prose accidentally landing in the
    extractor's `source` field parses as a whole-file citation on a path that
    does not exist, rather than raising. That is deliberate: a false strict
    raise fails the entire ingest transaction (one transaction per run,
    Step 6), so rejecting a 470-rule extraction over one prose-shaped
    citation is a worse outcome than accepting it, and no whitespace or
    extension heuristic separates the two cases reliably -- a repo-relative
    path may contain spaces and may have no extension.

    Such an entry reaches `resolve_anchor`, fails the working-tree existence
    check, and is stored with `anchor_resolution = 'unresolved'`. **It
    therefore shares that label with the case the label was written for** --
    an extraction taken against a different checkout -- so `requirements
    stats` must describe the `unresolved` rate as *citations naming a path
    that is not in the working tree*, which is what it literally measures,
    and must not describe it as evidence of a stale checkout specifically.
    The two are different faults with the same remedy at this layer (look at
    the citation), which is why they are allowed to share the label; what is
    not allowed is a report that names only one of them. Pinned by
    `test_citations.py::test_a_colonless_entry_is_a_whole_file_citation_not_an_error`.
    """
    import json

    text = raw.strip()
    items: list[str]
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError) as exc:
            if strict:
                raise CitationParseError(
                    f"citation payload opens with '[' but is not valid JSON: "
                    f"{exc}"
                ) from exc
            items = []
        else:
            if isinstance(parsed, list):
                items = [str(x) for x in parsed]
            else:
                # Unreachable in practice -- text opening with `[` parses as a
                # list or not at all -- and kept because the promoted body is
                # kept verbatim. Hence no test: there is no input that gets
                # here.
                if strict:
                    raise CitationParseError(
                        f"citation payload parsed as JSON "
                        f"{type(parsed).__name__}, not a list"
                    )
                items = []
    else:
        items = [line.strip() for line in text.splitlines() if line.strip()]

    citations: list[tuple[str, int, int]] = []
    for item in items:
        entry = item.strip()
        # Tolerate a leading list marker ("- ", "* ", "• ") so a bulleted
        # citation line doesn't fold the marker into the path.
        entry = entry.lstrip("-*• \t").strip()
        if not entry:
            if strict:
                raise CitationParseError(
                    f"citation {item!r} has no path once its list marker is "
                    f"stripped"
                )
            continue
        # One entry may carry several citations (`A.java:1-2, B.java:5-9`), and
        # `_split_citations` returns None for anything that is not cleanly that
        # -- in which case the entry is parsed exactly as it always was.
        for entry_text in _split_citations(entry) or [entry]:
            _parse_entry(entry_text, item, strict, citations)
    return citations


def _parse_entry(
    entry: str, item: str, strict: bool, citations: list[tuple[str, int, int]]
) -> None:
    """Parse one citation and append its triples to `citations`.

    Args:
        entry: One citation, list marker stripped and already split out of any
            comma-separated citation list.
        item: The original entry, for error messages.
        strict: See `parse_citation`.
        citations: The accumulator to append to.

    Raises:
        CitationParseError: As `parse_citation` documents, when `strict`.
    """
    # Split off the trailing `:start-end` (or `:line`, or a comma-separated
    # list of either) range. The path may itself contain colons (e.g. a
    # Windows drive), so split from the right.
    path = entry
    ranges = [(1, WHOLE_FILE_END_LINE)]
    if ":" in entry:
        head, _, tail = entry.rpartition(":")
        range_part = tail.strip()
        if range_part and all(
            ch.isdigit() or ch in "-," for ch in range_part
        ):
            try:
                parsed_ranges = _parse_range_list(range_part)
            except ValueError as exc:
                if strict:
                    raise CitationParseError(
                        f"citation {item!r} has a trailing ':{range_part}' "
                        f"that is not a 'start-end' line range"
                    ) from exc
                # Non-strict: the whole entry, range text included, stays
                # the path and the citation covers the whole file. That is
                # the pre-existing fallback, unchanged.
            else:
                path = head
                ranges = parsed_ranges
    for start, end in ranges:
        citations.append((path.strip(), start, end))


# ----------------------------------------------------------------------
# The per-run file-state cache
# ----------------------------------------------------------------------


class FileState(NamedTuple):
    """One file's working-tree state: does it exist, and what does it hash to.

    Both halves answer a **per-file** question while citations arrive
    per-*rule*, and a dense corpus cites the same file hundreds of times in
    one ingest -- so they are computed once per file per run and cached.

    `exists` and `sha256` are separate because they answer different
    questions and an unreadable file separates them. `exists` false is the
    one case that produces `resolution = 'unresolved'`; `sha256` `None` on an
    existing file means "present but could not be hashed", which fails the
    staleness guard (so the citation takes the file-level anchor) without
    ever being mislabelled as absent.
    """

    exists: bool
    sha256: str | None


HashCache = MutableMapping[str, FileState]
"""A run-scoped `normalize_path(relative_path)` -> `FileState` mapping.

Deliberately a parameter and not module state. A module-level dict would
outlive the run that filled it, so a second ingest in the same process --
`requirements ingest` twice, or a test suite -- would answer the staleness
guard from the first run's hashes: the exact stale-index failure the guard
exists to prevent, moved from the database into memory. It is a
`MutableMapping` rather than a `dict` so a caller may hand in a bounded or
instrumented mapping.
"""


def _file_state(
    repo_root: Path, relative_path: str, cache: HashCache | None
) -> FileState:
    """Return (and memoize) one file's `FileState`.

    Args:
        repo_root: The working-tree root the citation's path is relative to.
        relative_path: An already-normalized repository-relative path.
        cache: The run's cache, or `None` for an uncached single lookup.

    Returns:
        The file's `FileState`.
    """
    if cache is not None and relative_path in cache:
        return cache[relative_path]
    state = _read_file_state(repo_root / relative_path)
    if cache is not None:
        cache[relative_path] = state
    return state


def _read_file_state(absolute_path: Path) -> FileState:
    """Hash a file on disk, tolerating absence and unreadability.

    `sha256` is `hashlib.sha256(raw_bytes).hexdigest()` -- the same digest
    `discovery.py` writes to `repo_files.sha256`, which is what makes the
    staleness comparison meaningful rather than merely type-correct.

    Args:
        absolute_path: The file to inspect.

    Returns:
        `FileState(exists=False, sha256=None)` when the path is not in the
        tree; `FileState(exists=True, sha256=None)` when it is there but
        cannot be read; otherwise the digest.
    """
    try:
        raw = absolute_path.read_bytes()
    except FileNotFoundError:
        return FileState(exists=False, sha256=None)
    except OSError:
        # A directory, a permission error, a lock: it *is* there, so this is
        # not the `unresolved` case. The staleness guard simply cannot be
        # satisfied, and the citation takes the file-level anchor.
        return FileState(exists=absolute_path.exists(), sha256=None)
    return FileState(exists=True, sha256=hashlib.sha256(raw).hexdigest())


# ----------------------------------------------------------------------
# Anchor resolution
# ----------------------------------------------------------------------


class _Candidate(NamedTuple):
    """One symbol the citation's range lands on, with its sort key."""

    span: int
    start_line: int
    qualified_name: str
    anchor_key: str
    containment: str


def _file_level(relative_path: str, resolution: str) -> AnchorResolution:
    """Build the file-level resolution, which is the floor and is total.

    `all` holds exactly the one entry, with `containment = 'contains'`: the
    file does contain the cited range, and `AnchorHit.containment` admits
    only `contains` and `intersects`.

    Args:
        relative_path: An already-normalized repository-relative path.
        resolution: `'file'`, or `'unresolved'` when the path is not in the
            working tree at all.

    Returns:
        The `AnchorResolution`, whose `primary` is never empty.
    """
    key = file_anchor_key(relative_path)
    return AnchorResolution(
        primary=key,
        all=[AnchorHit(anchor_key=key, containment="contains")],
        resolution=resolution,
    )


def resolve_anchor(
    store: "SQLiteStore | None",
    repo_root: Path,
    relative_path: str,
    start_line: int,
    end_line: int,
    *,
    hash_cache: HashCache | None = None,
) -> AnchorResolution:
    """Resolve one citation to the anchor that keys its requirement.

    The rules, in the order they are applied:

    1. **The path is not in the working tree** -> the file-level anchor,
       labelled `resolution = 'unresolved'`. This is not a third tier beneath
       the floor: the anchor is still *computed*, because the key space must
       stay bounded by path, and the label is what stops the store carrying
       confident-looking anchors for absent files. It is also a real signal --
       `requirements stats` reports it as what it measures, an extraction
       taken against a different checkout.
    2. **`store is None`** -- a supported ingest, not an error path -- or the
       file is not in the index, or the citation is a bare path meaning the
       whole file, or nothing in the file overlaps the range, or the index is
       **stale** for this file -> the file-level anchor with
       `resolution = 'file'`. Correct rather than degraded: the floor is
       index-independent by construction.
    3. Otherwise the **innermost containing** symbol wins, or -- if nothing
       contains the range -- the **smallest-span intersector**, both under one
       tie-break: smallest span, then smallest `start_line`, then
       `qualified_name` ascending. `resolution = 'symbol'`.

    **Write that tie-break as stated and do not vary it.** It is hashed.

    Every symbol the range contains or intersects, winner included, appears in
    `all` with its `containment`; entries are ordered by the same tie-break,
    so the primary is first. `all` is de-duplicated by `anchor_key` because
    `gr_citation_anchor`'s primary key is `(citation_id, anchor_key)` and two
    symbols in one file legitimately share an anchor when the file declares
    the same qualified name twice; where both a containing and an intersecting
    row share a key, `contains` is kept as the stronger statement.

    Args:
        store: The Layer-0 index, or `None` when the repository has no
            `index.sqlite`. **The caller must check
            `index_sqlite_path.exists()` before constructing a store** --
            `SQLiteStore._connect` creates the file on its first query, so
            constructing one against a missing path silently materializes an
            empty index and then fails on `no such table: symbols`.
        repo_root: The working-tree root. Not decoration: the staleness guard
            and the absent-path test both read the tree, and `SQLiteStore`
            knows only where the database is. Without it both rules quietly
            become no-ops and a stale index yields confidently wrong anchors.
        relative_path: The cited path, in any separator style; normalized
            here.
        start_line: The citation's first line (1-based).
        end_line: The citation's last line, inclusive.
        hash_cache: The run's `FileState` cache. Pass one per ingest --
            `AnchorResolver` exists to own it -- or `None` to hash this one
            file uncached.

    Returns:
        The `AnchorResolution`. `primary` is never the empty string.
    """
    path = normalize_path(relative_path)

    state = _file_state(repo_root, path, hash_cache)
    if not state.exists:
        return _file_level(path, "unresolved")

    if store is None:
        return _file_level(path, "file")

    # A bare path means the whole file, which Step 6a assigns to the
    # file-level anchor by name. Resolving it against symbols would hand the
    # whole file's anchor to whichever declaration happened to be smallest.
    if end_line >= WHOLE_FILE_END_LINE:
        return _file_level(path, "file")

    indexed_sha, rows = store.symbols_overlapping_lines(path, start_line, end_line)
    if indexed_sha is None or not rows:
        return _file_level(path, "file")

    # The staleness guard. If the file on disk is no longer the file that was
    # indexed, the stored spans describe source that is not there, so a
    # symbol match would be confidently wrong -- and it would feed both
    # dedupe keys. Prefer the floor.
    if state.sha256 is None or state.sha256 != indexed_sha:
        return _file_level(path, "file")

    candidates: list[_Candidate] = []
    for symbol_id, language, entity_class, qualified_name, sym_start, sym_end in rows:
        contains = sym_start <= start_line and sym_end >= end_line
        candidates.append(
            _Candidate(
                span=sym_end - sym_start,
                start_line=sym_start,
                qualified_name=qualified_name,
                # The one derivation, shared with the insert path and the
                # version-2 backfill, so this key is equal to the stored
                # `symbols.anchor_key` by construction rather than by
                # coincidence. `entity_class` is coalesced to `other` for the
                # single row shape the backfill cannot reach (a symbol whose
                # `file_id` names no `repo_files` row), which this query's
                # join excludes anyway.
                anchor_key=symbol_anchor_key(
                    language, entity_class or "other", qualified_name, path
                ),
                containment="contains" if contains else "intersects",
            )
        )

    # Innermost containing symbol, and exactly one. Only if nothing contains
    # the range do the intersectors become eligible -- a class that merely
    # overlaps must never outrank the method that encloses the citation.
    containing = [c for c in candidates if c.containment == "contains"]
    pool = containing or candidates
    winner = min(pool, key=lambda c: (c.span, c.start_line, c.qualified_name))

    ordered = sorted(candidates, key=lambda c: (c.span, c.start_line, c.qualified_name))
    hits: dict[str, str] = {}
    for candidate in ordered:
        if hits.get(candidate.anchor_key) == "contains":
            continue
        hits[candidate.anchor_key] = candidate.containment

    return AnchorResolution(
        primary=winner.anchor_key,
        all=[
            AnchorHit(anchor_key=key, containment=containment)
            for key, containment in hits.items()
        ],
        resolution="symbol",
    )


@dataclass
class AnchorResolver:
    """`resolve_anchor` with the run's store, root and file cache bound to it.

    This is the shape ingest is meant to use: build one per run, resolve every
    citation through it, and the staleness guard hashes each cited file once
    however many rules cite it. The cache is an instance attribute rather than
    module state precisely so that it dies with the run -- a cache that
    outlived it would answer the guard from a previous run's hashes.

    Attributes:
        store: The Layer-0 index, or `None` when there is none. See
            `resolve_anchor` for why `None` is a supported ingest.
        repo_root: The working-tree root.
        hash_cache: The run's `FileState` cache, shared across every call.
    """

    store: "SQLiteStore | None"
    repo_root: Path
    hash_cache: HashCache = field(default_factory=dict)

    def resolve(
        self, relative_path: str, start_line: int, end_line: int
    ) -> AnchorResolution:
        """Resolve one citation, reusing this run's file-state cache.

        Args:
            relative_path: The cited path, in any separator style.
            start_line: The citation's first line (1-based).
            end_line: The citation's last line, inclusive.

        Returns:
            The `AnchorResolution`, exactly as `resolve_anchor` computes it.
        """
        return resolve_anchor(
            self.store,
            self.repo_root,
            relative_path,
            start_line,
            end_line,
            hash_cache=self.hash_cache,
        )
