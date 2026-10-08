"""Hermetic tests for the two doc-audit tools (no network, no git).

`scripts/validate_registers.py` and `scripts/url_probe.py` are the diff-scoped
doc audits: a register/citation validator and an SSRF-safe link prober. Both do
their real work off injected resolvers/fetchers here, so nothing touches the
network and the SSRF gate is proven rather than assumed.
"""

from __future__ import annotations

import pytest

from scripts import url_probe, validate_registers as vr

pytestmark = pytest.mark.timeout(120)


# --------------------------------------------------------------------------- #
# validate_registers
# --------------------------------------------------------------------------- #
def test_register_blocks_join_wrapped_rows():
    lines = [
        "# register",
        "- [ ] row one `[verified]`",
        "  wrapped with the marker on line two `[reported]`",
        "- [x] a done row that is exempt",
        "- [ ] bare open row",
    ]
    blocks = vr.register_blocks(lines)
    assert [start for start, _ in blocks] == [2, 5]
    text = "\n".join(t for _, t in blocks)
    assert "[reported]" in text


def test_open_row_without_a_marker_is_a_finding(tmp_path):
    doc = tmp_path / "FINDINGS.md"
    doc.write_text(
        "# register\n"
        "- [ ] marked `[verified]`\n"
        "- [ ] marked by brief number `[21]`\n"
        "- [ ] this one says nothing about its provenance\n"
        "- [x] a done row is exempt\n",
        encoding="utf-8",
    )
    found = vr.register_findings(doc)
    assert [f.kind for f in found] == ["unmarked-row"]
    assert found[0].line == 4
    assert "no [verified]" in found[0].message


def test_a_unique_bare_basename_resolves_but_a_sibling_one_does_not():
    index = vr._index()
    path, ambiguous = vr.resolve("sec_edgar.py", index, set())
    assert path is not None and not ambiguous
    assert path.name == "sec_edgar.py"
    # `main.py` exists in a sibling repo too, so a bare citation is not checkable.
    path, ambiguous = vr.resolve("main.py", index, {"main.py"})
    assert path is None and ambiguous


def test_path_qualified_resolves_under_the_package_root_and_external_is_ignored():
    index = vr._index()
    p, ambiguous = vr.resolve("dataflows/sec_edgar.py", index, set())
    assert p is not None and p.name == "sec_edgar.py"
    p, ambiguous = vr.resolve("backend/capabilities.py", index, set())
    assert p is None and not ambiguous  # a sibling repo's path, not ours


def test_citation_past_eof_is_flagged_and_in_range_is_not(tmp_path):
    index = vr._index()
    target = vr.REPO / "tradingagents" / "llm_clients" / "capabilities.py"
    total = len(target.read_text(encoding="utf-8").splitlines())
    doc = tmp_path / "prose.md"
    doc.write_text(
        f"in range: `tradingagents/llm_clients/capabilities.py:{total}`\n"
        f"past eof: `tradingagents/llm_clients/capabilities.py:{total + 500}`\n"
        "external: `yfinance/base.py:99999`\n",
        encoding="utf-8",
    )
    found = vr.citation_findings(doc, index, set())
    assert [f.kind for f in found] == ["citation-out-of-range"]
    assert f":{total + 500}`" in found[0].message


def test_is_error_only_on_a_line_the_diff_added():
    finding = vr.Finding("unmarked-row", vr.REPO / "x.md", 7, "m")
    assert vr.is_error(finding, None) is False
    assert vr.is_error(finding, {"x.md": {7}}) is True
    assert vr.is_error(finding, {"x.md": {1, 2}}) is False


# --------------------------------------------------------------------------- #
# url_probe
# --------------------------------------------------------------------------- #
def test_is_public_refuses_every_non_global_range():
    assert url_probe.is_public("93.184.216.34") is True
    for addr in ("127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1", "not-an-ip"):
        assert url_probe.is_public(addr) is False


def test_classify_status_is_a_closed_set():
    assert url_probe.classify_status(200) == "ok"
    assert url_probe.classify_status(301) == "permanent_redirect"
    assert url_probe.classify_status(302) == "redirect"
    assert url_probe.classify_status(403) == "restricted"
    assert url_probe.classify_status(404) == "dead"
    assert url_probe.classify_status(429) == "transient"
    assert url_probe.classify_status(503) == "transient"
    assert url_probe.classify_status(418) == "http_error"


def test_extract_urls_trims_punctuation_and_dedupes():
    text = "see https://a.example/x, and https://a.example/x and https://b.example/y)."
    assert url_probe.extract_urls(text) == ["https://a.example/x", "https://b.example/y"]


def _resolver(addr: str):
    def _r(host, port, type=None):  # noqa: A002 - mirrors socket.getaddrinfo
        return [(2, 1, 6, "", (addr, port))]

    return _r


def test_probe_refuses_a_non_global_host_without_fetching():
    calls = []

    def fetch(*a):  # pragma: no cover - must not run
        calls.append(a)
        return b""

    r = url_probe.probe(
        "http://169.254.169.254/latest/", resolver=_resolver("169.254.169.254"), fetch=fetch
    )
    assert r.outcome == "refused" and "non-global" in r.detail
    assert calls == []


def test_probe_follows_a_redirect_into_a_private_host_and_refuses_it():
    def fetch(host, addr, port, tls, path, timeout, method):
        return b"HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1/secret\r\n\r\n"

    def resolver(host, port, type=None):  # noqa: A002
        addr = "93.184.216.34" if host == "public.example" else "127.0.0.1"
        return [(2, 1, 6, "", (addr, port))]

    r = url_probe.probe("http://public.example/", resolver=resolver, fetch=fetch)
    assert r.outcome == "refused" and r.url == "http://public.example/"


def test_probe_reports_ok_and_falls_back_to_get_on_404():
    def fetch(host, addr, port, tls, path, timeout, method):
        if method == "HEAD":
            return b"HTTP/1.1 404 Not Found\r\n\r\n"
        return b"HTTP/1.1 200 OK\r\n\r\n"

    r = url_probe.probe("http://good.example/x", resolver=_resolver("93.184.216.34"), fetch=fetch)
    assert r.outcome == "ok" and r.status == 200


def test_probe_reports_transient_after_the_last_retry():
    def fetch(host, addr, port, tls, path, timeout, method):
        raise TimeoutError("slow")

    r = url_probe.probe(
        "http://slow.example/", retries=0, resolver=_resolver("93.184.216.34"), fetch=fetch
    )
    assert r.outcome == "transient"


def test_a_documented_non_browsable_url_is_allowed_not_dead():
    for url in url_probe._NON_BROWSABLE:
        r = url_probe.probe(url, resolver=_resolver("93.184.216.34"))
        assert r.outcome == "allowed"
