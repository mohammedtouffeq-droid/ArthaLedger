"""Indian Income Tax Optimizer (Old vs New Regime Budget 2025), SIP Wealth & Loan EMI Engine."""
from __future__ import annotations

from typing import Any, Dict, List


def _progressive_slab_tax(taxable: float, slabs: List[tuple[float, float]]) -> tuple[float, List[Dict[str, Any]]]:
    """Computes progressive slab-by-slab Indian income tax with itemized trace."""
    remaining = max(0.0, taxable)
    prev_limit = 0.0
    total = 0.0
    breakdown: List[Dict[str, Any]] = []

    for upper, rate in slabs:
        if remaining <= prev_limit:
            break
        slice_top = min(remaining, upper)
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
    Compares Indian Old Regime vs New Regime (Section 115BAC, Union Budget 2025 FY 2025-26 / 2026-27):
    New Regime slabs: 0-4L:0%, 4-8L:5%, 8-12L:10%, 12-16L:15%, 16-20L:20%, 20-24L:25%, >24L:30%.
    Salaried Standard Deduction: Rs.75,000 (New), Rs.50,000 (Old).
    Sec 87A Rebate: up to Rs.60,000 when taxable <= Rs.12,00,000 (with marginal relief above 12L) in New Regime;
                    up to Rs.12,500 when taxable <= Rs.5,00,000 in Old Regime. Cess = 4%.
    """
    gross = max(0.0, float(gross_income or 0.0))

    # --- NEW REGIME (Budget 2025, FY 2025-26 / FY 2026-27) ---
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
        # Marginal relief: tax cannot exceed excess income above Rs.12,00,000
        excess_over_12l = new_taxable - 1200000.0
        if new_base_tax > excess_over_12l:
            new_marginal_relief = new_base_tax - excess_over_12l
            new_tax_after_rebate = excess_over_12l
        else:
            new_tax_after_rebate = new_base_tax

    new_cess = new_tax_after_rebate * 0.04
    new_total_tax = round(new_tax_after_rebate + new_cess, 2)

    # --- OLD REGIME ---
    old_std_ded = 50000.0 if is_salaried and gross > 0 else 0.0
    cap_80c = min(150000.0, max(0.0, float(deduction_80c or 0.0)))
    cap_80d = min(100000.0, max(0.0, float(deduction_80d or 0.0)))
    cap_hra = max(0.0, float(hra_exemption or 0.0))
    cap_hl = min(200000.0, max(0.0, float(home_loan_interest or 0.0)))
    cap_nps = min(50000.0, max(0.0, float(nps_80ccd1b or 0.0)))
    old_total_deductions = old_std_ded + cap_80c + cap_80d + cap_hra + cap_hl + cap_nps

    old_taxable = max(0.0, gross - old_total_deductions)
    old_slabs = [
        (250000.0, 0.00),
        (500000.0, 0.05),
        (1000000.0, 0.20),
        (float("inf"), 0.30),
    ]
    old_base_tax, old_breakdown = _progressive_slab_tax(old_taxable, old_slabs)
    old_rebate = min(12500.0, old_base_tax) if old_taxable <= 500000.0 else 0.0
    old_after_rebate = max(0.0, old_base_tax - old_rebate)
    old_cess = old_after_rebate * 0.04
    old_total_tax = round(old_after_rebate + old_cess, 2)

    savings = round(abs(old_total_tax - new_total_tax), 2)
    if new_total_tax <= old_total_tax:
        recommended = "NEW_REGIME"
        summary = (
            f"New Regime (Sec 115BAC) saves Rs.{savings:,.0f} vs Old Regime on gross income Rs.{gross:,.0f}."
            if savings > 0
            else f"Both regimes result in identical net tax Rs.{new_total_tax:,.0f}."
        )
    else:
        recommended = "OLD_REGIME"
        summary = f"Old Regime saves Rs.{savings:,.0f} vs New Regime due to Rs.{old_total_deductions:,.0f} claimed deductions."

    citations = [
        {"code": "TAX-115BAC", "note": "New Regime FY 2025-26/26-27 progressive slabs (0% to 30%), Standard Deduction Rs.75,000"},
        {"code": "TAX-87A-NEW", "note": "Section 87A full rebate up to Rs.12,00,000 taxable income (Rs.12,75,000 salaried) + marginal relief"},
        {"code": "TAX-OLD-DED", "note": "Old Regime deductions: Std Ded Rs.50k, 80C cap Rs.1.5L, 80CCD(1B) Rs.50k, 80D, 24(b), HRA"},
    ]

    return {
        "success": True,
        "gross_income": round(gross, 2),
        "is_salaried": is_salaried,
        "recommended_regime": recommended,
        "net_tax_savings": savings,
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

    baseline_total_paid = base_emi * n
    baseline_interest = max(0.0, baseline_total_paid - p)

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
