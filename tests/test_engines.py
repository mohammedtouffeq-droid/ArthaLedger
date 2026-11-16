"""Unit tests for all deterministic Indian finance computation engines in ArthaLedger."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.copilot import ask_financial_copilot
from engines.fraud_shield import analyze_payment_risk
from engines.market_backtest import run_paper_backtest
from engines.sme_gst import compute_gst_and_cashflow
from engines.sms_ledger import export_ledger_csv, parse_sms_ledger
from engines.tax_wealth import calculate_indian_tax, simulate_emi_prepayment, simulate_sip_wealth


class TestFinancialEngines(unittest.TestCase):
    def test_tax_new_regime_salaried_12_75_lakh_zero_tax(self):
        # Salaried Rs.12,75,000 - Rs.75,000 Std Ded = Rs.12,00,000 taxable -> full 87A rebate -> Rs.0 tax
        res = calculate_indian_tax(gross_income=1275000, is_salaried=True)
        self.assertTrue(res["success"])
        self.assertEqual(res["new_regime"]["taxable_income"], 1200000.0)
        self.assertEqual(res["new_regime"]["base_tax"], 60000.0)
        self.assertEqual(res["new_regime"]["rebate_87a"], 60000.0)
        self.assertEqual(res["new_regime"]["total_tax"], 0.0)
        self.assertEqual(res["recommended_regime"], "NEW_REGIME")

    def test_tax_new_regime_marginal_relief_just_above_12_lakh(self):
        # Taxable Rs.12,10,000 -> base slab tax would be Rs.61,500; marginal relief caps pre-cess tax at Rs.10,000
        res = calculate_indian_tax(gross_income=1210000, is_salaried=False)
        self.assertEqual(res["new_regime"]["taxable_income"], 1210000.0)
        self.assertGreater(res["new_regime"]["marginal_relief"], 0.0)
        self.assertEqual(res["new_regime"]["total_tax"], 10400.0)  # 10000 + 4% cess

    def test_tax_old_regime_can_win_with_heavy_deductions(self):
        res = calculate_indian_tax(
            gross_income=2000000,
            is_salaried=True,
            deduction_80c=150000,
            deduction_80d=50000,
            hra_exemption=300000,
            home_loan_interest=200000,
            nps_80ccd1b=50000,
        )
        self.assertEqual(res["old_regime"]["total_deductions"], 800000.0)
        self.assertLess(res["old_regime"]["total_tax"], res["new_regime"]["total_tax"])
        self.assertEqual(res["recommended_regime"], "OLD_REGIME")

    def test_sms_ledger_parses_credits_debits_anomalies_and_csv(self):
        feed = "\n".join([
            "Credited Rs.20000.00 Salary from Example Corp on 01-Nov-2026.",
            "Debited Rs.200.00 via UPI to Metro Transit on 02-Nov-2026.",
            "Debited Rs.250.00 via UPI to Canteen Tiffin on 03-Nov-2026.",
            "Debited Rs.199.00 via UPI to Spotify Premium on 04-Nov-2026.",
            "Debited Rs.5000.00 via UPI to Croma Purchase on 05-Nov-2026.",
        ])
        res = parse_sms_ledger(feed, monthly_budget_target=10000)
        self.assertEqual(res["transaction_count"], 5)
        self.assertEqual(res["total_income"], 20000.0)
        self.assertEqual(res["total_spent"], 5649.0)
        self.assertEqual(res["net_cashflow"], 14351.0)
        citations = {a["citation"] for a in res["anomalies"]}
        self.assertIn("TXN-04", citations)  # subscription flagged
        self.assertIn("TXN-05", citations)  # outlier spend flagged
        csv_txt = export_ledger_csv(res["transactions"])
        self.assertIn("Citation ID,Date,Type,Category", csv_txt)
        self.assertIn("TXN-05", csv_txt)

    def test_fraud_shield_detects_phishing_collect_scam_and_safe_uri(self):
        scam = analyze_payment_risk(
            "upi://pay?pa=kyc-refund@okexample&pn=Customer%20Support&am=15000&tn=Enter%20UPI%20PIN%20to%20receive%20refund",
            claimed_context="Caller asked for KYC verification",
        )
        self.assertEqual(scam["verdict"], "HIGH_RISK_SCAM")
        self.assertGreaterEqual(scam["risk_score"], 55)
        self.assertTrue(len(scam["flags"]) >= 3)

        safe = analyze_payment_risk("upi://pay?pa=metro.transit@okaxis&pn=City%20Metro&am=100&tn=Pass")
        self.assertEqual(safe["verdict"], "LOW_RISK")
        self.assertLess(safe["risk_score"], 25)

    def test_sip_emi_backtest_and_sme_gst(self):
        sip = simulate_sip_wealth(10000, annual_return_pct=12.0, years=10, annual_step_up_pct=10.0)
        self.assertTrue(sip["success"])
        self.assertGreater(sip["projected_nominal_corpus"], sip["total_invested"])
        self.assertGreater(sip["projected_nominal_corpus"], sip["projected_real_corpus"])

        emi = simulate_emi_prepayment(1000000, 9.0, 120, extra_monthly_prepay=5000)
        self.assertGreater(emi["months_saved"], 0)
        self.assertGreater(emi["interest_saved"], 0)

        bt = run_paper_backtest(symbol="NIFTY50_PROXY", strategy="sma_crossover", initial_capital=100000)
        self.assertTrue(bt["paper_trading_only"])
        self.assertEqual(bt["periods"], 36)
        self.assertGreater(bt["final_equity"], 0)

        gst = compute_gst_and_cashflow(
            items=[{"name": "Hardware", "qty": 2, "unit_price": 10000, "gst_rate": 18}],
            supply_type="intra_state",
            input_tax_credit=1000,
        )
        self.assertEqual(gst["taxable_subtotal"], 20000.0)
        self.assertEqual(gst["gross_gst"], 3600.0)
        self.assertEqual(gst["net_gst_payable"], 2600.0)
        self.assertEqual(gst["lines"][0]["cgst"], 1800.0)
        self.assertEqual(gst["lines"][0]["sgst"], 1800.0)

    def test_copilot_deterministic_grounding_without_keys(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "", "BHARATCODE_API_KEY": ""}, clear=False):
            ctx = {
                "tax": calculate_indian_tax(1275000, is_salaried=True),
                "fraud": analyze_payment_risk("URGENT KYC http://bit.ly/fake enter UPI pin"),
            }
            res = ask_financial_copilot("Summarize my tax and scam risk", context=ctx, provider="auto")
        self.assertTrue(res["success"])
        self.assertEqual(res["provider_used"], "deterministic")
        self.assertIn("TAX-115BAC", res["citations"])
        self.assertIn("Rs.0", res["reply"])


if __name__ == "__main__":
    unittest.main()
