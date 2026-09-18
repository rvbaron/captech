"""The repository's licence texts exist in more than one place. Pin them.

Three separate files restate the same legal text, each for a reason that is
sound on its own:

- `LICENSE.md` is duplicated into `.claude/skills/code-modernization/` because
  that directory is DISTRIBUTED STANDALONE -- the plugin's README tells people
  to copy it into a client workspace -- and the terms covering CapTech's
  modifications have to travel with it. A pointer would arrive dangling.
- `NOTICE` is reproduced as Exhibit B inside `LICENSE.md` so that the licence is
  self-contained, while `NOTICE` remains the canonical file Apache 2.0 §4(d)
  expects. Exhibit B says as much, and says NOTICE governs if they differ.

Duplicated legal text that nothing checks is text that silently diverges, and
the failure is invisible until someone reads the wrong copy in a client
workspace. These tests are the check. They live in this suite for the dull
reason that it is the only one CI runs.

They assert nothing about what the licence SAYS -- that is not a test's
business. Only that the copies agree, and that the one file which must stay
pristine has not been edited.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# tests/ -> legacylift_search/ -> tools/ -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = REPO_ROOT / ".claude" / "skills" / "code-modernization"

ROOT_LICENSE = REPO_ROOT / "LICENSE.md"
PLUGIN_LICENSE_MD = PLUGIN_DIR / "LICENSE.md"
PLUGIN_LICENSE_APACHE = PLUGIN_DIR / "LICENSE"
NOTICE = REPO_ROOT / "NOTICE"

# The package is installed with `pip install -e`, so the checkout is normally
# right there -- but skip rather than fail if these tests are ever run from a
# built wheel, where the repository is not on disk at all.
pytestmark = pytest.mark.skipif(
    not ROOT_LICENSE.is_file(),
    reason="not running from a source checkout; repository licence files absent",
)


def _read(path: Path) -> str:
    """Read as text, normalising line endings.

    `.gitattributes` may check these files out CRLF on Windows and LF on Linux,
    so a byte comparison would fail on one platform and pass on the other --
    which is the exact class of defect the first CI run already caught once.
    """
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_the_plugins_captech_licence_matches_the_root_one():
    """The distributed copy must not drift from the source of truth."""
    assert PLUGIN_LICENSE_MD.is_file(), (
        f"{PLUGIN_LICENSE_MD.relative_to(REPO_ROOT)} is missing. The plugin "
        "directory is distributed standalone, so CapTech's terms must travel "
        "with it; copy LICENSE.md from the repository root."
    )
    assert _read(PLUGIN_LICENSE_MD) == _read(ROOT_LICENSE), (
        "The CapTech licence in the code-modernization plugin has drifted from "
        "the one at the repository root. The root file is the source of truth: "
        "copy it over the plugin's, in the same commit as whatever changed it."
    )


def test_the_plugins_apache_licence_is_pristine_upstream():
    """`LICENSE` is the §4(a) copy handed to anyone who receives the plugin.

    It is Anthropic's, and editing it breaks the one job it has. CapTech's terms
    belong in the `LICENSE.md` beside it -- which is why both files exist.
    """
    text = _read(PLUGIN_LICENSE_APACHE)

    assert text.lstrip().startswith("Apache License"), (
        "The plugin's LICENSE no longer begins with the Apache License. It must "
        "stay the pristine upstream text -- put CapTech terms in LICENSE.md."
    )
    assert "CapTech" not in text, (
        "The plugin's LICENSE mentions CapTech. It is the verbatim copy of the "
        "Apache License that §4(a) obliges us to give recipients; CapTech's "
        "terms go in the LICENSE.md beside it, never into this file."
    )
    # §4(b)/(c)/(d) are what the attribution convention rests on; a truncated
    # copy would still start with "Apache License" and pass the check above.
    assert "END OF TERMS AND CONDITIONS" in text, "Apache text is truncated."


def test_notice_matches_exhibit_b_of_the_licence():
    """Exhibit B is a verbatim copy of NOTICE, and claims to be."""
    assert NOTICE.is_file(), "NOTICE is missing from the repository root."

    licence = _read(ROOT_LICENSE)
    banner = "=" * 80

    _, after_heading = licence.split("EXHIBIT B — NOTICE (ATTRIBUTION)", 1)
    # The heading block is closed by a banner line; the Exhibit body follows it.
    exhibit_b = after_heading.split(banner + "\n", 1)[1]

    assert exhibit_b.strip() == _read(NOTICE).strip(), (
        "NOTICE and Exhibit B of LICENSE.md have diverged. NOTICE is canonical "
        "(Exhibit B says so); correct the Exhibit to match it."
    )


def test_the_licence_still_carves_out_the_third_party_components():
    """A guard on the structure the other files depend on, not on the wording.

    `NOTICE`, the plugin's `LICENSE.md` and `.claude-plugin/.upstream` all point
    at Section 9 by name. If a future edit renumbers or removes it, those
    references dangle silently -- and Section 9 is the clause that keeps the
    proprietary header from reading as a claim over Anthropic's code.
    """
    licence = _read(ROOT_LICENSE)

    assert "9. THIRD-PARTY AND OPEN SOURCE COMPONENTS" in licence
    assert "EXHIBIT A — APACHE LICENSE, VERSION 2.0" in licence
    assert "EXHIBIT B — NOTICE (ATTRIBUTION)" in licence
    # The header's proprietary claim must keep its exception; without it the
    # file asserts ownership of the vendored plugin it sits next to.
    assert "except for the\nThird-Party Open Source Components identified in Section 9" in licence


def test_every_licence_file_ends_with_a_newline():
    """POSIX text files end in a newline; diffs and `cat` misbehave otherwise."""
    for path in (ROOT_LICENSE, PLUGIN_LICENSE_MD, PLUGIN_LICENSE_APACHE, NOTICE):
        assert path.read_bytes().endswith(b"\n"), (
            f"{path.relative_to(REPO_ROOT)} does not end with a newline."
        )
