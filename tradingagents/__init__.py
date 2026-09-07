import contextlib
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

# Output-token caps are budget windows, not per-invocation overrides: a
# reasoning model spends part of its output cap on hidden reasoning, so a
# launcher that pre-exports a LOW max_output_tokens can starve report turns
# into empty responses. Reload .env with override=True for exactly the three
# cap keys so the repo's declared values always win (load_dotenv above used
# override=False and kept the launcher's stale smaller cap). Only these keys
# are force-set; all other caller exports are untouched.
try:
    import os as _os

    from dotenv import find_dotenv as _find, load_dotenv as _load

    _CAP_KEYS = (
        "TRADINGAGENTS_MAX_OUTPUT_TOKENS",
        "TRADINGAGENTS_MAX_OUTPUT_TOKENS_QUICK",
        "TRADINGAGENTS_MAX_OUTPUT_TOKENS_DEEP",
    )
    _prev = {k: _os.environ.get(k) for k in _CAP_KEYS}
    _load(_find(usecwd=True), override=True)
    _load(_find(".env.enterprise", usecwd=True), override=True)
    # For any cap key .env did not set, keep the caller's original value
    # (only raise a low launcher cap, never lower against explicit intent).
    for _k in _CAP_KEYS:
        if _prev.get(_k) is not None and _os.environ.get(_k) is None:
            _os.environ[_k] = _prev[_k]
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
