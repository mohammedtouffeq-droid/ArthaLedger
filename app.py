"""ArthaLedger AI HTTP server and Vercel-compatible request handler."""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from engines.copilot import ask_financial_copilot
from engines.fraud_shield import analyze_payment_risk
from engines.market_backtest import BENCHMARK_SERIES, run_paper_backtest
from engines.sme_gst import compute_gst_and_cashflow
from engines.sms_ledger import export_ledger_csv, parse_sms_ledger
from engines.tax_wealth import calculate_indian_tax, simulate_emi_prepayment, simulate_sip_wealth
from sample_data import PERSONAS, list_personas_summary

STATIC_DIR = ROOT_DIR / "static"
MAX_BODY_BYTES = 6 * 1024 * 1024  # 6 MB ceiling for multimodal screenshot audit payloads

STATIC_MIME_TYPES: Dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}

CSP_VALUE = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
)


def _safe_static_path(rel_path: str) -> Optional[Path]:
    clean = str(rel_path or "").strip().lstrip("/")
    if not clean or clean in (".", ".."):
        clean = "index.html"
    try:
        base_resolved = STATIC_DIR.resolve()
        candidate = (base_resolved / clean).resolve()
        candidate.relative_to(base_resolved)
        return candidate
    except (OSError, ValueError):
        return None


def _num(val: Any, default: float = 0.0) -> float:
    try:
        parsed = float(val)
        return default if parsed != parsed else parsed
    except (TypeError, ValueError):
        return default


def _int_val(val: Any, default: int = 0) -> int:
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


