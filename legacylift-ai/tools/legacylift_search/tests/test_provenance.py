"""Third-party provenance, and the one case that motivated sharing it.

`gaps.walk_repository` and `discover_source_files` must agree about what is
third-party. Before 2026-09-08 only the walk had the concept, which was
harmless while the allow-list named no vendored extension -- and stopped being
harmless the moment `**/*.tld` was added, because NNG's
`WEB-INF/tld/` directory holds nine JSTL/Spring/displaytag/joda/tiles
descriptors and two of the client's own tag libraries, side by side.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from legacylift_search.config import Manifest
from legacylift_search.discovery import (
    build_third_party_classifier,
    discover_source_files,
)
from legacylift_search.linguist import load_linguist_profile
from legacylift_search.provenance import ThirdPartyClassifier, declared_identity

VENDOR_TLD = """<?xml version="1.0" encoding="UTF-8"?>
<taglib>
  <tlib-version>1.1</tlib-version>
  <uri>http://www.springframework.org/tags/form</uri>
</taglib>
"""

CLIENT_TLD = """<?xml version="1.0" encoding="UTF-8"?>
<taglib>
  <tlib-version>1.0</tlib-version>
  <uri>http://www.nngco.com/nngauthz</uri>
</taglib>
"""


@pytest.fixture
def profile():
    return load_linguist_profile()


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_declared_identity_reads_the_uri_element(tmp_path: Path) -> None:
    path = _write(tmp_path, "spring-form.tld", VENDOR_TLD)
    assert declared_identity(path) == "http://www.springframework.org/tags/form"


def test_declared_identity_is_none_when_the_file_states_nothing(tmp_path: Path) -> None:
    path = _write(tmp_path, "plain.tld", "<taglib></taglib>\n")
    assert declared_identity(path) is None


def test_identity_rescues_a_client_file_from_a_vendored_glob(tmp_path, profile) -> None:
    """The whole reason this module exists, reduced to two files.

    Both sit under the same `vendored_globs` pattern. Only the declared `<uri>`
    separates them, and getting it wrong deletes a real access-control tag
    library (`com.nng.ple.web.tags.NngAuthorizeTag`) from the index.
    """
    vendor = _write(tmp_path, "web/WEB-INF/tld/spring-form.tld", VENDOR_TLD)
    client = _write(tmp_path, "web/WEB-INF/tld/nngauthz.tld", CLIENT_TLD)

    classifier = ThirdPartyClassifier(
        profile=profile,
        vendored_globs=["web/WEB-INF/tld/**"],
        own_identities=["nngco.com"],
    )

    verdict, rescued = classifier.classify(
        vendor, "web/WEB-INF/tld/spring-form.tld", ".tld"
    )
    assert verdict is not None
    assert verdict.rule == "declared_identity"
    assert not rescued

    verdict, rescued = classifier.classify(
        client, "web/WEB-INF/tld/nngauthz.tld", ".tld"
    )
    assert verdict is None
    assert rescued, "an own-identity file a vendored glob claimed is a rescue"


def test_identity_drops_a_vendor_file_no_glob_names(tmp_path, profile) -> None:
    """Authoritative in BOTH directions.

    NNG's two `xmlcatalog/spring*.tld` are covered by no `vendored_globs`
    pattern at all; only the declared identity catches them.
    """
    path = _write(tmp_path, "arch/xmlcatalog/spring.tld", VENDOR_TLD)
    classifier = ThirdPartyClassifier(
        profile=profile, vendored_globs=[], own_identities=["nngco.com"]
    )
    verdict, _ = classifier.classify(path, "arch/xmlcatalog/spring.tld", ".tld")
    assert verdict is not None
    assert verdict.rule == "declared_identity"


def test_no_own_identities_skips_the_identity_rule_entirely(tmp_path, profile) -> None:
    """Documented in the plan's Decision Log, and load-bearing.

    Taken literally against an empty token set, "authoritative in both
    directions" makes every file that declares any identity third-party --
    which would silently delete the very file the rule exists to rescue.
    """
    client = _write(tmp_path, "web/WEB-INF/tld/nngauthz.tld", CLIENT_TLD)
    classifier = ThirdPartyClassifier(
        profile=profile, vendored_globs=[], own_identities=[]
    )
    verdict, rescued = classifier.classify(client, "web/WEB-INF/tld/nngauthz.tld", ".tld")
    assert verdict is None
    assert not rescued


def test_vendored_glob_applies_when_no_identity_is_declared(tmp_path, profile) -> None:
    """The third rule, reached only when the first two decline.

    The fixture name is deliberately unremarkable. Naming it `jquery-ui.css`
    makes this pass for the wrong reason: `vendor.yml`'s filename patterns
    claim it first, and the assertion below then reports `vendor_filename`.
    """
    path = _write(tmp_path, "web/theme/colorbox.css", "body{}\n")
    classifier = ThirdPartyClassifier(
        profile=profile, vendored_globs=["web/theme/**"], own_identities=["nngco.com"]
    )
    verdict, _ = classifier.classify(path, "web/theme/colorbox.css", ".css")
    assert verdict is not None
    assert verdict.rule == "vendored_globs"
    assert verdict.detail == "web/theme/**"


def test_vendor_filename_outranks_vendored_globs(tmp_path, profile) -> None:
    """Precedence, pinned. Discovered by the fixture mistake above."""
    path = _write(tmp_path, "web/theme/jquery-ui.css", "body{}\n")
    classifier = ThirdPartyClassifier(
        profile=profile, vendored_globs=["web/theme/**"], own_identities=["nngco.com"]
    )
    verdict, _ = classifier.classify(path, "web/theme/jquery-ui.css", ".css")
    assert verdict is not None
    assert verdict.rule == "vendor_filename"


# ---------------------------------------------------------------------------
# Wiring: the classifier has to actually reach `discover_source_files`
# ---------------------------------------------------------------------------


def _manifest(tmp_path: Path, **project) -> Manifest:
    m = Manifest()
    m.project.include_globs = ["**/*.tld", "**/*.java"]
    m.project.exclude_globs = []
    for key, value in project.items():
        setattr(m.project, key, value)
    return m


def test_discovery_is_unchanged_when_no_domains_file_is_configured(
    tmp_path: Path,
) -> None:
    """The default must be today's behavior, exactly.

    Discovery runs in contexts where the modernization artifacts have not been
    authored yet; it must not start requiring a domains.json.
    """
    _write(tmp_path, "web/WEB-INF/tld/spring-form.tld", VENDOR_TLD)
    _write(tmp_path, "src/Kept.java", "class Kept {}\n")

    found = {sf.relative_path for sf in discover_source_files(tmp_path, _manifest(tmp_path))}
    assert found == {"web/WEB-INF/tld/spring-form.tld", "src/Kept.java"}


def test_discovery_drops_third_party_when_a_domains_file_supplies_provenance(
    tmp_path: Path,
) -> None:
    """End to end: manifest -> domains.json -> classifier -> discovered set."""
    _write(tmp_path, "web/WEB-INF/tld/spring-form.tld", VENDOR_TLD)
    _write(tmp_path, "web/WEB-INF/tld/nngauthz.tld", CLIENT_TLD)
    _write(tmp_path, "src/Kept.java", "class Kept {}\n")
    _write(
        tmp_path,
        "domains.json",
        json.dumps(
            {
                "schema_version": 1,
                "domains": [],
                "vendored_globs": ["web/WEB-INF/tld/**"],
                "own_identities": ["nngco.com"],
            }
        ),
    )

    manifest = _manifest(tmp_path, domains_file="domains.json")
    found = {sf.relative_path for sf in discover_source_files(tmp_path, manifest)}

    assert "web/WEB-INF/tld/spring-form.tld" not in found
    assert "web/WEB-INF/tld/nngauthz.tld" in found, "identity must rescue the client tag lib"
    assert "src/Kept.java" in found


def test_missing_domains_file_is_silent(tmp_path: Path) -> None:
    """Same rationale as `resolve_analysis_dir`: the artifact may not exist yet."""
    manifest = _manifest(tmp_path, domains_file="does-not-exist.json")
    assert build_third_party_classifier(tmp_path, manifest) is None


def test_domains_file_without_provenance_fields_builds_no_classifier(
    tmp_path: Path,
) -> None:
    """A classifier with neither list can only fire `vendor.yml`'s patterns.

    Turning those on for every repository is a behavior change nobody asked
    for -- and it would drop `.gitignore`/`.gitattributes`, which the plan's
    Surprises section records as `vendor.yml`'s one known imprecision.
    """
    _write(tmp_path, "domains.json", json.dumps({"schema_version": 1, "domains": []}))
    manifest = _manifest(tmp_path, domains_file="domains.json")
    assert build_third_party_classifier(tmp_path, manifest) is None
