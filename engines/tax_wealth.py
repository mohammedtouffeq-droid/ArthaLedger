"""Indian Income Tax Optimizer (Budget 2025 + Breakeven + Slab Waterfall), Goal SIP, Capital Gains & Loan EMI Engine."""
from __future__ import annotations

from typing import Any, Dict, List


def _progressive_slab_tax(taxable: float, slabs: List[tuple[float, float]]) -> tuple[float, List[Dict[str, Any]]]:
    remaining = max(0.0, taxable)
    prev_limit = 0.0
    total = 0.0
    breakdown: List[Dict[str, Any]] = []

    for upper, rate in slabs:
        slice_top = min(remaining, upper) if remaining > prev_limit else prev_limit
        band_income = max(0.0, slice_top - prev_limit)
        band_tax = band_income * rate
        total += band_tax
        label_top = "Above" if upper == float("inf") else f"Rs.{int(upper):,}"
        breakdown.append({
            "slab": f"Rs.{int(prev_limit):,} - {label_top}" if upper != float("inf") else f"Above Rs.{int(prev_limit):,}",
            "rate_pct": round(rate * 100, 1),
            "taxable_in_slab": round(band_income, 2),
            "tax": round(band_tax, 2),
        })
        prev_limit = upper

    return total, breakdown


def _compute_old_tax_only(gross: float, total_deductions: float) -> float:
    old_taxable = max(0.0, gross - total_deductions)
    old_slabs = [(250000.0, 0.00), (500000.0, 0.05), (1000000.0, 0.20), (float("inf"), 0.30)]
    old_base, _ = _progressive_slab_tax(old_taxable, old_slabs)
    old_rebate = min(12500.0, old_base) if old_taxable <= 500000.0 else 0.0
    return round(max(0.0, old_base - old_rebate) * 1.04, 2)


def _solve_breakeven_deduction(gross: float, target_new_tax: float) -> float:
    if target_new_tax <= 0.0:
        return max(0.0, gross - 500000.0)
    low, high = 0.0, gross
    for _ in range(42):
        mid = (low + high) / 2.0
        if _compute_old_tax_only(gross, mid) > target_new_tax:
            low = mid
        else:
            high = mid
    return round(high, 0)


