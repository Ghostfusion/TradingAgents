"""Capex-normalized FCF DCF — revenue-driven fade model + maintenance-capex floor.

WHY THIS EXISTS (the incident)
------------------------------
``tradingagents.strategies.dcf.compute_dcf`` projects one FCF at a single growth
rate ``g`` for N years and then applies Gordon at the SAME ``g``. That
telescopes algebraically into a single-stage perpetuity of *today's* FCF:

    FV/share = FCF/share * (1+g)/(wacc-g) + net_cash/share

Verified on MSFT 2026-09-16: ``8.85 * 1.025 / 0.075 + 3.84 = 124.80``, exactly
the printed leaf. The consequence is that the "5-year explicit window" cannot
represent a capex regime change: a company mid-investment-cycle is priced as if
its depressed free cash flow were permanent. MSFT FY2026 (revenue $331.8B,
OCF $182.9B, capex $115.9B, FCF $67.0B, D&A $43.45B) is exactly that case — the
model prints a fair value far below the market price and the report ends up
labelling the gap a "modeling artifact" instead of measuring it.

These two functions replace the dismissal with measurable answers:

* :func:`normalized_fcf_dcf` drives value off revenue and a capex-INTENSITY
  path (capex as a share of revenue) that fades from today's buildout level to
  a steady state (D&A/revenue — the capex that only maintains the asset base),
  so the terminal value capitalizes a normal, not a permanently-depressed, FCF.
  ``defensive_capex_share`` is the honest counterweight: if the buildout is
  franchise-defending rather than growth, that share of today's EXCESS capex
  intensity is treated as permanently required, and the answer sits closer to
  the reported-FCF perpetuity.
* :func:`maintenance_fcf` gives the other end of the range — the FCF the
  business would produce if capex were only D&A (stand-still capex), with
  ``reported_fcf`` and ``growth_capex`` alongside so the spread is explicit.

Known, deliberate property of the window (not hidden): the explicit years
discount at ``wacc`` while the FCF path grows at ``revenue_growth``, so when
``revenue_growth < terminal_growth`` the window slightly UNDERSTATES the forward
perpetuity on the same FCF (a flat FCF window converges to ``FCF/wacc``, not to
``FCF*(1+g)/(wacc-g)``). When ``revenue_growth == terminal_growth`` the model
telescopes exactly onto the forward perpetuity — that identity is what makes the
capex-intensity path the only lever that moves the answer.

Both functions are pure and deterministic: no I/O, no network, no logging, and
no imports from the agent layer. Nothing raises — unusable inputs degrade to an
explicit ``usable=False`` + ``reason`` result (mirroring ``compute_dcf``'s
honesty, which returns ``None`` when its inputs are unusable) rather than
fabricating a figure.
"""

from __future__ import annotations

__all__ = ["maintenance_fcf", "normalized_fcf_dcf"]

_MAINTENANCE_BASIS = (
    "maintenance capex proxied by D&A: ocf - depreciation is the spend required "
    "to stand still; reported_fcf = ocf - capex bills the whole buildout against "
    "cash flow; growth_capex = capex - depreciation is the discretionary "
    "expansion spend the fade model amortizes instead of capitalizing forever"
)


def _num(x, default=None):
    """Coerce ``x`` to float, or ``default`` when missing/uncoercible."""
    if x is None:
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _int(x, default: int) -> int:
    """Coerce ``x`` to int, or ``default`` when missing/uncoercible."""
    v = _num(x)
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError, OverflowError):
        return default


def maintenance_fcf(
    ocf: float | None,
    depreciation: float | None,
    capex: float | None = None,
) -> dict:
    """Maintenance-capex floor view of cash flow.

    ``depreciation`` (D&A) is the maintenance-capex proxy: the capital spend
    required to stand still. So ``maintenance_fcf = ocf - depreciation`` is the
    cash the business throws off before any growth investment — the floor a
    perpetuity should capitalize if the buildout stops. ``reported_fcf = ocf -
    capex`` is the GAAP-style free cash flow the market actually sees, and
    ``growth_capex = capex - depreciation`` isolates the discretionary expansion
    spend that the fade model amortizes rather than capitalizes forever.

    Args:
        ocf: operating cash flow (same units as the caller's price target path).
        depreciation: D&A for the period, used as the maintenance-capex proxy.
        capex: reported capital expenditure; ``None`` when unavailable.

    Returns:
        dict ``{"maintenance_fcf", "reported_fcf", "growth_capex", "basis"}``.
        Each figure is ``None`` when its inputs are missing; ``basis`` names the
        proxy explicitly. Never raises.
    """
    o = _num(ocf)
    dep = _num(depreciation)
    cap = _num(capex)
    return {
        "maintenance_fcf": (o - dep) if o is not None and dep is not None else None,
        "reported_fcf": (o - cap) if o is not None and cap is not None else None,
        "growth_capex": (cap - dep) if cap is not None and dep is not None else None,
        "basis": _MAINTENANCE_BASIS,
    }


