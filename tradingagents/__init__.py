import contextlib
import logging
import warnings

# Load .env files at package import so DEFAULT_CONFIG's env-var overlay
# (and every llm_clients consumer) sees the user's keys regardless of
# which entry point started the process. find_dotenv(usecwd=True) walks
# from the CWD, so the installed `tradingagents` console script picks up
# the project's .env instead of stepping up from site-packages.
# load_dotenv defaults to override=False, so it never clobbers values
# the caller has already exported.
try:
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv(usecwd=True))
    load_dotenv(find_dotenv(".env.enterprise", usecwd=True), override=False)
except ImportError:
    pass


def env_shadow_keys(declared: dict, environ) -> list[str]:
    """TRADINGAGENTS_* keys whose EXPORTED value overrides a different .env value.

    ``load_dotenv`` defaults to ``override=False``, so a variable the launching
    process already exported wins over the file. That order is correct - it is
    what python-dotenv's own README documents, what pydantic-settings states
    ("environment variables will always take priority over values loaded from a
    dotenv file") and what 12factor.net III requires ("store config in the
    environment") - and it is also invisible: the exported set on this machine
    has drifted, and a drifted key changes what a run computes (a 13-name vs
    15-name risk basket moves the book-CVaR GATE INPUT; a flipped decider gate
    changed the verdict battery from three files to four with nothing in the
    report tree saying so). This names the survivors so the drift is visible.

    ``declared`` maps a key to the value the .env file(s) declare; a valueless
    ``KEY`` line arrives as ``None`` and is skipped, because ``load_dotenv``
    ignores those. Only the engine's own ``TRADINGAGENTS_*`` config family is
    audited; vendor keys (``OPENROUTER_API_KEY``, ``ALPACA_*`` ...) belong to
    the modules that read them.
    """
    return sorted(
        key
        for key, exported in environ.items()
        if key.startswith("TRADINGAGENTS_")
        and declared.get(key) is not None
        and exported != declared[key]
    )


def env_shadow_warning(shadowed: list[str]) -> str | None:
    """One line naming the shadowed keys - key NAMES only, NEVER a value."""
    if not shadowed:
        return None
    shown = ", ".join(shadowed[:6])
    more = f" (+{len(shadowed) - 6} more)" if len(shadowed) > 6 else ""
    return (
        f"config: {len(shadowed)} TRADINGAGENTS_* key(s) are overridden by the process "
        f"environment (load_dotenv override=False), so this run uses the EXPORTED value, "
        f"not the .env one: {shown}{more}"
    )


# Output-token caps are budget windows, not per-invocation overrides: a
# reasoning model spends part of its output cap on hidden reasoning, so a
# launcher that pre-exports a LOW max_output_tokens can starve report turns
# into empty responses. Read exactly the three cap keys out of the files and
# force those, so the repo's declared values beat the launcher's stale smaller
# cap. Every OTHER caller export stays untouched: the earlier implementation
# reloaded the whole .env with override=True, which rewrote os.environ for
# every key the file declares (including the round-3 TRADINGAGENTS_ENABLE_*
# gates), so an exported value was silently replaced by the file's value.
try:
    import os as _os

    from dotenv import dotenv_values as _dotenv_values, find_dotenv as _find

    _CAP_KEYS = (
        "TRADINGAGENTS_MAX_OUTPUT_TOKENS",
        "TRADINGAGENTS_MAX_OUTPUT_TOKENS_QUICK",
        "TRADINGAGENTS_MAX_OUTPUT_TOKENS_DEEP",
    )
    _file_declared: dict = {}
    for _path in (_find(usecwd=True), _find(".env.enterprise", usecwd=True)):
        if not _path:
            continue
        for _key, _value in (_dotenv_values(_path) or {}).items():
            _file_declared[_key] = _value  # a later file wins, as before
    # A cap .env does not declare keeps whatever the caller exported.
    _os.environ.update({k: v for k, v in _file_declared.items() if k in _CAP_KEYS and v})
    # Audit AFTER the caps: a cap re-forced from the file is not a shadow, so
    # what gets named here is what the effective config actually runs with.
    _shadow_msg = env_shadow_warning(env_shadow_keys(_file_declared, _os.environ))
    if _shadow_msg:
        logging.getLogger(__name__).warning(_shadow_msg)
except (ImportError, OSError):
    pass

# langchain-core 1.3.3 calls surface_langchain_deprecation_warnings() in
# its own __init__, which prepends default-action filters for its
# subclassed warning categories. To suppress a specific warning we must
# install our filter AFTER langchain-core has installed its own, so import
# it first. The package is a guaranteed transitive dep via langgraph.
with contextlib.suppress(ImportError):
    import langchain_core  # noqa: F401

# langgraph-checkpoint 4.0.3 calls Reviver() at module load without an
# explicit allowed_objects, which triggers a noisy pending-deprecation
# warning from langchain-core 1.3.3 on every interpreter start. The fix
# is already merged upstream (langchain-ai/langgraph#7743, 2026-05-08)
# and will arrive in the next langgraph-checkpoint release. Remove this
# block (and the langchain_core preload above) when we bump past it.
warnings.filterwarnings(
    "ignore",
    message=r"The default value of `allowed_objects`.*",
    category=PendingDeprecationWarning,
)
