"""Tests for discovery.py (Milestone 3)."""

from pathlib import Path

import pytest

from legacylift_search.discovery import discover_source_files
from legacylift_search.languages import detect_language, get_language


# Minimal mock manifest for testing discovery.
class MockProjectConfig:
    """Mock project config for testing."""

    def __init__(self):
        self.include_globs = [
            "**/*.cs",
            "**/*.java",
            "**/*.py",
            "**/*.js",
            "**/*.jsx",
            "**/*.mjs",
            "**/*.cjs",
            "**/*.ts",
            "**/*.tsx",
            "**/*.cbl",
            "**/*.cob",
            "**/*.cpy",
            "**/*.copy",
            "**/*.pco",
            "**/*.sql",
            "**/*.ddl",
            "**/*.dml",
            "**/*.psql",
            "**/*.pgsql",
            "**/*.tsql",
        ]
        self.exclude_globs = [
            "**/.git/**",
            "**/node_modules/**",
            "**/bin/**",
            "**/obj/**",
            "**/dist/**",
            "**/build/**",
            "**/__pycache__/**",
        ]
        self.max_file_bytes = 2000000


class MockManifest:
    """Mock manifest for testing."""

    def __init__(self):
        self.project = MockProjectConfig()


def test_detect_language():
    """Test language detection from file extensions."""
    # Test recognized languages
    assert detect_language(Path("Demo.cs")).key == "csharp"
    assert detect_language(Path("Demo.java")).key == "java"
    assert detect_language(Path("eligibility.py")).key == "python"
    assert detect_language(Path("reclaim.js")).key == "javascript"
    assert detect_language(Path("enrollment.ts")).key == "typescript"
    assert detect_language(Path("PROVIDER.cbl")).key == "cobol"
    assert detect_language(Path("schema.sql")).key == "sql"

    # Test unrecognized extension
    assert detect_language(Path("README.md")) is None
    assert detect_language(Path("file_without_ext")) is None


def test_get_language():
    """Test language retrieval by key."""
    csharp = get_language("csharp")
    assert csharp.key == "csharp"
    assert csharp.display_name == "C#"
    assert ".cs" in csharp.extensions
    assert csharp.supports_tree_sitter is True

    cobol = get_language("cobol")
    assert cobol.key == "cobol"
    assert cobol.supports_tree_sitter is False

    # Test KeyError for unknown language
    with pytest.raises(KeyError):
        get_language("unknown_language")


def test_discover_source_files():
    """Test discovery of source files in the polyglot fixture repo."""
    # Get the fixture repo path relative to this test file.
    test_dir = Path(__file__).parent
    fixture_repo = test_dir / "fixtures" / "polyglot_repo"

    # Skip test if fixture doesn't exist (shouldn't happen after creation).
    if not fixture_repo.exists():
        pytest.skip("Fixture polyglot_repo not found")

    manifest = MockManifest()
    discovered = discover_source_files(fixture_repo, manifest)

    # Check that we found exactly 18 valid source files (7 original + 4 added
    # for the Milestone 22 type-hierarchy fixtures under hierarchy/ + 4 added
    # for the Milestone 23 annotation fixtures under annotations/ + 3 added for
    # the SQL bracket/temp-table/SSMS-export fixtures under database/).
    assert len(discovered) == 18, f"Expected 18 files, found {len(discovered)}"

    # Check that each expected file is present.
    relative_paths = {sf.relative_path for sf in discovered}
    expected = {
        "src/Demo.cs",
        "src/Demo.java",
        "src/eligibility.py",
        "src/enrollment.ts",
        "src/reclaim.js",
        "mainframe/PROVIDER.cbl",
        "database/schema.sql",
        # Milestone 22 type-hierarchy fixtures.
        "hierarchy/Shapes.cs",
        "hierarchy/Shapes.java",
        "hierarchy/shapes.py",
        "hierarchy/shapes.ts",
        # Milestone 23 annotation fixtures.
        "annotations/OrdersController.cs",
        "annotations/OrderApi.java",
        "annotations/routes.py",
        "annotations/orders.controller.ts",
        # SQL bracket-quoting / temp-table fixtures (sql-extractor-temp-cte-fk).
        "database/tsql_bracketed.sql",
        "database/tsql_bracketed_multi.sql",
        "database/tsql_ssms_scripted.sql",
    }
    assert relative_paths == expected

    # Verify that excluded files are not present.
    for sf in discovered:
        assert "node_modules" not in sf.relative_path
        assert "dist" not in sf.relative_path


def test_discover_source_files_metadata():
    """Test that discovered source files have correct metadata."""
    test_dir = Path(__file__).parent
    fixture_repo = test_dir / "fixtures" / "polyglot_repo"

    if not fixture_repo.exists():
        pytest.skip("Fixture polyglot_repo not found")

    manifest = MockManifest()
    discovered = discover_source_files(fixture_repo, manifest)

    # Check that each file has required fields populated.
    for sf in discovered:
        assert sf.absolute_path.exists()
        assert sf.repo_root == fixture_repo.resolve()
        assert sf.relative_path
        assert sf.language in ["csharp", "java", "python", "javascript", "typescript", "cobol", "sql"]
        assert sf.size_bytes > 0
        assert len(sf.sha256) == 64  # SHA-256 hex digest length
        assert sf.mtime_ns > 0