def calculate_indian_tax(
    gross_income: float,
    is_salaried: bool = True,
    deduction_80c: float = 0.0,
    deduction_80d: float = 0.0,
    hra_exemption: float = 0.0,
    home_loan_interest: float = 0.0,
    nps_80ccd1b: float = 0.0,
) -> Dict[str, Any]:
    """
    Compares Indian Old Regime vs New Regime (Section 115BAC, Union Budget 2025 FY 2025-26 / 2026-27)
    including Rs.75,000 Standard Deduction, Sec 87A Rs.60,000 rebate up to Rs.12,00,000 taxable,
    marginal relief above Rs.12L, 4% Cess, slab waterfall, monthly take-home, and deduction breakeven.
    """
    gross = max(0.0, float(gross_income or 0.0))

    new_std_ded = 75000.0 if is_salaried and gross > 0 else 0.0
    new_taxable = max(0.0, gross - new_std_ded)
    new_slabs = [
        (400000.0, 0.00),
        (800000.0, 0.05),
        (1200000.0, 0.10),
        (1600000.0, 0.15),
        (2000000.0, 0.20),
        (2400000.0, 0.25),
        (float("inf"), 0.30),
    ]
    new_base_tax, new_breakdown = _progressive_slab_tax(new_taxable, new_slabs)

    new_rebate = 0.0
    new_marginal_relief = 0.0
    if new_taxable <= 1200000.0:
        new_rebate = min(60000.0, new_base_tax)
        new_tax_after_rebate = max(0.0, new_base_tax - new_rebate)
    else:
        excess_over_12l = new_taxable - 1200000.0
        if new_base_tax > excess_over_12l:
            new_marginal_relief = new_base_tax - excess_over_12l
            new_tax_after_rebate = excess_over_12l
        else:
            new_tax_after_rebate = new_base_tax

    new_cess = new_tax_after_rebate * 0.04
    new_total_tax = round(new_tax_after_rebate + new_cess, 2)

    old_std_ded = 50000.0 if is_salaried and gross > 0 else 0.0
    cap_80c = min(150000.0, max(0.0, float(deduction_80c or 0.0)))
    cap_80d = min(100000.0, max(0.0, float(deduction_80d or 0.0)))
    cap_hra = max(0.0, float(hra_exemption or 0.0))
    cap_hl = min(200000.0, max(0.0, float(home_loan_interest or 0.0)))
    cap_nps = min(50000.0, max(0.0, float(nps_80ccd1b or 0.0)))
    old_total_deductions = old_std_ded + cap_80c + cap_80d + cap_hra + cap_hl + cap_nps

    old_taxable = max(0.0, gross - old_total_deductions)
    old_slabs = [(250000.0, 0.00), (500000.0, 0.05), (1000000.0, 0.20), (float("inf"), 0.30)]
    old_base_tax, old_breakdown = _progressive_slab_tax(old_taxable, old_slabs)
    old_rebate = min(12500.0, old_base_tax) if old_taxable <= 500000.0 else 0.0
    old_after_rebate = max(0.0, old_base_tax - old_rebate)
    old_cess = old_after_rebate * 0.04
    old_total_tax = round(old_after_rebate + old_cess, 2)

    savings = round(abs(old_total_tax - new_total_tax), 2)
    breakeven_deduction = _solve_breakeven_deduction(gross, new_total_tax)
    best_tax = min(new_total_tax, old_total_tax)
    monthly_take_home = round(max(0.0, (gross - best_tax) / 12.0), 2)

    if new_total_tax <= old_total_tax:
        recommended = "NEW_REGIME"
        summary = (
            f"New Regime (Sec 115BAC) saves Rs.{savings:,.0f} vs Old Regime. "
            f"Old Regime needs at least Rs.{breakeven_deduction:,.0f} in total deductions to break even."
        )
    else:
        recommended = "OLD_REGIME"
        summary = f"Old Regime saves Rs.{savings:,.0f} because your deductions (Rs.{old_total_deductions:,.0f}) exceed the Rs.{breakeven_deduction:,.0f} breakeven threshold."

    citations = [
        {"code": "TAX-115BAC", "note": "Budget 2025 New Regime slabs (0% to 30%) + Rs.75k Std Ded"},
        {"code": "TAX-87A-NEW", "note": "Section 87A Rs.60,000 rebate up to Rs.12,00,000 taxable (Rs.12.75L salaried) + marginal relief"},
        {"code": "TAX-BREAKEVEN", "note": f"Algebraic crossover deduction point: Rs.{breakeven_deduction:,.0f}"},
    ]

    return {
        "success": True,
        "gross_income": round(gross, 2),
        "is_salaried": is_salaried,
        "recommended_regime": recommended,
        "net_tax_savings": savings,
        "breakeven_deduction": breakeven_deduction,
        "monthly_take_home": monthly_take_home,
        "summary": summary,
        "new_regime": {
            "standard_deduction": new_std_ded,
            "taxable_income": round(new_taxable, 2),
            "base_tax": round(new_base_tax, 2),
            "rebate_87a": round(new_rebate, 2),
            "marginal_relief": round(new_marginal_relief, 2),
            "cess_4pct": round(new_cess, 2),
            "total_tax": new_total_tax,
            "effective_rate_pct": round((new_total_tax / gross) * 100, 2) if gross > 0 else 0.0,
            "slabs": new_breakdown,
        },
        "old_regime": {
            "total_deductions": round(old_total_deductions, 2),
            "taxable_income": round(old_taxable, 2),
            "base_tax": round(old_base_tax, 2),
            "rebate_87a": round(old_rebate, 2),
            "cess_4pct": round(old_cess, 2),
            "total_tax": old_total_tax,
            "effective_rate_pct": round((old_total_tax / gross) * 100, 2) if gross > 0 else 0.0,
            "slabs": old_breakdown,
        },
        "citations": citations,
    }


