"""End-to-end HTTP integration and security tests for ArthaLedger server."""
from __future__ import annotations

import json
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import make_server


class TestArthaLedgerHttpApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.15)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.server.shutdown()
            cls.server.server_close()
        except Exception:
            pass

    def _post(self, path: str, payload: dict) -> tuple[int, dict]:
        req = urllib.request.Request(
            f"{self.base}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    def test_ui_assets_security_headers_and_traversal_block(self):
        for route in ["/", "/static/styles.css", "/static/app.js", "/api/health", "/api/personas"]:
            with urllib.request.urlopen(f"{self.base}{route}", timeout=6) as r:
                self.assertEqual(r.status, 200)
                self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")
                self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertIn("script-src 'self'", r.headers.get("Content-Security-Policy", ""))

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{self.base}/static/../../app.py", timeout=5)
        self.assertEqual(ctx.exception.code, 403)

    def test_all_finance_endpoints_work_end_to_end(self):
        s_code, ledger = self._post("/api/ledger/analyze", {
            "raw_text": "Credited Rs.10000 Allowance\nDebited Rs.500 via UPI to Swiggy on 05-Nov",
            "monthly_budget_target": 5000,
        })
        self.assertEqual(s_code, 200)
        self.assertEqual(ledger["total_spent"], 500.0)

        f_code, fraud = self._post("/api/fraud/audit", {
            "payload_text": "upi://pay?pa=refund@okexample&am=9999&tn=Enter UPI PIN",
        })
        self.assertEqual(f_code, 200)
        self.assertEqual(fraud["verdict"], "HIGH_RISK_SCAM")

        t_code, tax = self._post("/api/tax/compare", {"gross_income": 1275000, "is_salaried": True})
        self.assertEqual(t_code, 200)
        self.assertEqual(tax["new_regime"]["total_tax"], 0.0)

        m_code, bt = self._post("/api/market/backtest", {"symbol": "NIFTY50_PROXY", "strategy": "sma_crossover"})
        self.assertEqual(m_code, 200)
        self.assertTrue(bt["paper_trading_only"])

        g_code, gst = self._post("/api/sme/gst", {
            "supply_type": "inter_state",
            "input_tax_credit": 500,
            "items": [{"name": "Service", "qty": 1, "unit_price": 10000, "gst_rate": 18}],
        })
        self.assertEqual(g_code, 200)
        self.assertEqual(gst["net_gst_payable"], 1300.0)

        c_code, copilot = self._post("/api/copilot/ask", {
            "question": "Summarize my financial health",
            "provider": "deterministic",
            "context": {"ledger": ledger, "fraud": fraud, "tax": tax, "backtest": bt, "sme": gst},
        })
        self.assertEqual(c_code, 200)
        self.assertTrue(copilot["success"])
        self.assertIn("TAX-115BAC", copilot["citations"])


if __name__ == "__main__":
    unittest.main()
