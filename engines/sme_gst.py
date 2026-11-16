"""Small business Indian GST invoicing and 90-day working-capital runway analyzer."""
from __future__ import annotations

from typing import Any, Dict, List

VALID_GST_RATES = (0.0, 5.0, 12.0, 18.0, 28.0)


def _nearest_gst_slab(rate: float) -> float:
    return min(VALID_GST_RATES, key=lambda r: abs(r - rate))


def compute_gst_and_cashflow(
    items: List[Dict[str, Any]],
    supply_type: str = "intra_state",
    input_tax_credit: float = 0.0,
    opening_cash: float = 120000.0,
    monthly_fixed_costs: float = 48000.0,
    expected_monthly_collections: float = 95000.0,
    pending_receivables: float = 65000.0,
) -> Dict[str, Any]:
    """Computes CGST/SGST vs IGST invoice totals, net GST after ITC, and 90-day cash runway."""
    mode = "inter_state" if str(supply_type).lower() == "inter_state" else "intra_state"
    computed_lines: List[Dict[str, Any]] = []

    taxable_subtotal = 0.0
    total_gst = 0.0

    for idx, item in enumerate(items or [], 1):
        desc = str(item.get("name", f"Line Item {idx}")).strip()[:80] or f"Line Item {idx}"
        qty = max(1.0, float(item.get("qty", 1) or 1))
        unit_price = max(0.0, float(item.get("unit_price", 0) or 0))
        slab = _nearest_gst_slab(float(item.get("gst_rate", 18) or 0))

        base_amt = qty * unit_price
        gst_amt = base_amt * (slab / 100.0)
        cgst = gst_amt / 2.0 if mode == "intra_state" else 0.0
        sgst = gst_amt / 2.0 if mode == "intra_state" else 0.0
        igst = gst_amt if mode == "inter_state" else 0.0

        taxable_subtotal += base_amt
        total_gst += gst_amt
        computed_lines.append({
            "line_id": f"INV-{idx:02d}",
            "name": desc,
            "qty": qty,
            "unit_price": round(unit_price, 2),
            "taxable_value": round(base_amt, 2),
            "gst_rate_pct": slab,
            "cgst": round(cgst, 2),
            "sgst": round(sgst, 2),
            "igst": round(igst, 2),
            "line_total": round(base_amt + gst_amt, 2),
        })

    itc = max(0.0, float(input_tax_credit or 0.0))
    itc_utilized = min(total_gst, itc)
    net_gst_payable = max(0.0, total_gst - itc_utilized)
    itc_carry_forward = max(0.0, itc - itc_utilized)

    cash = max(0.0, float(opening_cash or 0.0))
    fixed_m = max(1.0, float(monthly_fixed_costs or 1.0))
    coll_m = max(0.0, float(expected_monthly_collections or 0.0))
    receivables = max(0.0, float(pending_receivables or 0.0))

    # 3-month projection: Base vs 35% receivable delay stress test
    projection: List[Dict[str, Any]] = []
    base_bal = cash
    stress_bal = cash
    for m in range(1, 4):
        recv_tranche = receivables * 0.35 if m == 1 else 0.0
        gst_outflow = net_gst_payable if m == 1 else 0.0
        base_bal = base_bal + coll_m + recv_tranche - fixed_m - gst_outflow
        stress_bal = stress_bal + (coll_m * 0.65) - fixed_m - gst_outflow
        projection.append({
            "month": f"Month +{m}",
            "base_cash": round(base_bal, 2),
            "delayed_receivables_cash": round(stress_bal, 2),
        })

    net_burn_stress = max(0.0, fixed_m - (coll_m * 0.65))
    runway_days = round((cash / (net_burn_stress / 30.0)), 0) if net_burn_stress > 0 else 365

    return {
        "success": True,
        "supply_type": mode,
        "lines": computed_lines,
        "taxable_subtotal": round(taxable_subtotal, 2),
        "gross_gst": round(total_gst, 2),
        "itc_utilized": round(itc_utilized, 2),
        "net_gst_payable": round(net_gst_payable, 2),
        "itc_carry_forward": round(itc_carry_forward, 2),
        "grand_invoice_total": round(taxable_subtotal + total_gst, 2),
        "stress_runway_days": int(min(365, runway_days)),
        "projection_90d": projection,
        "citations": [
            {"code": "GST-CGST-SGST", "note": f"{'Intra-state 50/50 CGST+SGST split' if mode == 'intra_state' else 'Inter-state 100% IGST'}"},
            {"code": "GST-ITC-SET", "note": f"Input Tax Credit Rs.{itc_utilized:,.0f} offset against output liability"},
            {"code": "WC-STRESS-90D", "note": "35% delayed-receivable working capital stress buffer"},
        ],
    }
