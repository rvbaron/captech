"""Tests for the shared identity module (Milestone 1, Step 1).

These keys are hashed and corpus-wide: a formula that changes silently
re-keys every anchor in both databases, and a collision silently merges two
signed-off requirements. So the tests here pin the *formula* — pinned golden
digests, the closed `entity_class` set asserted exactly, and the delimiter
collision the U+001F separator exists to prevent — rather than only
exercising the happy path.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

from legacylift_search import identity
from legacylift_search.identity import (
    ENTITY_CLASSES,
    anchor_key,
    content_hash,
    file_anchor_key,
    new_ulid,
    normalize_path,
)

US = "\x1f"


# ---------------------------------------------------------------------------
# The closed entity_class set
# ---------------------------------------------------------------------------


def test_entity_class_set_is_exactly_the_seven_closed_values() -> None:
    """A silent addition or rename must fail the build.

    Changing this set re-keys every `anchor_key` derived from it, which is an
    `ak2:` event (bump the prefix, recompute both databases) and never an
    edit in place. This assertion is what forces that conversation.
    """
    assert ENTITY_CLASSES == frozenset(
        {"type", "function", "field", "table", "column", "file", "other"}
    )
    assert len(ENTITY_CLASSES) == 7


def test_no_entity_class_of_kind_function_is_exported() -> None:
    """The forbidden function must not reappear under its own name.

    `symbols.kind` is not enumerable from this repository — the analyzed
    repository's framework vocabulary authors kinds — so a total mapping
    cannot exist. Only the clearly-named backfill shim survives.
    """
    assert not hasattr(identity, "entity_class_of")
    assert "entity_class_of" not in identity.__all__


# ---------------------------------------------------------------------------
# normalize_path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("src/Acme/Order.cs", "src/Acme/Order.cs"),
        ("src\\Acme\\Order.cs", "src/Acme/Order.cs"),
        ("./src/Acme/Order.cs", "src/Acme/Order.cs"),
        (".\\src\\Acme\\Order.cs", "src/Acme/Order.cs"),
        ("", ""),
        ("Order.cs", "Order.cs"),
    ],
)
def test_normalize_path_separator_styles(raw: str, expected: str) -> None:
    assert normalize_path(raw) == expected


def test_normalize_path_preserves_case() -> None:
    """Case-folding is wrong on case-sensitive filesystems.

    `Foo.java` and `foo.java` are two different files on Linux, which is
    where the analyzed code is authored.
    """
    assert normalize_path("src/Acme/OrderService.cs") == "src/Acme/OrderService.cs"
    assert normalize_path("SRC\\ACME\\ORDERSERVICE.CS") == "SRC/ACME/ORDERSERVICE.CS"
    assert normalize_path("a/B.cs") != normalize_path("A/b.cs")


def test_normalize_path_is_idempotent() -> None:
    for raw in ("./a/b.cs", ".\\a\\b.cs", "././a.cs", "a.cs", ""):
        once = normalize_path(raw)
        assert normalize_path(once) == once


def test_normalize_path_does_not_touch_anything_else() -> None:
    """No slash collapsing, no `..` resolution, no trailing-slash handling.

    Every extra rule is a way for two implementations to disagree, and a
    disagreement here is a silent corpus-wide re-key.
    """
    assert normalize_path("a//b.cs") == "a//b.cs"
    assert normalize_path("a/../b.cs") == "a/../b.cs"
    assert normalize_path("a/b/") == "a/b/"
    assert normalize_path("../a.cs") == "../a.cs"


# ---------------------------------------------------------------------------
# anchor_key: formula, prefix, digest length
# ---------------------------------------------------------------------------


def test_anchor_key_prefix_and_digest_length() -> None:
    """`ak1:` + 16 hex characters, deliberately 16 and not 12.

    48 bits at 100,000 entities is roughly a one-in-55,000 collision chance;
    64 bits puts it near three in ten billion.
    """
    key = anchor_key("java", "type", "com.acme.Order", "src/com/acme/Order.java")
    assert key.startswith("ak1:")
    digest = key[len("ak1:") :]
    assert len(digest) == 16
    assert all(c in "0123456789abcdef" for c in digest)
    assert len(key) == 20


def test_anchor_key_matches_the_specified_formula_exactly() -> None:
    """Recompute the spec formula independently and compare."""
    language, entity_class = "csharp", "function"
    qualified = "Acme.Orders.OrderService.Recalculate"
    path = "src/Acme/Orders/OrderService.cs"
    payload = US.join((language, entity_class, qualified, normalize_path(path)))
    expected = "ak1:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    assert anchor_key(language, entity_class, qualified, path) == expected


def test_anchor_key_golden_values_are_pinned() -> None:
    """Pin the formula against silent drift.

    If this fails, the key formula changed. That is an `ak2:` event — a new
    prefix and a recomputation of every anchor in both databases — not a
    test to update.
    """
    assert (
        anchor_key(
            "csharp",
            "function",
            "Acme.Orders.OrderService.Recalculate",
            "src/Acme/Orders/OrderService.cs",
        )
        == "ak1:386ea9fbeaa13aa9"
    )
    assert file_anchor_key("src/Acme/Orders/OrderService.cs") == "ak1:9bc3cea1d6f6034b"
    assert content_hash("def f():\n    return 1\n") == "ch1:8795b1c438f59538"


# ---------------------------------------------------------------------------
# anchor_key: the delimiter collision
# ---------------------------------------------------------------------------


def test_colon_delimiter_would_collide_but_unit_separator_does_not() -> None:
    """The reason the delimiter is U+001F and not `:`.

    Both `qualified_name` and `relative_path` contain colons, dots and
    slashes, so under a `:` join the field boundary is ambiguous: `"a:b"` +
    `"c"` and `"a"` + `"b:c"` produce identical bytes. These are two
    genuinely different entities and they must not share an anchor.
    """
    left = ("java", "type", "com.acme:Order", "src/Order.java")
    right = ("java", "type", "com.acme", "Order:src/Order.java")

    # Demonstrate the defect being avoided: a `:` join collapses the pair.
    assert ":".join(left) == ":".join(right)

    # And the shipped formula keeps them apart.
    assert anchor_key(*left) != anchor_key(*right)


def test_unit_separator_in_an_input_is_rejected_rather_than_hashed() -> None:
    """The injectivity argument rests on U+001F never occurring in an input.

    Accepting it silently would reintroduce the very ambiguity the delimiter
    choice exists to remove, so it fails loudly instead.
    """
    with pytest.raises(ValueError, match="U\\+001F"):
        anchor_key("java", "type", f"com.acme{US}Order", "src/Order.java")
    with pytest.raises(ValueError, match="U\\+001F"):
        anchor_key("java", "type", "com.acme.Order", f"src{US}Order.java")


# ---------------------------------------------------------------------------
# anchor_key: inputs it takes, and inputs it refuses
# ---------------------------------------------------------------------------


def test_anchor_key_takes_the_coarse_class_and_discriminates_on_it() -> None:
    """The hash takes `entity_class`, never the fine-grained `kind`.

    `SecUser.StatusEnum` appears in the NNG corpus as both an
    `enum_declaration` and a `field_declaration`; the coarse class is what
    keeps those two entities apart without churning when an extractor is
    tuned.
    """
    as_type = anchor_key("csharp", "type", "Acme.SecUser.StatusEnum", "src/SecUser.cs")
    as_field = anchor_key(
        "csharp", "field", "Acme.SecUser.StatusEnum", "src/SecUser.cs"
    )
    assert as_type != as_field


def test_anchor_key_rejects_a_class_outside_the_closed_set() -> None:
    """A fine-grained `kind` reaching this argument is the failure to catch."""
    with pytest.raises(ValueError, match="closed"):
        anchor_key("csharp", "enum_declaration", "Acme.Order", "src/Order.cs")
    with pytest.raises(ValueError, match="closed"):
        anchor_key("csharp", "", "Acme.Order", "src/Order.cs")


def test_anchor_key_normalizes_separators_but_not_case() -> None:
    windows = anchor_key("csharp", "type", "Acme.Order", "src\\Acme\\Order.cs")
    posix = anchor_key("csharp", "type", "Acme.Order", "src/Acme/Order.cs")
    dotted = anchor_key("csharp", "type", "Acme.Order", "./src/Acme/Order.cs")
    assert windows == posix == dotted

    upper = anchor_key("csharp", "type", "Acme.Order", "SRC/ACME/ORDER.CS")
    assert upper != posix


def test_anchor_key_excludes_line_numbers_and_body() -> None:
    """The signature is the assertion: there is nowhere to pass either.

    `anchor_key` must be stable across edits above a symbol, which is the
    whole reason it exists beside the line-embedding `symbols.id`.
    """
    params = list(inspect.signature(anchor_key).parameters)
    assert params == ["language", "entity_class", "qualified_name", "relative_path"]


def test_no_key_takes_a_domain_as_an_input() -> None:
    """Hard invariant: domain is never an input to any key defined here.

    A domain is a retaggable, human-authored judgement. If it fed a key, a
    retag would re-key every requirement citing the retagged file, and the
    merge would stop matching with nothing raised anywhere.
    """
    for func in (normalize_path, anchor_key, file_anchor_key, content_hash, new_ulid):
        params = inspect.signature(func).parameters
        assert not any("domain" in name.lower() for name in params), func.__name__


# ---------------------------------------------------------------------------
# file_anchor_key — the file grain
# ---------------------------------------------------------------------------


def test_file_anchor_key_is_the_specified_constant_tuple() -> None:
    """`file_anchor_key(p) == anchor_key("", "file", "", p)` (§S3.1.1)."""
    path = "config/hibernate.cfg.xml"
    assert file_anchor_key(path) == anchor_key("", "file", "", path)


def test_file_anchor_key_takes_no_language_argument() -> None:
    """A `language` parameter would invite the lookup §S3.1.1 forbids.

    `repo_files.language` exists only for files the indexer accepted, so a
    lookup would make a tier-1 `dedupe_key` input a function of whether an
    `index` run had happened. A constant cannot churn.
    """
    assert list(inspect.signature(file_anchor_key).parameters) == ["relative_path"]


def test_file_anchor_key_stable_across_separator_styles() -> None:
    posix = file_anchor_key("web/WEB-INF/flows/order-flow.xml")
    windows = file_anchor_key("web\\WEB-INF\\flows\\order-flow.xml")
    dotted = file_anchor_key("./web/WEB-INF/flows/order-flow.xml")
    assert posix == windows == dotted


def test_file_anchor_key_differs_from_a_symbol_anchor_on_the_same_path() -> None:
    path = "src/Acme/Order.cs"
    assert file_anchor_key(path) != anchor_key("csharp", "type", "Acme.Order", path)
    # And from an `other`-class symbol with an empty name on the same path,
    # so the discrimination is the class rather than an accident of naming.
    assert file_anchor_key(path) != anchor_key("", "other", "", path)


def test_file_anchor_key_ignores_the_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Computed identically whether or not the path exists on disk.

    An `unresolved` citation names a path that is not in the working tree at
    all, and it must key the same as a resolved one.
    """
    relative = "src/Acme/Order.cs"
    present = tmp_path / "present"
    (present / "src" / "Acme").mkdir(parents=True)
    (present / relative).write_text("class Order {}\n", encoding="utf-8")
    absent = tmp_path / "absent"
    absent.mkdir()

    monkeypatch.chdir(present)
    assert (present / relative).exists()
    with_file = file_anchor_key(relative)

    monkeypatch.chdir(absent)
    assert not (absent / relative).exists()
    without_file = file_anchor_key(relative)

    assert with_file == without_file