def _unusable(
    reason: str, assumptions: dict, maintenance: dict, wacc: float | None, shares: float | None
) -> dict:
    """Explicit "no usable valuation" result (never a fabricated number)."""
    return {
        "usable": False,
        "reason": reason,
        "fair_value": None,
        "pv_explicit": None,
        "pv_terminal": None,
        "terminal_share": None,
        "wacc": wacc,
        "shares": shares,
        "fcf_path": [],
        "capex_ratio_path": [],
        "assumptions": assumptions,
        "maintenance": maintenance,
    }


def normalized_fcf_dcf(
    revenue: float | None,
    ocf: float | None,
    capex: float | None,
    depreciation: float | None,
    shares: float | None,
    wacc: float | None,
    revenue_growth: float | None,
    *,
    margin: float | None = None,
    years: int = 5,
    terminal_capex_ratio: float | None = None,
    capex_fade_years: int | None = None,
    terminal_growth: float = 0.025,
    cash: float | None = 0.0,
    debt: float | None = 0.0,
    defensive_capex_share: float | None = None,
) -> dict:
    """Revenue-driven DCF whose capex intensity fades from buildout to steady state.

    Mechanics:
        ``margin = ocf / revenue`` (override via ``margin``);
        ``initial_capex_ratio = capex / revenue``;
        ``terminal_capex_ratio = depreciation / revenue`` (steady state: capex
        tracks D&A) unless overridden. The ratio path fades LINEARLY from the
        initial ratio in year 1 to the terminal ratio in year ``capex_fade_years``
        (default ``years``), then holds the terminal ratio; with
        ``capex_fade_years <= 1`` the terminal ratio applies from year 1.
        ``defensive_capex_share`` in [0, 1] treats that share of today's EXCESS
        capex intensity as permanently required:
        ``terminal_ratio_effective = terminal_ratio + share * (initial_ratio -
        terminal_ratio)``, so 1.0 reproduces "capex stays at today's intensity"
        (the reported-FCF view) and 0.0 is the full fade.

        ``revenue_t = revenue * (1+revenue_growth)**t``,
        ``ocf_t = revenue_t * margin``, ``fcf_t = ocf_t - revenue_t * ratio_t``
        for t in 1..years; explicit flows are discounted at ``wacc`` (year-t
        factor ``1/(1+wacc)**t``). The Gordon terminal value keeps the repo
        convention ``tv = fcf_years * (1+terminal_growth)/(wacc-terminal_growth)``,
        discounted back from year ``years``; ``ev = pv_explicit + pv_terminal``;
        ``equity = ev + cash - debt``; ``fair_value = equity / shares``.

    Args:
        revenue: latest annual revenue.
        ocf: operating cash flow.
        capex: reported capital expenditure.
        depreciation: D&A, the maintenance-capex proxy and default terminal ratio.
        shares: diluted shares outstanding.
        wacc: discount rate (fraction).
        revenue_growth: annual revenue growth (fraction) for the explicit window.
        margin: OCF margin override; defaults to ``ocf/revenue``.
        years: explicit forecast years (>= 1).
        terminal_capex_ratio: capex/revenue held after the fade; defaults to
            ``depreciation/revenue``.
        capex_fade_years: years over which the intensity fades to terminal;
            defaults to ``years``.
        terminal_growth: Gordon growth after the window (fraction).
        cash: cash + equivalents added to EV.
        debt: total debt subtracted from EV.
        defensive_capex_share: share of today's excess capex intensity deemed
            permanently required (0..1, clamped); defaults to 0.

    Returns:
        dict with keys ``usable`` (bool), ``reason`` (str | None),
        ``fair_value``, ``pv_explicit``, ``pv_terminal``, ``terminal_share``
        (= pv_terminal/ev), ``wacc``, ``shares``, ``fcf_path``,
        ``capex_ratio_path``, ``assumptions`` (the full assumption set, so a
        printed leaf is reproducible from it) and ``maintenance`` (the
        ``maintenance_fcf`` view). ``usable=False`` with a ``reason`` (and no
        exception) when revenue/ocf/capex/shares/wacc/revenue_growth is missing,
        revenue <= 0, shares <= 0, wacc <= 0, wacc <= terminal_growth, the
        terminal capex ratio is unavailable (depreciation missing and no
        explicit override), or the resulting equity value is <= 0.
    """
    rev = _num(revenue)
    op_cf = _num(ocf)
    cap = _num(capex)
    dep = _num(depreciation)
    sh = _num(shares)
    w = _num(wacc)
    rg = _num(revenue_growth)
    tg = _num(terminal_growth, 0.025)
    if tg is None:
        tg = 0.025
    cash_v = _num(cash, 0.0)
    if cash_v is None:
        cash_v = 0.0
    debt_v = _num(debt, 0.0)
    if debt_v is None:
        debt_v = 0.0
    defensive = _num(defensive_capex_share, 0.0)
    if defensive is None:
        defensive = 0.0
    defensive = min(1.0, max(0.0, defensive))

    years_v = _int(years, 5)
    if years_v < 1:
        years_v = 1
    fade_v = _int(capex_fade_years, years_v) if capex_fade_years is not None else years_v
    if fade_v < 1:
        fade_v = 1

    positive_rev = rev is not None and rev > 0
    margin_v = (
        _num(margin)
        if margin is not None
        else (op_cf / rev if positive_rev and op_cf is not None else None)
    )
    initial_ratio = cap / rev if positive_rev and cap is not None else None
    explicit_terminal = _num(terminal_capex_ratio) if terminal_capex_ratio is not None else None
    terminal_ratio = (
        explicit_terminal
        if explicit_terminal is not None
        else (dep / rev if positive_rev and dep is not None else None)
    )
    terminal_effective = (
        terminal_ratio + defensive * (initial_ratio - terminal_ratio)
        if terminal_ratio is not None and initial_ratio is not None
        else terminal_ratio
    )

    assumptions = {
        "revenue": rev,
        "ocf": op_cf,
        "capex": cap,
        "depreciation": dep,
        "revenue_growth": rg,
        "margin": margin_v,
        "initial_capex_ratio": initial_ratio,
        "terminal_capex_ratio_effective": terminal_effective,
        "capex_fade_years": fade_v,
        "years": years_v,
        "terminal_growth": tg,
        "defensive_capex_share": defensive,
        "cash": cash_v,
        "debt": debt_v,
    }
    maintenance = maintenance_fcf(ocf, depreciation, capex)

    missing = [
        name
        for name, val in (
            ("revenue", rev),
            ("ocf", op_cf),
            ("capex", cap),
            ("shares", sh),
            ("wacc", w),
            ("revenue_growth", rg),
        )
        if val is None
    ]
    if missing:
        return _unusable("missing inputs: " + ", ".join(missing), assumptions, maintenance, w, sh)
    if rev <= 0:
        return _unusable("revenue must be positive", assumptions, maintenance, w, sh)
    if sh <= 0:
        return _unusable("shares must be positive", assumptions, maintenance, w, sh)
    if w <= 0:
        return _unusable("wacc must be positive", assumptions, maintenance, w, sh)
    if margin_v is None:
        return _unusable(
            "margin unavailable: need ocf/revenue or an explicit margin",
            assumptions,
            maintenance,
            w,
            sh,
        )
    if terminal_ratio is None:
        return _unusable(
            "terminal capex ratio unavailable: need depreciation/revenue or an explicit terminal_capex_ratio",
            assumptions,
            maintenance,
            w,
            sh,
        )
    if w <= tg:
        return _unusable(
            f"wacc ({w:.4f}) must exceed terminal_growth ({tg:.4f}) for a finite terminal value",
            assumptions,
            maintenance,
            w,
            sh,
        )

    span = fade_v - 1
    ratio_path = []
    for t in range(1, years_v + 1):
        if fade_v <= 1 or t >= fade_v:
            ratio_path.append(terminal_effective)
        else:
            ratio_path.append(
                initial_ratio + (terminal_effective - initial_ratio) * (t - 1) / span
            )
    revenue_path = [rev * (1.0 + rg) ** t for t in range(1, years_v + 1)]
    fcf_path = [
        rev_t * (margin_v - ratio_t)
        for rev_t, ratio_t in zip(revenue_path, ratio_path, strict=True)
    ]
    pv_explicit = sum(
        f / (1.0 + w) ** t for t, f in zip(range(1, years_v + 1), fcf_path, strict=True)
    )
    tv = fcf_path[-1] * (1.0 + tg) / (w - tg)
    pv_terminal = tv / (1.0 + w) ** years_v
    ev = pv_explicit + pv_terminal
    equity = ev + cash_v - debt_v
    if equity <= 0:
        return _unusable(
            "equity value is not positive: debt exceeds enterprise value",
            assumptions,
            maintenance,
            w,
            sh,
        )
    return {
        "usable": True,
        "reason": None,
        "fair_value": equity / sh,
        "pv_explicit": pv_explicit,
        "pv_terminal": pv_terminal,
        "terminal_share": (pv_terminal / ev) if ev else None,
        "wacc": w,
        "shares": sh,
        "fcf_path": fcf_path,
        "capex_ratio_path": ratio_path,
        "assumptions": assumptions,
        "maintenance": maintenance,
    }
