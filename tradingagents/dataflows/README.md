# dataflows — vendor notes

The vendor layer (`route_to_vendor`, typed errors, sentinel contract, cache)
plus the guarded quirks this project has learned from its no-key + keyed
vendors. Anything here pinned to a library version is a **deliberate pin** —
bumping the library is a conscious step, not an accident of a floating
constraint (see the version-bump checklist below).

## Pinned dependency: yfinance ~= 1.4

`requirements.txt` / `pyproject.toml` pin `yfinance~=1.4` (the 1.x line,
verified since 1.4.1). yfinance 1.x is an active rewrite (protobuf pricing,
SQLite caches, curl_cffi backend); behavior has changed between minors (e.g.
1.4.0 changed `ignore_tz` semantics: intraday indexes now convert to the
most-common exchange timezone instead of UTC; the unnamed-index quirk). The
quirk guards below are version-coupled by construction — evaluate them
before any bump.

### Guarded quirks (verified against 1.4+)

- **Exclusive `end` (#986)**: yfinance `end` is exclusive; callers request
  `today + 1d` so the current-day row is included. Look-ahead is still
  prevented by the `effective_date`/`curr_date` filter downstream.
- **Stale frames (#1021)**: yfinance occasionally returns ~year-old frames;
  `MAX_OHLCV_STALE_DAYS = 10` treats older-than-10-day latest rows as stale.
  Date-ish frames are normalized (`reset_index`/`DatetimeIndex` handling)
  because some builds leave the index unnamed or name it `Datetime`.
- **Statements newest-first**: yfinance financial-statement CSVs put the
  most recent period in the FIRST column; parsers take the first numeric cell
  (the rightmost-cell reading is a known bug).
- **Rate limits**: yfinance raises `YFRateLimitError` on HTTP 429 but does
  not retry internally; `stockstats_utils.yf_retry` adds exponential backoff
  (3 retries, base 2.0 s) only for rate limits — other exceptions propagate
  immediately.
- **Blank/garbage tickers**: `symbol_utils.normalize_symbol` must resolve
  every yfinance entry point; never pass raw user text into `yf.Ticker`.

### Version-bump checklist (any 1.x bump, or 2.x)

1. Re-run the vendor suites: `tests/test_yfinance_keyless_vendor.py`,
   `tests/test_vendor_routing.py`, `tests/test_vendor_errors.py`,
   `tests/test_market_router.py`, `tests/test_vendor_absence.py`.
2. Diff the changelog for quirk-affecting changes: `ignore_tz` /
   index-naming / exclusive-end / rate-limit / cookie-crumb strategy.
3. Update the guarded-quirk list above to the verified version.
4. Commit the pin change separately from feature work (revert-friendly).