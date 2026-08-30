import re
from pathlib import Path

# Tickers can contain letters, digits, dot, dash, underscore, caret
# (index symbols like ^GSPC), equals (futures like GC=F), and plus
# (forex/CFD symbols like XAUUSD+). None of these enable directory
# traversal, so the value never escapes a containing directory when
# interpolated into a path. Anything else is rejected.
_TICKER_PATH_RE = re.compile(r"^[A-Za-z0-9._\-\^=+]+$")


def safe_ticker_component(value: str, *, max_len: int = 32) -> str:
    """Validate ``value`` is safe to interpolate into a filesystem path.

    Tickers come from user CLI input or from LLM tool calls, both of which
    can be influenced by attacker-controlled content (e.g. prompt injection
    embedded in fetched news). Without validation, a value like
    ``"../../../etc/foo"`` flows into ``os.path.join`` / ``Path /`` and
    escapes the configured cache, checkpoint, or results directory.

    Returns ``value`` unchanged when it matches the allowed pattern; raises
    ``ValueError`` otherwise.
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"ticker must be a non-empty string, got {value!r}")
    if len(value) > max_len:
        raise ValueError(f"ticker exceeds {max_len} chars: {value!r}")
    if not _TICKER_PATH_RE.fullmatch(value):
        raise ValueError(
            f"ticker contains characters not allowed in a filesystem path: {value!r}"
        )
    # The regex above allows '.', so values like '.', '..', '...' would pass,
    # and as a path component they traverse the parent directory. Reject any
    # value that's only dots.
    if set(value) == {"."}:
        raise ValueError(f"ticker cannot consist solely of dots: {value!r}")
    return value


def repo_root() -> Path:
    """Canonical TradingAgents repo root (parent of the installed package).

    Derived from this file's location (``tradingagents/dataflows/utils.py``),
    never from the process CWD, so every output lands in the TradingAgents
    project no matter where the CLI / web server was launched from.
    """
    return Path(__file__).resolve().parent.parent.parent


def resolve_output_path(value: str | Path) -> Path:
    """Anchor a relative output path to the repo root.

    Reports / screener / action-report outputs must always live under the
    TradingAgents project (``<repo>/reports``, ``<repo>/screener``,
    ``<repo>/action_reports``) regardless of the launch directory — the web
    app runs from ``TradingNew`` or ``trading_web`` and an in-process
    ``batch.analyze`` used to write to the process CWD. Absolute paths and
    ``~``-expanded paths are returned unchanged (callers that opt into a
    custom location keep it).
    """
    p = Path(value).expanduser()
    if p.is_absolute():
        return p
    return repo_root() / p