class ArthaLedgerHandler(BaseHTTPRequestHandler):
    """Serves static institutional fintech UI and deterministic/AI JSON endpoints."""

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP_VALUE)

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(raw)

    def _send_bytes(self, data: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> tuple[Optional[Dict[str, Any]], int]:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            return None, 400
        if length < 0 or length > MAX_BODY_BYTES:
            return None, 413
        if length == 0:
            return {}, 200
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, 400
        if not isinstance(parsed, dict):
            return None, 400
        return parsed, 200

    def _resolve_path(self) -> tuple[str, Dict[str, list[str]]]:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        req_path = parsed.path
        if "__artha_path__" in query and query["__artha_path__"]:
            req_path = "/" + str(query["__artha_path__"][0]).lstrip("/")
        return req_path, query

    def do_GET(self) -> None:
        path, query = self._resolve_path()

        if path == "/api/health":
            self._send_json({
                "status": "ok",
                "app": "ArthaLedger",
                "ai_providers": {
                    "deterministic": True,
                    "gemini_env_configured": bool(os.environ.get("GEMINI_API_KEY")),
                    "bharatcode_env_configured": bool(os.environ.get("BHARATCODE_API_KEY")),
                },
            })
            return

        if path == "/api/personas":
            pid = (query.get("id", [""])[0] or "").strip()
            if pid and pid in PERSONAS:
                self._send_json({"success": True, "persona": PERSONAS[pid]})
                return
            self._send_json({"success": True, "personas": list_personas_summary(), "benchmarks": [
                {"id": k, "label": v["label"]} for k, v in BENCHMARK_SERIES.items()
            ]})
            return

        if path in ("/", "/index.html") or path.startswith("/static/"):
            rel = "index.html" if path in ("/", "/index.html") else path[len("/static/"):]
            target = _safe_static_path(rel)
            if target is None:
                self._send_json({"success": False, "error": "Forbidden path"}, status=403)
                return
            if not target.exists() or not target.is_file():
                self._send_json({"success": False, "error": "Asset not found"}, status=404)
                return
            ctype = STATIC_MIME_TYPES.get(target.suffix.lower())
            if not ctype:
                self._send_json({"success": False, "error": "Unsupported file type"}, status=415)
                return
            self._send_bytes(target.read_bytes(), ctype, status=200)
            return

        self._send_json({"success": False, "error": "Route not found"}, status=404)

    def do_POST(self) -> None:
        path, _ = self._resolve_path()
        body, err_code = self._read_json_body()
        if body is None:
            self._send_json({"success": False, "error": "Invalid or oversized JSON payload"}, status=err_code)
            return

        if path == "/api/ledger/analyze":
            res = parse_sms_ledger(
                raw_text=str(body.get("raw_text", "")),
                monthly_budget_target=_num(body.get("monthly_budget_target"), 0.0),
            )
            self._send_json(res)
            return

        if path == "/api/ledger/export.csv":
            res = parse_sms_ledger(
                raw_text=str(body.get("raw_text", "")),
                monthly_budget_target=_num(body.get("monthly_budget_target"), 0.0),
            )
            csv_data = export_ledger_csv(res.get("transactions", []))
            self._send_bytes(csv_data.encode("utf-8"), "text/csv; charset=utf-8", status=200)
            return

        if path == "/api/fraud/audit":
            res = analyze_payment_risk(
                payload_text=str(body.get("payload_text", "")),
                claimed_context=str(body.get("claimed_context", "")),
            )
            self._send_json(res, status=200 if res.get("success") else 400)
            return

        if path == "/api/tax/compare":
            res = calculate_indian_tax(
                gross_income=_num(body.get("gross_income"), 0.0),
                is_salaried=bool(body.get("is_salaried", True)),
                deduction_80c=_num(body.get("deduction_80c"), 0.0),
                deduction_80d=_num(body.get("deduction_80d"), 0.0),
                hra_exemption=_num(body.get("hra_exemption"), 0.0),
                home_loan_interest=_num(body.get("home_loan_interest"), 0.0),
                nps_80ccd1b=_num(body.get("nps_80ccd1b"), 0.0),
            )
            self._send_json(res)
            return

        if path == "/api/wealth/sip":
            res = simulate_sip_wealth(
                monthly_sip=_num(body.get("monthly_sip"), 5000.0),
                annual_return_pct=_num(body.get("annual_return_pct"), 12.0),
                years=_int_val(body.get("years"), 10),
                annual_step_up_pct=_num(body.get("annual_step_up_pct"), 10.0),
                inflation_pct=_num(body.get("inflation_pct"), 6.0),
            )
            self._send_json(res)
            return

        if path == "/api/wealth/emi":
            res = simulate_emi_prepayment(
                principal=_num(body.get("principal"), 500000.0),
                annual_interest_pct=_num(body.get("annual_interest_pct"), 9.5),
                tenure_months=_int_val(body.get("tenure_months"), 60),
                extra_monthly_prepay=_num(body.get("extra_monthly_prepay"), 0.0),
            )
            self._send_json(res)
            return

        if path == "/api/market/backtest":
            raw_custom = body.get("custom_prices")
            custom_list = None
            if isinstance(raw_custom, str) and raw_custom.strip():
                custom_list = [float(x) for x in raw_custom.split(",") if x.strip()]
            elif isinstance(raw_custom, list):
                custom_list = [float(x) for x in raw_custom]
            res = run_paper_backtest(
                symbol=str(body.get("symbol", "NIFTY50_PROXY")),
                strategy=str(body.get("strategy", "sma_crossover")),
                initial_capital=_num(body.get("initial_capital"), 100000.0),
                fast_window=_int_val(body.get("fast_window"), 3),
                slow_window=_int_val(body.get("slow_window"), 7),
                custom_prices=custom_list,
            )
            self._send_json(res)
            return

        if path == "/api/sme/gst":
            res = compute_gst_and_cashflow(
                items=body.get("items") or [],
                supply_type=str(body.get("supply_type", "intra_state")),
                input_tax_credit=_num(body.get("input_tax_credit"), 0.0),
                opening_cash=_num(body.get("opening_cash"), 120000.0),
                monthly_fixed_costs=_num(body.get("monthly_fixed_costs"), 48000.0),
                expected_monthly_collections=_num(body.get("expected_monthly_collections"), 95000.0),
                pending_receivables=_num(body.get("pending_receivables"), 65000.0),
            )
            self._send_json(res)
            return

        if path == "/api/copilot/ask":
            session_key = str(self.headers.get("X-User-AI-Key", "") or body.get("user_api_key", "")).strip()
            res = ask_financial_copilot(
                question=str(body.get("question", "")),
                context=body.get("context") if isinstance(body.get("context"), dict) else {},
                provider=str(body.get("provider", "auto")),
                model=str(body.get("model", "")),
                user_api_key=session_key,
                image_data=str(body.get("image_data", "")),
                image_mime=str(body.get("image_mime", "image/png")),
            )
            self._send_json(res, status=200 if res.get("success") else 400)
            return

        self._send_json({"success": False, "error": "Route not found"}, status=404)


def make_server(host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), ArthaLedgerHandler)


class handler(ArthaLedgerHandler):
    pass


app = handler


if __name__ == "__main__":
    bind_host = os.environ.get("ARTHA_HOST", "127.0.0.1")
    bind_port = int(os.environ.get("ARTHA_PORT", "8080"))
    httpd = make_server(bind_host, bind_port)
    print(f"ArthaLedger listening at http://{bind_host}:{bind_port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
