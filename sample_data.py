"""100% synthetic Indian financial persona packs for ArthaLedger (zero real PII)."""
from __future__ import annotations

from typing import Any, Dict, List

PERSONAS: Dict[str, Dict[str, Any]] = {
    "student_budget": {
        "id": "student_budget",
        "name": "Student Monthly Budget (Rs.18,500 Allowance)",
        "tagline": "Track hostel/college UPI burn, detect stealth subscriptions, start Rs.2,000 SIP",
        "monthly_budget_target": 15000,
        "sms_ledger": "\n".join([
            "Credited Rs.15000.00 via IMPS from Guardian Allowance on 01-Nov-2026.",
            "Credited Rs.3500.00 towards Freelance Web Landing Page Settlement on 04-Nov-2026.",
            "Debited Rs.180.00 via UPI to Campus Canteen Tiffin on 02-Nov-2026.",
            "Debited Rs.449.00 via UPI to Swiggy Instamart Order on 03-Nov-2026.",
            "Debited Rs.199.00 via UPI Autodebit to Spotify Premium Subscription on 05-Nov-2026.",
            "Debited Rs.699.00 via UPI to Jio Fiber Broadband Recharge on 06-Nov-2026.",
            "Debited Rs.649.00 via UPI Autodebit to Cloud Streaming Bundle Subscription on 07-Nov-2026.",
            "Debited Rs.2150.00 via UPI to Engineering Textbooks & Lab Printouts on 09-Nov-2026.",
            "Debited Rs.320.00 via UPI to Metro Rail Transit Pass on 10-Nov-2026.",
            "Debited Rs.890.00 via UPI to Zomato Weekend Group Order on 12-Nov-2026.",
            "Debited Rs.5200.00 via UPI to Hostel Mess & Room Rent Share on 14-Nov-2026.",
            "Debited Rs.260.00 via UPI to Blinkit Late-Night Snacks on 15-Nov-2026.",
        ]),
        "fraud_sample": "URGENT KYC ALERT: Your demo savings account will be BLOCKED within 24 hours. Click http://sbi-kyc-verify-demo.example/update and enter UPI PIN to claim Rs.4,999 cashback.",
        "tax_inputs": {
            "gross_income": 222000,
            "is_salaried": False,
            "deduction_80c": 0,
            "deduction_80d": 0,
            "hra_exemption": 0,
            "home_loan_interest": 0,
            "nps_80ccd1b": 0,
        },
        "sip_inputs": {
            "monthly_sip": 2000,
            "annual_return_pct": 12.0,
            "years": 12,
            "annual_step_up_pct": 15.0,
            "inflation_pct": 6.0,
        },
        "emi_inputs": {
            "principal": 180000,
            "annual_interest_pct": 9.5,
            "tenure_months": 36,
            "extra_monthly_prepay": 1000,
        },
    },
    "salaried_investor": {
        "id": "salaried_investor",
        "name": "Early-Career Engineer (Rs.14.5L CTC)",
        "tagline": "Optimize FY25-26 Old vs New Tax Regime, calibrate 80C/NPS, simulate home loan prepayment",
        "monthly_budget_target": 58000,
        "sms_ledger": "\n".join([
            "Credited Rs.98500.00 Salary from Acme Software India Pvt Ltd on 01-Nov-2026.",
            "Debited Rs.24000.00 via NEFT to Landlord Rent Transfer on 02-Nov-2026.",
            "Debited Rs.4850.00 via UPI to BESCOM & Utility Bills on 03-Nov-2026.",
            "Debited Rs.1650.00 via UPI to Blinkit Weekly Groceries on 05-Nov-2026.",
            "Debited Rs.1499.00 via UPI Autodebit to GitHub Copilot & Cloud Hosting on 06-Nov-2026.",
            "Debited Rs.2350.00 via UPI to Indian Oil Fuel Pump on 08-Nov-2026.",
            "Debited Rs.1920.00 via UPI to Swiggy Dineout on 10-Nov-2026.",
            "Debited Rs.18900.00 via UPI to Croma Monitor Upgrade Purchase on 12-Nov-2026.",
            "Debited Rs.1420.00 via UPI to BigBasket Monthly Pantry on 14-Nov-2026.",
        ]),
        "fraud_sample": "upi://pay?pa=helpdesk-tax-refund@okexample&pn=IncomeTax%20Instant%20Refund&am=14500&mode=02&tn=Verify%20PIN%20to%20Receive%20Refund",
        "tax_inputs": {
            "gross_income": 1450000,
            "is_salaried": True,
            "deduction_80c": 150000,
            "deduction_80d": 25000,
            "hra_exemption": 180000,
            "home_loan_interest": 0,
            "nps_80ccd1b": 50000,
        },
        "sip_inputs": {
            "monthly_sip": 22000,
            "annual_return_pct": 12.5,
            "years": 15,
            "annual_step_up_pct": 10.0,
            "inflation_pct": 6.0,
        },
        "emi_inputs": {
            "principal": 3500000,
            "annual_interest_pct": 8.65,
            "tenure_months": 240,
            "extra_monthly_prepay": 5000,
        },
    },
    "sme_retailer": {
        "id": "sme_retailer",
        "name": "Local Trader & Services SME (GST & Cashflow)",
        "tagline": "Compute CGST/SGST after Input Tax Credit and stress-test 90-day receivables",
        "monthly_budget_target": 110000,
        "sms_ledger": "\n".join([
            "Credited Rs.64000.00 towards Client B2B Settlement on 02-Nov-2026.",
            "Credited Rs.52500.00 towards Counter UPI Merchant Batch on 07-Nov-2026.",
            "Debited Rs.42000.00 towards Wholesale Inventory Supplier on 03-Nov-2026.",
            "Debited Rs.18000.00 towards Shop Rent Transfer on 05-Nov-2026.",
            "Debited Rs.6400.00 towards Commercial Electricity Board on 08-Nov-2026.",
            "Debited Rs.22000.00 towards Delivery Staff Stipend & Transport on 10-Nov-2026.",
            "Debited Rs.4200.00 towards Packaging & Thermal Printer Rolls on 12-Nov-2026.",
        ]),
        "fraud_sample": "Congratulations! Merchant QR cashback lottery Rs.25,000 approved. Install AnyDesk remote access support app and approve Rs.12,500 collect request.",
        "tax_inputs": {
            "gross_income": 1200000,
            "is_salaried": False,
            "deduction_80c": 120000,
            "deduction_80d": 25000,
            "hra_exemption": 0,
            "home_loan_interest": 0,
            "nps_80ccd1b": 0,
        },
        "sip_inputs": {
            "monthly_sip": 15000,
            "annual_return_pct": 11.5,
            "years": 10,
            "annual_step_up_pct": 8.0,
            "inflation_pct": 6.0,
        },
        "emi_inputs": {
            "principal": 600000,
            "annual_interest_pct": 11.2,
            "tenure_months": 48,
            "extra_monthly_prepay": 3000,
        },
        "sme_inputs": {
            "supply_type": "intra_state",
            "input_tax_credit": 6800,
            "opening_cash": 145000,
            "monthly_fixed_costs": 62000,
            "expected_monthly_collections": 108000,
            "pending_receivables": 72000,
            "items": [
                {"name": "Retail Point-of-Sale Hardware Bundle", "qty": 2, "unit_price": 18500, "gst_rate": 18},
                {"name": "Barcode Scanner & Setup Calibration", "qty": 4, "unit_price": 3200, "gst_rate": 18},
                {"name": "Thermal Billing Paper Packs", "qty": 10, "unit_price": 450, "gst_rate": 12},
            ],
        },
    },
}


def list_personas_summary() -> List[Dict[str, str]]:
    return [
        {"id": p["id"], "name": p["name"], "tagline": p["tagline"]}
        for p in PERSONAS.values()
    ]
