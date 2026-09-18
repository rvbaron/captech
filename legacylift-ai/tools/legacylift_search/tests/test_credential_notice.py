"""The indexer's credential notice.

The behaviour under test is a warning, so the assertions that matter are about
what it does NOT do: it never excludes a file, and it never carries a value.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from legacylift_search.credential_notice import (
    CredentialNotice,
    log_lines,
    render_notice,
    scan_discovered_files,
)


@dataclass
class _File:
    """The `SourceFile` shape the scanner actually uses (duck-typed)."""

    absolute_path: Path
    relative_path: str


def _write(tmp_path: Path, relative_path: str, text: str) -> _File:
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return _File(absolute_path=path, relative_path=relative_path)


# The shape the NNG measurement found, condensed: a real Spring Cloud config
# password, the Java keystore default, an unresolved interpolation, a commented
# line, and an already-encrypted value.
NNG_SHAPED = """\
# application-prod1.properties
spring.application.name=nng-app
spring.cloud.config.password=k3Y8vQ2mNp4rT7wXz1aB5cD9e
server.ssl.key-store-password=changeit
hazelcast.group.password=s3cr3tGr0up
datasource.password=${DB_PASSWORD}
#spring.cloud.config.password=old-value-in-a-comment
jasypt.encryptor.password=ENC(A1B2C3D4E5F6)
server.port=8443
"""


def test_finds_literal_credentials_and_skips_the_four_non_secrets(tmp_path):
    """Three findings, and each exclusion is for its own stated reason."""
    f = _write(tmp_path, "config/application-prod1.properties", NNG_SHAPED)

    notice = scan_discovered_files([f], provider="hash")

    keys = sorted(x.key for x in notice.findings)
    assert keys == [
        "hazelcast.group.password",
        "server.ssl.key-store-password",
        "spring.cloud.config.password",
    ]
    # Excluded: `${DB_PASSWORD}` (interpolation), the `#` comment (even though
    # it holds a credential-shaped key), `ENC(...)` (already encrypted), and
    # `server.port` / `spring.application.name` (key does not match).
    assert notice.files_scanned == 1
    assert notice.files_affected == ("config/application-prod1.properties",)


def test_public_defaults_are_reported_but_counted_apart(tmp_path):
    """`changeit` is public knowledge; conflating it with a real secret is what
    trains a reader to ignore the whole notice."""
    f = _write(tmp_path, "app.properties", NNG_SHAPED)

    notice = scan_discovered_files([f], provider="hash")

    by_key = {x.key: x for x in notice.findings}
    assert by_key["server.ssl.key-store-password"].looks_like_public_default is True
    assert by_key["spring.cloud.config.password"].looks_like_public_default is False
    assert len(notice.likely_real) == 2


def test_no_value_ever_leaves_the_module(tmp_path):
    """The whole point. A finding names a place, never a secret."""
    secret = "k3Y8vQ2mNp4rT7wXz1aB5cD9e"
    f = _write(tmp_path, "app.properties", NNG_SHAPED)

    notice = scan_discovered_files([f], provider="api")

    # Not on the dataclass...
    assert not any(secret in repr(x) for x in notice.findings)
    assert secret not in repr(notice)
    # ...not in the console notice...
    assert secret not in render_notice(notice)
    # ...and not in the log, which additionally must not name the KEYS, because
    # it is a durable file that travels with the analysis tree.
    logged = "\n".join(log_lines(notice))
    assert secret not in logged
    assert "spring.cloud.config.password" not in logged
    assert "app.properties" in logged


def test_hosted_provider_says_the_values_are_transmitted(tmp_path):
    """provider='api' is the case that turns local storage into disclosure."""
    f = _write(tmp_path, "app.properties", NNG_SHAPED)

    hosted = render_notice(scan_discovered_files([f], provider="api"))
    local = render_notice(scan_discovered_files([f], provider="qwen3"))

    assert "OFF THIS MACHINE" in hosted
    assert "OFF THIS MACHINE" not in local
    assert "nothing" in local and "leaves the machine" in local


def test_notice_states_its_own_scope_so_silence_is_not_read_as_proof(tmp_path):
    """Only `.properties` is scanned. A notice that hid that would let a clean
    run on an XML-configured estate read as an all-clear."""
    f = _write(tmp_path, "app.properties", NNG_SHAPED)

    text = render_notice(scan_discovered_files([f], provider="api"))

    assert "not proof of absence" in text
    assert ".xml" in text
    assert "not a gate" in text


def test_non_properties_files_are_not_scanned(tmp_path):
    """Scope is by suffix, and `.xml` is explicitly out for now."""
    xml = _write(
        tmp_path,
        "beans.xml",
        '<bean><property name="password" value="s3cr3t"/></bean>',
    )
    java = _write(tmp_path, "Main.java", 'String password = "s3cr3t";')

    notice = scan_discovered_files([xml, java], provider="api")

    assert notice.files_scanned == 0
    assert not notice


def test_empty_notice_is_falsy_and_renders_nothing():
    """No findings must produce no output at all -- not a reassuring banner.

    A 'no credentials found' message would be a claim this module cannot make:
    it reads one file format with a key-name heuristic.
    """
    notice = CredentialNotice(files_scanned=12, provider="api")

    assert not notice
    assert render_notice(notice) == ""
    assert tuple(log_lines(notice)) == ()


def test_unreadable_file_is_skipped_not_fatal(tmp_path):
    """A warning must never be able to fail the index run."""
    missing = _File(
        absolute_path=tmp_path / "gone.properties", relative_path="gone.properties"
    )
    present = _write(tmp_path, "app.properties", NNG_SHAPED)

    notice = scan_discovered_files([missing, present], provider="hash")

    assert notice.files_affected == ("app.properties",)


def test_colon_separator_and_whitespace_are_handled(tmp_path):
    """`.properties` accepts `:` as well as `=`."""
    f = _write(
        tmp_path,
        "app.properties",
        "  api.token :  abc123XYZ  \nother.setting = 5\n",
    )

    notice = scan_discovered_files([f], provider="hash")

    assert [x.key for x in notice.findings] == ["api.token"]
    assert notice.findings[0].line_number == 1