def test_file_anchor_key_discriminates_by_path() -> None:
    assert file_anchor_key("a/Order.cs") != file_anchor_key("b/Order.cs")


# ---------------------------------------------------------------------------
# content_hash
# ---------------------------------------------------------------------------


def test_content_hash_prefix_and_digest_length() -> None:
    value = content_hash("int x = 1;")
    assert value.startswith("ch1:")
    digest = value[len("ch1:") :]
    assert len(digest) == 16
    assert all(c in "0123456789abcdef" for c in digest)
    assert len(value) == 20


def test_content_hash_stable_across_line_endings() -> None:
    lf = content_hash("line one\nline two\nline three\n")
    crlf = content_hash("line one\r\nline two\r\nline three\r\n")
    cr = content_hash("line one\rline two\rline three\r")
    assert lf == crlf == cr


def test_content_hash_stable_under_trailing_whitespace() -> None:
    clean = content_hash("if (a) {\n    b();\n}")
    trailing = content_hash("if (a) {   \n    b();\t\n}  ")
    assert clean == trailing


def test_content_hash_stable_under_leading_and_trailing_blank_lines() -> None:
    bare = content_hash("return 1;")
    padded = content_hash("\n\n   \nreturn 1;\n\n\t\n")
    assert bare == padded


def test_content_hash_sensitive_to_interior_blank_lines() -> None:
    """Only *leading and trailing* blank lines are dropped.

    An interior blank line is part of the body; removing it is an edit.
    """
    assert content_hash("a;\n\nb;") != content_hash("a;\nb;")