def simulate_sip_wealth(
    monthly_sip: float,
    annual_return_pct: float = 12.0,
    years: int = 10,
    annual_step_up_pct: float = 10.0,
    inflation_pct: float = 6.0,
) -> Dict[str, Any]:
    """Simulates step-up monthly SIP wealth accumulation with nominal vs real purchasing power."""
    sip = max(0.0, float(monthly_sip or 0.0))
    yrs = max(1, min(40, int(years or 10)))
    r_month = max(0.0, float(annual_return_pct or 0.0)) / 100.0 / 12.0
    step = max(0.0, float(annual_step_up_pct or 0.0)) / 100.0
    inf = max(0.0, float(inflation_pct or 0.0)) / 100.0

    invested = 0.0
    corpus = 0.0
    cur_sip = sip
    yearly_series: List[Dict[str, Any]] = []

    for yr in range(1, yrs + 1):
        for _ in range(12):
            invested += cur_sip
            corpus = (corpus + cur_sip) * (1.0 + r_month)
        real_val = corpus / ((1.0 + inf) ** yr)
        yearly_series.append({
            "year": yr,
            "monthly_sip": round(cur_sip, 2),
            "invested": round(invested, 2),
            "nominal_value": round(corpus, 2),
            "real_value_today_inr": round(real_val, 2),
        })
        cur_sip *= (1.0 + step)

    return {
        "success": True,
        "years": yrs,
        "total_invested": round(invested, 2),
        "projected_nominal_corpus": round(corpus, 2),
        "projected_real_corpus": yearly_series[-1]["real_value_today_inr"],
        "estimated_wealth_gain": round(corpus - invested, 2),
        "series": yearly_series,
    }


def solve_goal_sip(
    target_corpus_today_inr: float,
    annual_return_pct: float = 12.0,
    years: int = 10,
    inflation_pct: float = 6.0,
) -> Dict[str, Any]:
    """Calculates monthly SIP required to reach an inflation-adjusted financial target."""
    target_real = max(1000.0, float(target_corpus_today_inr or 0.0))
    yrs = max(1, min(40, int(years or 10)))
    r_m = max(0.0, float(annual_return_pct or 0.0)) / 100.0 / 12.0
    inf = max(0.0, float(inflation_pct or 0.0)) / 100.0

    future_nominal_target = target_real * ((1.0 + inf) ** yrs)
    months = yrs * 12
    if r_m == 0:
        req_sip = future_nominal_target / months
    else:
        annuity_factor = (((1.0 + r_m) ** months) - 1.0) / r_m * (1.0 + r_m)
        req_sip = future_nominal_target / annuity_factor

    return {
        "success": True,
        "target_today_inr": round(target_real, 2),
        "inflation_adjusted_target": round(future_nominal_target, 2),
        "required_monthly_sip": round(req_sip, 0),
        "years": yrs,
    }


def estimate_equity_mf_tax(gain_amount: float, holding_months: int = 18) -> Dict[str, Any]:
    """Computes Indian Equity MF capital gains tax under FY 2025-26 rules (STCG 20% <12m, LTCG 12.5% above Rs.1.25L >=12m)."""
    gain = max(0.0, float(gain_amount or 0.0))
    months = max(1, int(holding_months or 1))
    if months >= 12:
        exempt = min(125000.0, gain)
        taxable_gain = max(0.0, gain - exempt)
        base_tax = taxable_gain * 0.125
        kind = "LTCG (12.5% above Rs.1,25,000 exemption)"
    else:
        exempt = 0.0
        taxable_gain = gain
        base_tax = taxable_gain * 0.20
        kind = "STCG (20% under 12 months)"
    total_tax = round(base_tax * 1.04, 2)
    return {
        "success": True,
        "regime_label": kind,
        "gain_amount": round(gain, 2),
        "exempt_amount": round(exempt, 2),
        "taxable_gain": round(taxable_gain, 2),
        "estimated_tax_with_cess": total_tax,
        "post_tax_gain": round(max(0.0, gain - total_tax), 2),
    }


