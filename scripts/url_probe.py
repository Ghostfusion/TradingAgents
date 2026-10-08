"""SSRF-safe URL prober for the docs' external links (advisory; never edits).

The docs cite vendors, licences and papers by URL, and a dead or moved link is
invisible until someone follows it.  This walks a curated doc set, extracts the
http(s) links, and probes each one - safely.

**Safe means SSRF-resistant.**  A URL from a document is untrusted input: it can
point at `169.254.169.254`, `127.0.0.1`, a private RFC1918 address, or a host
whose DNS answer changes between the check and the connect.  So the host is
resolved once, the resolved address is refused unless `ipaddress.is_global`, and
the connection is made to **that pinned address** while the TLS SNI and the HTTP
`Host:` header keep the original name.  A redirect target is resolved and
refused by the same rule.  A non-global target is reported as `refused`, never
followed, so a document can describe an intranet link without this tool reaching
into anything.

Outcomes are a closed set so the caller can act on a class, not a status code:
`ok`, `redirect` (followed), `permanent_redirect` (301/308), `restricted`
(401/403), `dead` (404/410, DNS failure, connection refused), `transient`
(429/5xx/timeout, retried), `http_error` (any other 4xx/5xx), `refused`
(non-global or malformed).

Usage:
    py -3.12 scripts/url_probe.py                       # curated docs, summary
    py -3.12 scripts/url_probe.py --verbose
    py -3.12 scripts/url_probe.py --json --all
    py -3.12 scripts/url_probe.py --paths README.md docs/api_reference.md
    py -3.12 scripts/url_probe.py --hosts               # unique hosts only

Exit code: 1 when any link is `dead` or `refused` (the classes a weekly audit
should open an issue for), else 0.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import pathlib
import re
import socket
import ssl
import sys
import time
from collections import namedtuple
from urllib.parse import urlsplit

REPO = pathlib.Path(__file__).resolve().parents[1]

#: The curated set the audit walks.  The paper corpora
#: (`docs/paper_survey_26/`, `Strategies/books*/`) are deliberately excluded:
#: they cite thousands of arXiv links, which are stable and would swamp the run.
DOC_GLOBS = ("README.md", "docs/*.md", "docs/developer/*.md")

_URL = re.compile(r"https?://[^\s<>()\[\]\"'`]+")
_FATAL = frozenset({"dead", "refused"})
_UA = "TradingAgents-link-audit/1.0"

#: URLs this repo documents that are deliberately not browsable resources - a
#: POST-only API endpoint and a bare API host both answer a HEAD/GET with 404.
#: That is not link rot, so they are reported as `allowed`.  Reviewed by hand.
_NON_BROWSABLE = {
    "https://openrouter.ai/api/alpha/decisions": "POST-only JEV decision endpoint",
    "https://openapi.longbridge.com": "bare Longbridge HTTP API host (resources under /v1, POST)",
}

Probe = namedtuple("Probe", "url outcome status detail")
Step = namedtuple("Step", "addr error")


def extract_urls(text: str) -> list[str]:
    """Every http(s) URL in `text`, trailing punctuation trimmed, order kept."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in _URL.findall(text):
        url = raw.rstrip(".,;:")
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def is_public(addr: str) -> bool:
    """True only for a globally-routable address (the SSRF gate)."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return ip.is_global


def resolve(host: str, port: int, resolver=socket.getaddrinfo) -> Step:
    """(pinned address | None, error).  Refuses a non-global answer."""
    try:
        infos = resolver(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        return Step(None, f"dns: {exc}")
    for info in infos:
        addr = info[4][0]
        if is_public(addr):
            return Step(addr, None)
    return Step(None, "non-global or unresolvable")


def classify_status(code: int) -> str:
    if 200 <= code < 300:
        return "ok"
    if code in (301, 308):
        return "permanent_redirect"
    if code in (302, 303, 307):
        return "redirect"
    if code in (401, 403):
        return "restricted"
    if code in (404, 410):
        return "dead"
    if code == 429 or 500 <= code < 600:
        return "transient"
    return "http_error"


def _raw_fetch(
    host: str, addr: str, port: int, tls: bool, path: str, timeout: float, method: str = "HEAD"
) -> bytes:
    """A HEAD (or GET) request to the PINNED address, Host/SNI kept."""
    sock = socket.create_connection((addr, port), timeout=timeout)
    try:
        if tls:
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(sock, server_hostname=host)
        req = (
            f"{method} {path or '/'} HTTP/1.1\r\n"
            f"Host: {host}\r\nUser-Agent: {_UA}\r\nAccept: */*\r\n"
            f"Connection: close\r\n\r\n"
        )
        sock.sendall(req.encode("ascii", "replace"))
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 16384:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data
    finally:
        sock.close()


def _status_and_location(head: bytes) -> tuple[int, str | None]:
    text = head.decode("iso-8859-1", "replace")
    lines = text.split("\r\n")
    if not lines or not lines[0].startswith("HTTP/"):
        return 0, None
    parts = lines[0].split()
    code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    location = None
    for line in lines[1:]:
        if not line:
            break
        if line.lower().startswith("location:"):
            location = line.split(":", 1)[1].strip()
    return code, location


def probe(
    url: str,
    *,
    timeout: float = 10.0,
    retries: int = 2,
    max_redirects: int = 5,
    resolver=socket.getaddrinfo,
    fetch=_raw_fetch,
) -> Probe:
    """Probe one URL, following redirects, never leaving the global address space."""
    if url in _NON_BROWSABLE:
        return Probe(url, "allowed", 0, _NON_BROWSABLE[url])
    current = url
    for _hop in range(max_redirects + 1):
        parts = urlsplit(current)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return Probe(url, "refused", 0, "malformed or non-http scheme")
        tls = parts.scheme == "https"
        port = parts.port or (443 if tls else 80)
        host = parts.hostname
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"
        step = resolve(host, port, resolver)
        if step.addr is None:
            return Probe(url, "refused", 0, f"{host}: {step.error}")
        last = ""
        for attempt in range(retries + 1):
            try:
                head = fetch(host, step.addr, port, tls, path, timeout, "HEAD")
                break
            except TimeoutError as exc:
                last = f"timeout: {exc}"
            except (OSError, ssl.SSLError) as exc:
                return Probe(url, "dead", 0, f"{type(exc).__name__}: {exc}")
            if attempt < retries:
                time.sleep(min(2**attempt, 4))
        else:
            return Probe(url, "transient", 0, last)
        code, location = _status_and_location(head)
        if code in (404, 405):
            # Many servers reject HEAD (or hide a page from it); ask once with GET.
            try:
                head = fetch(host, step.addr, port, tls, path, timeout, "GET")
                code, location = _status_and_location(head)
            except OSError:
                pass
        outcome = classify_status(code)
        if outcome in ("redirect", "permanent_redirect") and location:
            if outcome == "permanent_redirect":
                current = location if location.startswith("http") else current
                if current == url:
                    return Probe(url, "permanent_redirect", code, location)
            if location.startswith("http"):
                current = location
                continue
            # Relative redirect: same origin, re-probe the resolved path.
            return Probe(url, outcome, code, f"relative -> {location}")
        return Probe(url, outcome, code, "")
    return Probe(url, "transient", 0, f"> {max_redirects} redirects")


def _collect(paths: list[str] | None) -> list[str]:
    files = [REPO / p for p in paths] if paths else [p for pat in DOC_GLOBS for p in REPO.glob(pat)]
    urls: list[str] = []
    seen: set[str] = set()
    for f in sorted(set(files)):
        if not f.is_file():
            continue
        for u in extract_urls(f.read_text(encoding="utf-8", errors="replace")):
            if u not in seen:
                seen.add(u)
                urls.append(u)
    return urls


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paths", nargs="*", default=None, help="Only these files.")
    ap.add_argument("--hosts", action="store_true", help="Probe one URL per unique host.")
    ap.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout (s).")
    ap.add_argument("--retries", type=int, default=2, help="Retries on a transient failure.")
    ap.add_argument("--json", action="store_true", help="Machine-readable results.")
    ap.add_argument("--verbose", action="store_true", help="Print every result, not the summary.")
    ap.add_argument("--all", action="store_true", help="With --json, include non-fatal rows.")
    ap.add_argument("--limit", type=int, default=0, help="Cap URLs probed (0 = no cap).")
    args = ap.parse_args(argv)

    urls = _collect(args.paths)
    if args.hosts:
        hosts: set[str] = set()
        picked: list[str] = []
        for u in urls:
            h = urlsplit(u).hostname or ""
            if h and h not in hosts:
                hosts.add(h)
                picked.append(u)
        urls = picked
    if args.limit:
        urls = urls[: args.limit]

    results = [
        probe(u, timeout=args.timeout, retries=args.retries)
        for u in urls
    ]
    bad = [r for r in results if r.outcome in _FATAL]

    if args.json:
        rows = results if args.all else bad
        print(
            json.dumps(
                {
                    "probed": len(results),
                    "fatal": len(bad),
                    "results": [
                        {
                            "url": r.url,
                            "outcome": r.outcome,
                            "status": r.status,
                            "detail": r.detail,
                        }
                        for r in rows
                    ],
                },
                indent=2,
            )
        )
        return 1 if bad else 0

    if args.verbose:
        for r in results:
            tag = f"{r.status}" if r.status else "-"
            print(f"{r.outcome:>18}  {tag:>4}  {r.url}" + (f"  ({r.detail})" if r.detail else ""))
    counts: dict[str, int] = {}
    for r in results:
        counts[r.outcome] = counts.get(r.outcome, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    print(f"url-probe: {len(results)} link(s): {summary or 'none'}")
    for r in bad:
        print(f"  FATAL {r.outcome}: {r.url} ({r.detail})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