def test_content_hash_changes_when_a_comment_changes() -> None:
    """Comments are KEPT — a rule may be cited *to* a comment.

    So a comment change is real drift and must re-verify the requirement,
    not be normalized away.
    """
    before = content_hash("// vendor number is mandatory\nrequire(vendor);")
    after = content_hash("// vendor number is optional\nrequire(vendor);")
    assert before != after

    # Removing the comment entirely is likewise a change.
    assert content_hash("require(vendor);") != before


def test_content_hash_changes_when_leading_indentation_changes() -> None:
    """Only *trailing* whitespace is stripped; indentation is code."""
    assert content_hash("if x:\n    return 1") != content_hash("if x:\n  return 1")


def test_content_hash_excludes_path_name_language_and_lines() -> None:
    """The signature is the assertion: body text is the only input.

    That exclusion is what makes the `anchor_key`/`content_hash` pair
    jointly informative — one includes the path and excludes the body, the
    other does the reverse — so a move is distinguishable from a clone.
    """
    assert list(inspect.signature(content_hash).parameters) == ["body_text"]


def test_content_hash_identifies_a_clone_across_files() -> None:
    """Two byte-identical bodies in different files share a content hash and
    differ in anchor: the "clone or move" quadrant of the §S3.2 matrix."""
    body = "public int Total() { return a + b; }"
    assert content_hash(body) == content_hash(body)
    assert anchor_key("csharp", "function", "A.Total", "src/A.cs") != anchor_key(
        "csharp", "function", "B.Total", "src/B.cs"
    )