def simulate_ltcg_harvesting(
    portfolio_value: float = 800000.0,
    unrealized_gain: float = 180000.0,
    annual_harvest_limit: float = 125000.0,
    years: int = 5,
    annual_return_pct: float = 12.0,
) -> Dict[str, Any]:
    """Models annual Sec 112A Rs.1.25L zero-tax LTCG harvesting vs unharvested lump-sum redemption."""
    port = max(10000.0, float(portfolio_value or 0.0))
    init_gain = max(0.0, min(port * 0.9, float(unrealized_gain or 0.0)))
    yrs = max(1, min(20, int(years or 5)))
    r = max(0.0, min(30.0, float(annual_return_pct or 0.0))) / 100.0
    limit = max(0.0, float(annual_harvest_limit or 125000.0))

    cost_no_harvest = port - init_gain
    final_port = port * ((1.0 + r) ** yrs)
    total_gain_no_harvest = max(0.0, final_port - cost_no_harvest)
    tax_no_harvest = max(0.0, total_gain_no_harvest - limit) * 0.125 * 1.04

    cur_val = port
    cur_cost = cost_no_harvest
    harvested_total = 0.0
    for _ in range(yrs):
        gain_now = max(0.0, cur_val - cur_cost)
        booked = min(limit, gain_now)
        cur_cost += booked
        harvested_total += booked
        cur_val *= (1.0 + r)

    remaining_gain = max(0.0, cur_val - cur_cost)
    tax_with_harvest = max(0.0, remaining_gain - limit) * 0.125 * 1.04
    saved = max(0.0, tax_no_harvest - tax_with_harvest)

    return {
        "success": True,
        "years": yrs,
        "projected_portfolio": round(final_port, 2),
        "tax_without_harvest": round(tax_no_harvest, 2),
        "tax_with_harvest": round(tax_with_harvest, 2),
        "net_tax_saved": round(saved, 2),
        "total_exempt_step_up": round(harvested_total, 2),
    }


def simulate_emi_prepayment(
    principal: float,
    annual_interest_pct: float,
    tenure_months: int,
    extra_monthly_prepay: float = 0.0,
) -> Dict[str, Any]:
    """Calculates reducing-balance EMI schedule and interest/months saved via extra prepayment."""
    p = max(1.0, float(principal or 0.0))
    n = max(1, min(480, int(tenure_months or 12)))
    r = max(0.0, float(annual_interest_pct or 0.0)) / 100.0 / 12.0
    extra = max(0.0, float(extra_monthly_prepay or 0.0))

    if r == 0:
        base_emi = p / n
    else:
        factor = (1.0 + r) ** n
        base_emi = p * r * factor / (factor - 1.0)

    baseline_interest = max(0.0, (base_emi * n) - p)
    bal = p
    months_with_prepay = 0
    total_interest_prepay = 0.0
    while bal > 0.01 and months_with_prepay < n * 2:
        months_with_prepay += 1
        interest_m = bal * r
        principal_m = min(bal, (base_emi - interest_m) + extra)
        total_interest_prepay += interest_m
        bal -= principal_m

    return {
        "success": True,
        "monthly_emi": round(base_emi, 2),
        "baseline_months": n,
        "baseline_total_interest": round(baseline_interest, 2),
        "prepay_months": months_with_prepay,
        "prepay_total_interest": round(total_interest_prepay, 2),
        "months_saved": max(0, n - months_with_prepay),
        "interest_saved": round(max(0.0, baseline_interest - total_interest_prepay), 2),
    }
