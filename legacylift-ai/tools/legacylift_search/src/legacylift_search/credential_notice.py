"""Tell the operator when indexing is about to store and transmit credentials.

This is the *notice* half of the credential problem, not the gate. Layer 0 has
no concept of a secret: it reads a discovered file whole, stores its text in
`chunks`, mirrors it into FTS5, and — with ``embedding.provider="api"`` — sends
that text to Amazon Bedrock. Nothing in that path ever looked at what the file
contained. That was survivable while ``include_globs`` named only
programming-language extensions; the 2026-09-08 coverage widening added
``**/*.properties``, which in a Java application is exactly where credentials
live. Measured on the NNG corpus: 15 of 44 first-party ``.properties`` files
carry 22 credential-shaped keys with literal values, ``application-prod1``
among them.

**This module warns. It never excludes, redacts, or refuses.** That division is
deliberate and is settled design, recorded in
``docs/exec-plans/pending/indexer-credential-gate.md``:

- File-level exclusion is the wrong default — a ``.properties`` file is mostly
  configuration worth retrieving, and dropping the file to hide one line costs
  the other forty. The gate that is actually wanted redacts at chunk level, and
  its five open design questions are not answered yet.
- A rule fitted to key names alone is too crude to act on silently. On NNG, 8
  of the 22 matches are almost certainly the Java default ``changeit`` — public
  knowledge, not a secret. A gate with that false-positive rate would remove
  files from the index without saying so, which is the precise failure mode the
  coverage widening exists to end. A *warning* with that false-positive rate
  costs a human ten seconds.

**Values are never read out of this module.** A finding carries the file, the
line number and the key name — never the value, not in the return type, not in
the rendered text, and not in ``index.log``. Value shape is used only to decide
whether a line is a finding at all, and is discarded immediately.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

# Scoped to `.properties` on purpose. It is the measured motivating case, and
# the one shape this module can parse without guessing. `.xml` carries the same
# exposure through Spring datasource beans and `.json` would too — the draft's
# open question 3 — but a scanner that half-reads XML and reports "clean" would
# be worse than one that says plainly which formats it looked at. The rendered
# notice states the scope for exactly that reason.
SCANNED_SUFFIXES = frozenset({".properties"})

# Key-name patterns. Matched against the casefolded key. Deliberately generous:
# this decides what a human is asked to look at, not what gets dropped.
_CREDENTIAL_KEY_RE = re.compile(
    r"(password|passwd|pwd|secret|token|credential|api[-_.]?key|access[-_.]?key"
    r"|private[-_.]?key|auth[-_.]?key|signing[-_.]?key)",
    re.IGNORECASE,
)

# Values that are not secrets, and the reason each is exempt:
#   ${...} / {{...}} / @...@  — unresolved interpolation; the secret is elsewhere
#   ENC(...) / {cipher}...    — already encrypted at rest (Jasypt, Spring Cloud)
#   empty                     — nothing there
_PLACEHOLDER_RE = re.compile(
    r"""^(
          \$\{.*\}
        | \{\{.*\}\}
        | @[^@\s]+@
        | ENC\(.*\)
        | \{cipher\}.*
    )$""",
    re.VERBOSE | re.IGNORECASE,
)

# Publicly-documented default values. A match here is still reported — hiding it
# would be this module deciding for the operator — but it is counted separately,
# because on the reference corpus these are the majority of the noise and a
# reader who cannot tell them apart will learn to ignore the whole notice.
_KNOWN_PUBLIC_DEFAULTS = frozenset(
    {"changeit", "changeme", "password", "passwd", "admin", "secret", "default", "none"}
)


@dataclass(frozen=True)
class CredentialFinding:
    """One credential-shaped assignment. Carries no value, by construction."""

    relative_path: str
    line_number: int
    key: str
    # True when the value is a publicly-documented default (`changeit` and
    # friends). Derived from the value and then the value is dropped.
    looks_like_public_default: bool


@dataclass(frozen=True)
class CredentialNotice:
    """What the scan found, and what the operator needs to decide about it."""

    findings: tuple[CredentialFinding, ...] = ()
    files_scanned: int = 0
    # True when this run's embedder sends chunk text off the machine. It does
    # not change what is reported — only how urgently it reads.
    transmits_offsite: bool = False
    provider: str = ""

    @property
    def files_affected(self) -> tuple[str, ...]:
        seen: list[str] = []
        for f in self.findings:
            if f.relative_path not in seen:
                seen.append(f.relative_path)
        return tuple(seen)

    @property
    def likely_real(self) -> tuple[CredentialFinding, ...]:
        return tuple(f for f in self.findings if not f.looks_like_public_default)

    def __bool__(self) -> bool:
        return bool(self.findings)


def _scan_properties_text(relative_path: str, text: str) -> list[CredentialFinding]:
    """Findings for one `.properties` file's text.

    Line-oriented and intentionally simple: `.properties` allows continuation
    lines and escapes that a full parser would honour, but a missed key is a
    missed warning, whereas a wrong one is a false alarm a human must chase. The
    conservative direction here is to under-report, and the notice says so.
    """
    findings: list[CredentialFinding] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line[0] in "#!":
            continue
        # `.properties` accepts `=` and `:` as separators.
        sep_index = min(
            (i for i in (line.find("="), line.find(":")) if i > 0),
            default=-1,
        )
        if sep_index < 0:
            continue
        key = line[:sep_index].strip()
        value = line[sep_index + 1 :].strip()
        if not key or not _CREDENTIAL_KEY_RE.search(key):
            continue
        if not value or _PLACEHOLDER_RE.match(value):
            continue
        findings.append(
            CredentialFinding(
                relative_path=relative_path,
                line_number=lineno,
                key=key,
                looks_like_public_default=value.casefold() in _KNOWN_PUBLIC_DEFAULTS,
            )
        )
        # `value` goes out of scope here and is never carried further.
    return findings


def scan_discovered_files(
    files: Iterable[object],
    *,
    provider: str = "",
) -> CredentialNotice:
    """Scan the files this run is about to index.

    Takes the discovered set rather than walking the repository, because the
    question is not "does this repo contain a secret" — that is
    `/modernize-assess`'s `SECRETS.local.md` step, which owns telling a human
    what to rotate. The question here is narrower: *is this indexing run about
    to store and transmit one*. A credential in a file that `exclude_globs`
    already drops is not this module's business.

    Args:
        files: `SourceFile`-shaped objects with `absolute_path` and
            `relative_path`. Typed loosely so this module does not import the
            indexer's models and create a cycle.
        provider: `manifest.embedding.provider`, to say whether text leaves the
            machine.

    Returns:
        A `CredentialNotice`. Falsy when nothing was found.
    """
    findings: list[CredentialFinding] = []
    scanned = 0
    for f in files:
        path = Path(getattr(f, "absolute_path"))
        if path.suffix.lower() not in SCANNED_SUFFIXES:
            continue
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # An unreadable file is not a finding. Discovery already read this
            # file for its SHA-256, so this is rare, and failing the index run
            # over a warning would be the wrong trade.
            continue
        findings.extend(_scan_properties_text(getattr(f, "relative_path"), text))

    return CredentialNotice(
        findings=tuple(findings),
        files_scanned=scanned,
        transmits_offsite=(provider == "api"),
        provider=provider,
    )


def render_notice(notice: CredentialNotice, *, max_files: int = 10) -> str:
    """The operator-facing warning. Returns '' when there is nothing to say."""
    if not notice:
        return ""

    total = len(notice.findings)
    real = len(notice.likely_real)
    defaults = total - real
    affected = notice.files_affected

    lines: list[str] = [
        "",
        "!! CREDENTIALS IN THE INDEXED SET ------------------------------------",
        "",
        f"{total} credential-shaped key(s) with literal values, in "
        f"{len(affected)} of {notice.files_scanned} scanned .properties file(s).",
    ]
    if defaults:
        lines.append(
            f"{real} look like real secrets; {defaults} match a publicly-documented "
            f"default (changeit and similar) and are probably not."
        )

    lines.append("")
    if notice.transmits_offsite:
        lines += [
            f"This run embeds with provider '{notice.provider}', which sends chunk",
            "text OFF THIS MACHINE to the hosted embedding service. These values",
            "will be transmitted. Switch to a local provider (qwen3, hash) if that",
            "is not acceptable for this estate.",
        ]
    else:
        lines += [
            f"This run embeds with provider '{notice.provider or 'unknown'}', so nothing",
            "leaves the machine. The values are still stored in index.sqlite and",
            "mirrored into FTS5 in plaintext.",
        ]

    lines += ["", "Files (key names only; values are never read out):"]
    for relative_path in affected[:max_files]:
        keys = [f.key for f in notice.findings if f.relative_path == relative_path]
        shown = ", ".join(sorted(set(keys))[:4])
        more = "" if len(set(keys)) <= 4 else f", +{len(set(keys)) - 4} more"
        lines.append(f"  {relative_path} -- {shown}{more}")
    if len(affected) > max_files:
        lines.append(f"  ... and {len(affected) - max_files} more file(s)")

    lines += [
        "",
        "Indexing CONTINUES -- this is a notice, not a gate. Only .properties was",
        "scanned, so a short list is not proof of absence: .xml, .yaml and .json",
        "carry the same shape and are not checked. Rotation and remediation are",
        "/modernize-assess's SECRETS.local.md step, not this command's.",
        "----------------------------------------------------------------------",
        "",
    ]
    return "\n".join(lines)


def log_lines(notice: CredentialNotice) -> Sequence[str]:
    """What goes in `index.log`: counts and paths, never key names or values.

    The log is a file on disk that outlives the run and gets copied around with
    the analysis tree. The console notice names keys because a human is reading
    it once; the log does not, because a durable artifact listing which key in
    which file holds a secret is a map worth stealing.
    """
    if not notice:
        return ()
    return (
        f"[credentials] {len(notice.findings)} credential-shaped key(s) in "
        f"{len(notice.files_affected)} file(s) of {notice.files_scanned} scanned; "
        f"provider={notice.provider or 'unknown'} "
        f"offsite={'yes' if notice.transmits_offsite else 'no'}",
        *(f"[credentials] {p}" for p in notice.files_affected),
    )


__all__ = [
    "CredentialFinding",
    "CredentialNotice",
    "SCANNED_SUFFIXES",
    "log_lines",
    "render_notice",
    "scan_discovered_files",
]