# ---------------------------------------------------------------------------
# new_ulid
# ---------------------------------------------------------------------------

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def test_new_ulid_shape_and_prefix() -> None:
    """`"GR-" + ULID` is twenty-nine characters."""
    value = new_ulid("GR-")
    assert value.startswith("GR-")
    assert len(value) == 29
    assert len(value[len("GR-") :]) == 26

    run = new_ulid("RUN-")
    assert run.startswith("RUN-")
    assert len(run) == 30


def test_new_ulid_uses_the_crockford_alphabet() -> None:
    """`I`, `L`, `O` and `U` are omitted so a transcription cannot confuse them."""
    for excluded in "ILOU":
        assert excluded not in _CROCKFORD
    for _ in range(200):
        body = new_ulid("GR-")[len("GR-") :]
        assert all(c in _CROCKFORD for c in body), body


def test_new_ulid_sorts_in_generation_order() -> None:
    """Lexicographic sort must equal creation order, including within a
    single millisecond — the export sorts by `gr_id` and a reviewer expects
    creation order without joining to a timestamp column."""
    minted = [new_ulid("GR-") for _ in range(1000)]
    assert minted == sorted(minted)
    assert all(a < b for a, b in zip(minted, minted[1:]))


def test_new_ulid_is_unique_over_ten_thousand() -> None:
    minted = [new_ulid("GR-") for _ in range(10_000)]
    assert len(set(minted)) == 10_000


def test_new_ulid_prefixes_do_not_collide() -> None:
    """A run identifier must never be mistaken for a requirement identifier."""
    assert not new_ulid("RUN-").startswith("GR-")
    assert not new_ulid("GR-").startswith("RUN-")


def test_new_ulid_is_not_content_derived() -> None:
    """`gr_id` is a surrogate on purpose: two calls with the same prefix
    differ, so approving a human's edit can never mint a new requirement."""
    assert new_ulid("GR-") != new_ulid("GR-")
