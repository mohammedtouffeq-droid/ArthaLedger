"""Unit tests for all deterministic Indian finance computation engines in ArthaLedger."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.copilot import ask_financial_copilot, compute_financial_health_score
from engines.fraud_shield import analyze_payment_risk, decode_qr_from_bytes, generate_sample_qr_png
from engines.market_backtest import compare_amfi_funds, run_paper_backtest, search_amfi_funds, simulate_direct_vs_regular
from engines.sme_gst import compute_gst_and_cashflow
from engines.sms_ledger import csv_statement_to_lines, export_ledger_csv, parse_sms_ledger
from engines.tax_wealth import (
    calculate_indian_tax,
    estimate_equity_mf_tax,
    simulate_emi_prepayment,
    simulate_ltcg_harvesting,
    simulate_sip_wealth,
    solve_goal_sip,
)


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
            "Credited Rs.15000.00 via IMPS from Guardian Allowance on 02-Nov-2026.",
            "Debited Rs.200.00 via UPI to Metro Transit on 02-Nov-2026.",
            "Debited Rs.250.00 via UPI to Canteen Tiffin on 03-Nov-2026.",
            "Debited Rs.199.00 via UPI Autodebit to Spotify Premium Subscription on 04-Nov-2026.",
            "Debited Rs.5000.00 via UPI to Croma Purchase on 05-Nov-2026.",
        ])
        res = parse_sms_ledger(feed, monthly_budget_target=10000)
        self.assertEqual(res["transaction_count"], 6)
        self.assertEqual(res["total_income"], 35000.0)
        self.assertEqual(res["total_spent"], 5649.0)
        self.assertEqual(res["subscription_annual_runrate"], 2388.0)
        self.assertEqual(res["transactions"][1]["merchant"], "Guardian Allowance")
        self.assertEqual(res["transactions"][4]["category"], "Subscriptions & Cloud")
        citations = {a["citation"] for a in res["anomalies"]}
        self.assertIn("TXN-05", citations)
        self.assertIn("TXN-06", citations)
        csv_txt = export_ledger_csv(res["transactions"])
        self.assertIn("Citation ID,Date,Type,Category", csv_txt)
        self.assertIn("TXN-06", csv_txt)

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

    def test_v2_csv_breakeven_amfi_direct_drag_and_health_score(self):
        csv_raw = "Date,Description,Debit,Credit\n01-Nov-2026,Allowance,,15000\n02-Nov-2026,Spotify,199,\n"
        lines = csv_statement_to_lines(csv_raw)
        parsed = parse_sms_ledger(lines, monthly_budget_target=10000)
        self.assertEqual(parsed["total_income"], 15000.0)
        self.assertEqual(parsed["total_spent"], 199.0)
        self.assertEqual(parsed["subscription_annual_runrate"], 2388.0)

        tax = calculate_indian_tax(gross_income=1600000, is_salaried=True)
        self.assertGreater(tax["breakeven_deduction"], 200000.0)
        self.assertGreater(tax["monthly_take_home"], 100000.0)

        drag = simulate_direct_vs_regular(monthly_sip=15000, years=15)
        self.assertGreater(drag["commission_leakage"], 400000.0)

        mf = search_amfi_funds("")
        self.assertTrue(mf["success"])
        self.assertGreaterEqual(len(mf["funds"]), 4)

        scam = analyze_payment_risk("upi://pay?pa=kyc-helpdesk@okexample&am=9999&tn=Enter UPI PIN")
        self.assertTrue(any(a["field"] == "PIN-For-Receipt Trap" and a["value"] == "DETECTED" for a in scam["anatomy"]))

        health = compute_financial_health_score({"ledger": parsed, "fraud": scam, "tax": tax, "backtest": {"sharpe_ratio": 1.1}})
        self.assertGreaterEqual(health["score"], 60)
        self.assertLessEqual(health["score"], 100)

        # Verify AMFI scheme backtest parsing cleanly with mocked AMFI payload
        sample_amfi = json.dumps({
            "meta": {"scheme_name": "Test Nifty 50 Index Direct"},
            "data": [{"date": f"{d:02d}-01-2026", "nav": str(100 + (20 - d) * 0.8)} for d in range(1, 21)],
        }).encode("utf-8")

        class _FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return sample_amfi

        with patch("engines.market_backtest.urllib.request.urlopen", return_value=_FakeResp()):
            amfi_bt = run_paper_backtest(amfi_scheme_code="999120", strategy="sma_crossover", initial_capital=100000)
        self.assertEqual(amfi_bt["data_source"], "live_amfi_public_nav")
        self.assertEqual(amfi_bt["periods"], 20)
        self.assertGreater(amfi_bt["final_equity"], 0)

        with patch.dict("os.environ", {"GEMINI_API_KEY": "", "BHARATCODE_API_KEY": ""}, clear=False):
            yo_res = ask_financial_copilot("yoo", context={"ledger": parsed, "fraud": scam}, provider="auto")
        self.assertNotIn("SME Invoice", yo_res["reply"])
        self.assertIn("Live Telemetry Loaded", yo_res["reply"])

    def test_v3_fraud_apk_homoglyph_goal_sip_and_capital_gains(self):
        apk_scam = analyze_payment_risk("URGENT: Download eChallan_RTO_Verify.apk or call 9876543210 for KYC helpline")
        self.assertEqual(apk_scam["verdict"], "HIGH_RISK_SCAM")
        apk_ids = [f["citation"] for f in apk_scam["flags"]]
        self.assertIn("FRAUD-APK-01", apk_ids)
        self.assertIn("FRAUD-TEL-01", apk_ids)

        homo_scam = analyze_payment_risk("Update \u200bsbi KYC now")
        homo_ids = [f["citation"] for f in homo_scam["flags"]]
        self.assertIn("FRAUD-HOMO-01", homo_ids)

        goal = solve_goal_sip(target_corpus_today_inr=1000000, annual_return_pct=12.0, years=10, inflation_pct=6.0)
        self.assertTrue(goal["success"])
        self.assertGreater(goal["inflation_adjusted_target"], 1000000)
        self.assertGreater(goal["required_monthly_sip"], 0)

        ltcg = estimate_equity_mf_tax(gain_amount=225000, holding_months=18)
        self.assertEqual(ltcg["exempt_amount"], 125000.0)
        self.assertEqual(ltcg["estimated_tax_with_cess"], 13000.0)

        stcg = estimate_equity_mf_tax(gain_amount=100000, holding_months=6)
        self.assertEqual(stcg["exempt_amount"], 0.0)
        self.assertEqual(stcg["estimated_tax_with_cess"], 20800.0)

    def test_v4_qr_roundtrip_multibank_csv_compare_funds_and_ltcg_harvesting(self):
        scam_png = generate_sample_qr_png("scam")
        self.assertGreater(len(scam_png), 200)
        decoded_uri = decode_qr_from_bytes(scam_png)
        self.assertIn("cashback-helpdesk@okexample", decoded_uri)
        scam_res = analyze_payment_risk(decoded_uri)
        self.assertEqual(scam_res["verdict"], "HIGH_RISK_SCAM")

        hdfc_tsv = (
            "Account Statement for 0042XXXXXX\n"
            "Date\tNarration\tWithdrawal Amt.\tDeposit Amt.\n"
            "01/11/2026\tNEFT CLIENT SETTLEMENT\t\t45000.00\n"
            "02/11/2026\tSPOTIFY AUTODEBIT\t199.00\t\n"
        )
        parsed = parse_sms_ledger(hdfc_tsv, monthly_budget_target=10000)
        self.assertEqual(parsed["transaction_count"], 2)
        self.assertEqual(parsed["total_income"], 45000.0)
        self.assertEqual(parsed["total_spent"], 199.0)

        hv = simulate_ltcg_harvesting(portfolio_value=900000, unrealized_gain=200000, annual_harvest_limit=125000, years=5, annual_return_pct=12.0)
        self.assertTrue(hv["success"])
        self.assertGreater(hv["net_tax_saved"], 0)
        self.assertLess(hv["tax_with_harvest"], hv["tax_without_harvest"])

        fake_nav = json.dumps({
            "meta": {"scheme_name": "Sample Equity Fund"},
            "data": [{"date": f"{d:02d}-01-2026", "nav": str(100 + (20 - d) * 0.9)} for d in range(1, 21)],
        }).encode("utf-8")

        class _MockResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return fake_nav

        with patch("engines.market_backtest.urllib.request.urlopen", return_value=_MockResp()):
            cmp_res = compare_amfi_funds("120716", "122639")
        self.assertTrue(cmp_res["success"])
        self.assertEqual(cmp_res["periods"], 20)
        self.assertIn("correlation", cmp_res)
        self.assertEqual(cmp_res["series"][0]["fund_a_indexed"], 100.0)


if __name__ == "__main__":
    unittest.main()
