"""Citation-grounded Financial AI Copilot with Gemini 3.x fallback chain, BharatCode GLM 5.3 Flash (vision), multi-turn history & deterministic engine."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List

GEMINI_MODELS = ("gemini-3.5-flash-lite", "gemini-3-flash-preview", "gemini-3.8-flash")
BHARATCODE_MODELS = ("glm-5.3-flash", "deepseek-chat")
ALLOWED_IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/webp"})
BASE64_DATA_URL_RE = re.compile(r"^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\s]+)$", re.IGNORECASE)
SAFE_MODEL_RE = re.compile(r"^[A-Za-z0-9._-]{3,64}$")

SYSTEM_PROMPT = (
    "You are ArthaLedger Copilot, an evidence-first Indian personal and small-business finance analyst. "
    "Ground every figure strictly in the verified telemetry JSON provided. Always cite inline codes like "
    "[TXN-01], [CASHFLOW], [TAX-115BAC], [TAX-87A-NEW], [TAX-BREAKEVEN], [FRAUD-AUDIT], [FRAUD-LURE-01], "
    "[BACKTEST-PAPER], [MF-DIRECT-DRAG], or [GST-ITC-SET] when referencing numbers. "
    "Be concise, helpful, never invent INR amounts, never recommend live real-money stock trades, "
    "and use plain authoritative prose with zero emojis."
)


def compute_financial_health_score(context: Dict[str, Any]) -> Dict[str, Any]:
    """Computes a composite 0-100 Financial Readiness Score across active telemetry."""
    ledger = context.get("ledger") or {}
    fraud = context.get("fraud") or {}
    tax = context.get("tax") or {}
    backtest = context.get("backtest") or {}

    savings_pct = float(ledger.get("savings_rate_pct", 0) or 0)
    if savings_pct >= 30:
        savings_pts = 30
    elif savings_pct >= 15:
        savings_pts = 22
    elif savings_pct > 0:
        savings_pts = 14
    else:
        savings_pts = 6

    sub_annual = float(ledger.get("subscription_annual_runrate", 0) or 0)
    burn_pts = 25 if sub_annual == 0 else (18 if sub_annual < 12000 else 10)

    risk_score = float(fraud.get("risk_score", 0) or 0)
    hygiene_pts = 25 if risk_score >= 55 else 20

    tax_pts = 10 if tax.get("recommended_regime") else 5
    sharpe = float(backtest.get("sharpe_ratio", 0) or 0)
    mkt_pts = 10 if sharpe >= 0.8 else (7 if sharpe > 0 else 4)

    total = min(100, savings_pts + burn_pts + hygiene_pts + tax_pts + mkt_pts)
    grade = "STRONG" if total >= 80 else ("MODERATE" if total >= 60 else "ATTENTION")
    return {
        "score": int(total),
        "grade": grade,
        "pillars": {
            "cashflow_savings": savings_pts,
            "recurring_burn_control": burn_pts,
            "scam_defense_readiness": hygiene_pts,
            "tax_optimization": tax_pts,
            "risk_adjusted_investing": mkt_pts,
        },
    }


def _sanitize_image(image_data: str, image_mime: str = "image/png") -> tuple[str, str]:
    raw = str(image_data or "").strip()
    if not raw:
        return "", ""
    m = BASE64_DATA_URL_RE.match(raw)
    if m:
        return m.group(1).lower(), re.sub(r"\s+", "", m.group(2))
    mime = image_mime.lower() if image_mime.lower() in ALLOWED_IMAGE_MIMES else "image/png"
    b64 = re.sub(r"\s+", "", raw)
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", b64 or ""):
        return "", ""
    return mime, b64


def _derive_actions_and_citations(context: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[str]]:
    actions: List[Dict[str, Any]] = []
    citations: List[str] = []

    ledger = context.get("ledger") or {}
    tax = context.get("tax") or {}
    fraud = context.get("fraud") or {}
    backtest = context.get("backtest") or {}
    sme = context.get("sme") or {}

    net_cf = float(ledger.get("net_cashflow", 0) or 0)
    if net_cf >= 1000:
        suggested_sip = int(round(net_cf * 0.45, -2)) or 1000
        actions.append({
            "label": f"Simulate Rs.{suggested_sip:,}/mo Step-Up SIP",
            "tab": "tax",
            "patch": {"sipMonthlyInput": suggested_sip},
        })

    anoms = ledger.get("anomalies") or []
    if anoms:
        first_id = anoms[0]["citation"]
        citations.append(first_id)
        actions.append({"label": f"Inspect Flagged Entry {first_id}", "tab": "ledger", "highlight_txn": first_id})

    if tax.get("recommended_regime"):
        citations.extend(["TAX-115BAC", "TAX-BREAKEVEN"])

    if fraud.get("risk_score", 0) >= 25:
        citations.append("FRAUD-AUDIT")
        actions.append({"label": "Open Scam Anatomy Breakdown", "tab": "fraud"})

    if backtest.get("direct_vs_regular"):
        citations.extend(["BACKTEST-PAPER", "MF-DIRECT-DRAG"])
        actions.append({"label": "Run Drawdown Dip Strategy", "tab": "market", "patch": {"btStrategySelect": "dip_accumulation"}})

    if sme.get("grand_invoice_total"):
        citations.extend(["GST-ITC-SET", "WC-STRESS-90D"])
    if context.get("comparison"):
        citations.append("MF-CORR-OVERLAP")
    if context.get("harvest"):
        citations.append("TAX-HARVEST-112A")
    if context.get("qr_scan"):
        citations.append("FRAUD-QR-SCAN")

    return actions, sorted(set(citations))


def _build_deterministic_answer(question: str, context: Dict[str, Any], has_image: bool) -> Dict[str, Any]:
    """Produces a targeted conversational or executive diagnostic strictly from computed telemetry."""
    q_clean = question.strip()
    q_low = q_clean.lower()
    health = compute_financial_health_score(context)
    actions, base_citations = _derive_actions_and_citations(context)

    ledger = context.get("ledger") or {}
    tax = context.get("tax") or {}
    fraud = context.get("fraud") or {}
    backtest = context.get("backtest") or {}
    sme = context.get("sme") or {}

    greeting_words = {"hi", "hello", "hey", "yo", "yoo", "hii", "helo", "sup", "namaste"}
    if q_low.strip("!?. ") in greeting_words:
        net_cf = float(ledger.get("net_cashflow", 0) or 0)
        sub_yr = float(ledger.get("subscription_annual_runrate", 0) or 0)
        risk = int(fraud.get("risk_score", 0) or 0)
        reply_text = (
            f"ArthaLedger Deterministic Copilot ready (Financial Health Index: {health['score']}/100 - {health['grade']}).\n\n"
            f"Live Telemetry Loaded:\n"
            f"- [CASHFLOW] Monthly surplus Rs.{net_cf:,.0f} (Subscriptions tracked: Rs.{sub_yr:,.0f}/yr).\n"
            f"- [FRAUD-AUDIT] Active payment audit risk: {risk}/100.\n\n"
            "Ask about your subscriptions, tax regime breakeven, scam link audit, AMFI mutual fund performance, or click Full Money Audit."
        )
        extracted = sorted(set(re.findall(r"\[([A-Z0-9_-]{3,24})\]", reply_text)))
        return {
            "success": True,
            "provider_used": "deterministic",
            "model_used": "artha-deterministic-citation-v2",
            "reply": reply_text,
            "citations": extracted,
            "actions": actions[:2],
            "health_score": health,
        }

    is_full_audit = any(w in q_low for w in ("full", "audit", "summarize", "summary", "overall", "health", "all"))
    want_cash = is_full_audit or any(w in q_low for w in ("spend", "budget", "cashflow", "sub", "txn", "money", "save", "afford", "expense", "upi"))
    want_tax = is_full_audit or any(w in q_low for w in ("tax", "regime", "80c", "nps", "salary", "ctc", "deduction", "take-home"))
    want_fraud = is_full_audit or any(w in q_low for w in ("scam", "fraud", "phishing", "kyc", "collect", "link", "pin", "safe"))
    want_mkt = is_full_audit or any(w in q_low for w in ("sip", "fund", "amfi", "market", "backtest", "sharpe", "nifty", "stock", "invest", "regular", "direct"))
    want_sme = is_full_audit or any(w in q_low for w in ("gst", "sme", "invoice", "itc", "business", "runway", "receivable"))
    if not (want_cash or want_tax or want_fraud or want_mkt or want_sme):
        want_cash = want_tax = True

    bullets: List[str] = [f"Financial Health Index: {health['score']}/100 ({health['grade']})."]

    if want_cash and ledger.get("transaction_count"):
        spent = float(ledger.get("total_spent", 0))
        income = float(ledger.get("total_income", 0))
        net = float(ledger.get("net_cashflow", 0))
        sub_yr = float(ledger.get("subscription_annual_runrate", 0))
        top_cats = ledger.get("categories") or []
        top_str = ", ".join(f"{c['category']} ({c['share_pct']}%)" for c in top_cats[:3])
        bullets.append(
            f"[CASHFLOW] Net monthly surplus is Rs.{net:,.0f} (Inflow Rs.{income:,.0f} vs Outflow Rs.{spent:,.0f}, "
            f"{ledger.get('savings_rate_pct', 0)}% savings rate). Leading spend buckets: {top_str or 'N/A'}."
        )
        if sub_yr > 0:
            bullets.append(f"[SUB-BURN] Recurring subscriptions total Rs.{sub_yr:,.0f}/year annualized across flagged debits.")
        for anom in (ledger.get("anomalies") or [])[:4]:
            bullets.append(f"[{anom['citation']}] {anom['reason']}")

    if want_tax and tax.get("recommended_regime"):
        rec = "New Tax Regime (Sec 115BAC)" if tax["recommended_regime"] == "NEW_REGIME" else "Old Tax Regime"
        bullets.append(
            f"[TAX-115BAC][TAX-BREAKEVEN] Optimal regime: {rec} "
            f"(New Tax: Rs.{tax['new_regime']['total_tax']:,.0f} vs Old Tax: Rs.{tax['old_regime']['total_tax']:,.0f}, "
            f"saving Rs.{tax['net_tax_savings']:,.0f}/yr; Monthly take-home ~Rs.{tax.get('monthly_take_home', 0):,.0f}). "
            f"Old Regime requires Rs.{tax.get('breakeven_deduction', 0):,.0f} deductions to beat Budget 2025 New Regime."
        )

    if want_fraud and fraud.get("verdict"):
        bullets.append(
            f"[FRAUD-AUDIT] Active audit verdict: {fraud['verdict']} (Risk {fraud['risk_score']}/100). "
            f"{fraud['recommended_action']}"
        )
        for fl in (fraud.get("flags") or [])[:3]:
            bullets.append(f"[{fl['citation']}] {fl['detail']}")

    if want_mkt and backtest.get("final_equity"):
        drag = backtest.get("direct_vs_regular") or {}
        bullets.append(
            f"[BACKTEST-PAPER][MF-DIRECT-DRAG] {backtest.get('label')}: Strategy {backtest.get('total_return_pct')}% "
            f"vs Benchmark {backtest.get('benchmark_return_pct')}% (Sharpe {backtest.get('sharpe_ratio')}, "
            f"Max Drawdown {backtest.get('max_drawdown_pct')}%). Switching Regular->Direct plan avoids "
            f"Rs.{drag.get('commission_leakage', 0):,.0f} fee drag over {drag.get('years', 15)} years."
        )

    if want_sme and sme.get("grand_invoice_total"):
        bullets.append(
            f"[GST-ITC-SET][WC-STRESS-90D] SME Invoice Rs.{sme['grand_invoice_total']:,.0f}, Net GST Payable after ITC "
            f"Rs.{sme['net_gst_payable']:,.0f}, 35% Delayed-Receivable Stress Runway: {sme['stress_runway_days']} days."
        )

    if has_image:
        bullets.append(
            "[VISION-PENDING] Screenshot attached. Add a live Gemini or BharatCode GLM 5.3 Flash key in AI Keys for vision inspection."
        )

    reply_text = f"Grounded Telemetry Response ({q_clean[:90]}):\n\n" + "\n".join(f"- {b}" for b in bullets)
    extracted = sorted(set(re.findall(r"\[([A-Z0-9_-]{3,24})\]", reply_text)) | set(base_citations))

    return {
        "success": True,
        "provider_used": "deterministic",
        "model_used": "artha-deterministic-citation-v2",
        "reply": reply_text,
        "citations": extracted,
        "actions": actions,
        "health_score": health,
    }


def _call_gemini(
    api_key: str,
    model: str,
    question: str,
    context_json: str,
    img_mime: str,
    img_b64: str,
    history: List[Dict[str, str]] | None = None,
) -> str:
    chosen = model if SAFE_MODEL_RE.match(model or "") and not model.startswith(("gemini-2.5", "gemini-2.0", "gemini-1.")) else GEMINI_MODELS[0]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{chosen}:generateContent"

    contents: List[Dict[str, Any]] = []
    for turn in (history or [])[-6:]:
        role = "model" if turn.get("role") == "assistant" else "user"
        txt = str(turn.get("content", "")).strip()
        if txt:
            contents.append({"role": role, "parts": [{"text": txt[:1500]}]})

    parts: List[Dict[str, Any]] = [
        {"text": f"Context Telemetry JSON:\n{context_json}\n\nUser Question: {question}"}
    ]
    if img_b64 and img_mime:
        parts.append({"inlineData": {"mimeType": img_mime, "data": img_b64}})
    contents.append({"role": "user", "parts": parts})

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 900},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=14) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    candidates = data.get("candidates") or []
    parts_out = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
    return "\n".join(str(p.get("text", "")) for p in parts_out if p.get("text")).strip()


def _call_bharatcode(
    api_key: str,
    model: str,
    question: str,
    context_json: str,
    img_mime: str,
    img_b64: str,
    history: List[Dict[str, str]] | None = None,
) -> str:
    chosen = model if model in BHARATCODE_MODELS else "glm-5.3-flash"
    url = "https://bharatcode.ai/api/model/v1/chat/completions"

    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in (history or [])[-6:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        txt = str(turn.get("content", "")).strip()
        if txt:
            messages.append({"role": role, "content": txt[:1500]})

    text_block = f"Context Telemetry JSON:\n{context_json}\n\nUser Question: {question}"
    if img_b64 and img_mime and chosen == "glm-5.3-flash":
        user_content: Any = [
            {"type": "text", "text": text_block},
            {"type": "image_url", "image_url": {"url": f"data:{img_mime};base64,{img_b64}"}},
        ]
    else:
        user_content = text_block
    messages.append({"role": "user", "content": user_content})

    payload = {"model": chosen, "messages": messages, "temperature": 0.2, "max_tokens": 900}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    choices = data.get("choices") or []
    msg = (choices[0].get("message") or {}) if choices else {}
    return str(msg.get("content", "")).strip()


def ask_financial_copilot(
    question: str,
    context: Dict[str, Any] | None = None,
    provider: str = "auto",
    model: str = "",
    user_api_key: str = "",
    image_data: str = "",
    image_mime: str = "image/png",
    history: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    """Routes grounded Q&A (+ optional screenshot & conversation history) to Gemini 3.x, BharatCode GLM 5.3 Flash, or Deterministic Engine."""
    q = str(question or "").strip()
    if not q:
        return {"success": False, "error": "Enter a financial question or audit prompt."}

    ctx = context if isinstance(context, dict) else {}
    img_mime, img_b64 = _sanitize_image(image_data, image_mime)
    has_img = bool(img_b64)
    context_json = json.dumps(ctx, ensure_ascii=True)[:12000]
    health = compute_financial_health_score(ctx)
    actions, base_citations = _derive_actions_and_citations(ctx)

    prov = str(provider or "auto").strip().lower()
    gemini_key = (user_api_key if prov == "gemini" else "") or os.environ.get("GEMINI_API_KEY", "").strip()
    bc_key = (user_api_key if prov == "bharatcode" else "") or os.environ.get("BHARATCODE_API_KEY", "").strip()
    if prov == "auto" and user_api_key.strip():
        if model.startswith("glm-") or model.startswith("deepseek"):
            bc_key = user_api_key.strip()
        else:
            gemini_key = user_api_key.strip()

    if prov != "deterministic":
        if (prov in ("gemini", "auto")) and gemini_key:
            candidates_order = [model] if (model and not model.startswith(("gemini-2.", "gemini-1.", "glm-", "deepseek"))) else []
            for m in GEMINI_MODELS:
                if m not in candidates_order:
                    candidates_order.append(m)
            last_exc = None
            for chosen_m in candidates_order:
                try:
                    reply = _call_gemini(gemini_key, chosen_m, q, context_json, img_mime, img_b64, history=history)
                    if reply:
                        cites = sorted(set(re.findall(r"\[([A-Z0-9_-]{3,24})\]", reply)) | set(base_citations))
                        return {
                            "success": True,
                            "provider_used": "gemini",
                            "model_used": chosen_m,
                            "reply": reply,
                            "citations": cites,
                            "actions": actions,
                            "health_score": health,
                        }
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
                    last_exc = exc
                    continue
            fallback = _build_deterministic_answer(q, ctx, has_img)
            fallback["fallback_reason"] = f"Gemini fallback: {last_exc}"
            return fallback

        if (prov in ("bharatcode", "auto")) and bc_key:
            chosen_m = model if model in BHARATCODE_MODELS else "glm-5.3-flash"
            try:
                reply = _call_bharatcode(bc_key, chosen_m, q, context_json, img_mime, img_b64, history=history)
                if reply:
                    cites = sorted(set(re.findall(r"\[([A-Z0-9_-]{3,24})\]", reply)) | set(base_citations))
                    return {
                        "success": True,
                        "provider_used": "bharatcode",
                        "model_used": chosen_m,
                        "reply": reply,
                        "citations": cites,
                        "actions": actions,
                        "health_score": health,
                    }
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
                fallback = _build_deterministic_answer(q, ctx, has_img)
                fallback["fallback_reason"] = f"BharatCode API fallback: {exc}"
                return fallback

    return _build_deterministic_answer(q, ctx, has_img)


def extract_payment_text_from_image(
    image_data: str,
    image_mime: str = "image/png",
    provider: str = "auto",
    model: str = "",
    user_api_key: str = "",
) -> Dict[str, Any]:
    """Extracts payment URIs, VPAs, phone numbers, URLs, and coercion cues from an uploaded QR or payment screenshot."""
    mime, b64 = _sanitize_image(image_data, image_mime)
    if not b64:
        return {"success": False, "extracted_text": "", "vision_provider": "none", "error": "Invalid image data"}

    prov = str(provider or "auto").strip().lower()
    gemini_key = (user_api_key if prov == "gemini" else "") or os.environ.get("GEMINI_API_KEY", "").strip()
    bc_key = (user_api_key if prov == "bharatcode" else "") or os.environ.get("BHARATCODE_API_KEY", "").strip()
    extract_q = (
        "Extract EVERY payment detail verbatim from this QR code or payment/SMS screenshot into one compact plain-text block: "
        "include any upi://pay?... URI, VPA (@handle), payee display name, INR amount, phone numbers, domain/URLs, .apk filenames, "
        "and exact visible warning/cashback/PIN/KYC lines. Plain text only, zero markdown."
    )

    if prov != "deterministic" and (prov in ("gemini", "auto")) and gemini_key:
        for chosen_m in GEMINI_MODELS:
            try:
                txt = _call_gemini(gemini_key, chosen_m, extract_q, "{}", mime, b64, history=[])
                if txt:
                    return {"success": True, "extracted_text": txt, "vision_provider": f"gemini ({chosen_m})"}
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
                continue

    if prov != "deterministic" and (prov in ("bharatcode", "auto")) and bc_key:
        try:
            txt = _call_bharatcode(bc_key, "glm-5.3-flash", extract_q, "{}", mime, b64, history=[])
            if txt:
                return {"success": True, "extracted_text": txt, "vision_provider": "bharatcode (glm-5.3-flash)"}
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
            pass

    return {"success": False, "extracted_text": "", "vision_provider": "none"}


PDF_BASE64_RE = re.compile(r"^data:application/pdf;base64,([A-Za-z0-9+/=\s]+)$", re.IGNORECASE)


def extract_ledger_lines_from_pdf(
    pdf_data: str,
    provider: str = "auto",
    model: str = "",
    user_api_key: str = "",
) -> Dict[str, Any]:
    """Extracts normalized Indian bank/UPI transaction lines from an uploaded statement PDF."""
    raw = str(pdf_data or "").strip()
    m = PDF_BASE64_RE.match(raw)
    b64 = re.sub(r"\s+", "", m.group(1) if m else raw)
    if not b64 or not re.fullmatch(r"[A-Za-z0-9+/=]+", b64):
        return {"success": False, "lines": "", "error": "Invalid PDF payload"}

    prov = str(provider or "auto").strip().lower()
    gemini_key = (user_api_key if prov in ("gemini", "auto") else "") or os.environ.get("GEMINI_API_KEY", "").strip()
    prompt = (
        "Extract EVERY credit and debit transaction from this Indian bank statement PDF. "
        "Output ONLY plain lines (no markdown, no headers) in exact format:\n"
        "Credited Rs.AMOUNT towards COUNTERPARTY on DD-Mon-YYYY.\n"
        "Debited Rs.AMOUNT via UPI to COUNTERPARTY on DD-Mon-YYYY."
    )

    if prov != "deterministic" and gemini_key:
        for chosen_m in GEMINI_MODELS:
            try:
                txt = _call_gemini(gemini_key, chosen_m, prompt, "{}", "application/pdf", b64, history=[])
                clean_lines = "\n".join(
                    ln.strip() for ln in txt.splitlines()
                    if re.search(r"\b(credited|debited)\b", ln, re.I) and re.search(r"\d", ln)
                )
                if clean_lines:
                    return {"success": True, "lines": clean_lines, "source": f"gemini ({chosen_m})"}
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
                continue

    # Pure-Python fallback for uncompressed text PDF streams offline
    try:
        import base64 as _b64
        decoded = _b64.b64decode(b64, validate=False).decode("latin-1", errors="ignore")
        ascii_runs = re.findall(r"\(([^()]{8,140})\)", decoded)
        text_lines = "\n".join(
            run.strip() for run in ascii_runs
            if re.search(r"\b(credit|debit|rs\.?|inr)\b", run, re.I) and re.search(r"\d", run)
        )
        if text_lines:
            return {"success": True, "lines": text_lines, "source": "pdf_text_stream_fallback"}
    except ValueError:
        pass

    return {
        "success": False,
        "lines": "",
        "error": "Could not extract transactions from scanned/compressed PDF offline. Configure Gemini API key in AI Keys or export CSV.",
    }


def _extract_json_block(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {}
    try:
        parsed = json.loads(m.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def run_financial_council(
    context: Dict[str, Any] | None = None,
    provider: str = "auto",
    model: str = "",
    user_api_key: str = "",
) -> Dict[str, Any]:
    """Orchestrates 3 specialist AI financial agents (CA Tax/Cashflow, Cyber Fraud, Quant Strategist) grounded in live telemetry."""
    ctx = context if isinstance(context, dict) else {}
    ledger = ctx.get("ledger") or {}
    tax = ctx.get("tax") or {}
    fraud = ctx.get("fraud") or {}
    backtest = ctx.get("backtest") or {}
    cmp_data = ctx.get("comparison") or {}
    harvest = ctx.get("harvest") or {}
    mc = ctx.get("monte_carlo") or {}
    news = ctx.get("news_impact") or {}

    sub_annual = float(ledger.get("subscription_annual_runrate", 0) or 0)
    tax_save = float(tax.get("net_tax_savings", 0) or 0)
    harvest_save_ann = round(float(harvest.get("net_tax_saved", 0) or 0) / max(1, int(harvest.get("years", 5) or 5)), 0)
    fee_drag_ann = round(float((backtest.get("direct_vs_regular") or {}).get("commission_leakage", 0) or 0) / 15.0, 0)
    ca_impact = int(round(sub_annual + tax_save + harvest_save_ann))
    quant_impact = int(round(fee_drag_ann))

    risk_score = int(float(fraud.get("risk_score", 0) or 0))
    verdict = str(fraud.get("verdict") or "UNSCANNED")
    req_amt = float((fraud.get("parsed_upi") or {}).get("amount") or 0)
    fraud_impact = int(round(req_amt)) if risk_score >= 55 and req_amt > 0 else (19999 if risk_score >= 55 else 0)
    total_impact = ca_impact + quant_impact + fraud_impact

    det_ca = (
        f"Optimal {tax.get('recommended_regime', 'NEW_REGIME')} saves Rs.{tax_save:,.0f}/yr; "
        f"recurring subscriptions burn Rs.{sub_annual:,.0f}/yr ([TXN-05]), and Sec 112A LTCG harvesting saves Rs.{harvest_save_ann:,.0f}/yr [TAX-HARVEST-112A]."
    )
    det_fraud = (
        f"Active verdict {verdict} ({risk_score}/100) [FRAUD-AUDIT]. "
        + ("Decline collect/APK immediately and report sender on 1930 / Chakshu." if risk_score >= 55 else "Maintain strict UPI PIN discipline.")
    )
    det_quant = (
        f"Switching Regular->Direct saves Rs.{fee_drag_ann:,.0f}/yr [MF-DIRECT-DRAG]; "
        f"AMFI correlation r={cmp_data.get('correlation', '--')} [MF-CORR-OVERLAP], Monte Carlo Goal Hit {mc.get('goal_success_prob_pct', '--')}%, Macro {news.get('regime', 'BALANCED')}."
    )
    det_plan = [
        f"1. Cancel idle subscriptions & execute {tax.get('recommended_regime', 'NEW_REGIME')} plan (+Rs.{ca_impact:,}/yr).",
        f"2. Enforce Threat Shield rule: {verdict} ({risk_score}/100) [FRAUD-AUDIT].",
        f"3. Keep Direct Plan MF + diversify correlation r={cmp_data.get('correlation', '--')} (+Rs.{quant_impact:,}/yr).",
    ]

    prov = str(provider or "auto").strip().lower()
    gemini_key = (user_api_key if prov in ("gemini", "auto") else "") or os.environ.get("GEMINI_API_KEY", "").strip()
    engine_used = "deterministic-council-v1"
    ca_brief, fraud_brief, quant_brief, priority_plan = det_ca, det_fraud, det_quant, det_plan

    if prov != "deterministic" and gemini_key:
        council_prompt = (
            "Act as ArthaLedger's 3-Agent Financial Council. Using ONLY numbers from Context Telemetry JSON, "
            "return strictly one valid JSON object with exact keys: "
            '{"ca_brief": "<=35 words citing [TAX-115BAC]/[TXN-*]", '
            '"fraud_brief": "<=35 words citing [FRAUD-AUDIT]", '
            '"quant_brief": "<=35 words citing [MF-DIRECT-DRAG]/[BACKTEST-PAPER]", '
            '"priority_plan": ["step 1", "step 2", "step 3"]}.'
        )
        ctx_compact = json.dumps({
            "ledger": {"surplus": ledger.get("net_cashflow"), "subs_yr": sub_annual},
            "tax": {"rec": tax.get("recommended_regime"), "save": tax_save},
            "harvest": {"saved_yr": harvest_save_ann},
            "fraud": {"verdict": verdict, "score": risk_score, "amt": fraud_impact},
            "quant": {"fee_drag_yr": fee_drag_ann, "corr": cmp_data.get("correlation"), "mc_prob": mc.get("goal_success_prob_pct"), "news": news.get("regime")},
        }, ensure_ascii=True)
        for chosen_m in GEMINI_MODELS:
            try:
                raw_out = _call_gemini(gemini_key, chosen_m, council_prompt, ctx_compact, "", "", history=[])
                parsed = _extract_json_block(raw_out)
                if parsed.get("ca_brief") and parsed.get("fraud_brief") and parsed.get("quant_brief"):
                    ca_brief = str(parsed["ca_brief"]).strip()
                    fraud_brief = str(parsed["fraud_brief"]).strip()
                    quant_brief = str(parsed["quant_brief"]).strip()
                    if isinstance(parsed.get("priority_plan"), list) and parsed["priority_plan"]:
                        priority_plan = [str(x).strip() for x in parsed["priority_plan"][:3]]
                    engine_used = f"gemini ({chosen_m})"
                    break
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
                continue

    return {
        "success": True,
        "engine_used": engine_used,
        "total_annual_rupee_impact": total_impact,
        "agents": [
            {"role": "Chartered Accountant Agent", "tag": f"+Rs.{ca_impact:,}/yr", "brief": ca_brief, "pillar": "Tax & Burn"},
            {"role": "Cyber Forensics Agent", "tag": f"Shield: {verdict}", "brief": fraud_brief, "pillar": "Fraud Defense"},
            {"role": "Quant Macro Strategist", "tag": f"+Rs.{quant_impact:,}/yr", "brief": quant_brief, "pillar": "Wealth & Risk"},
        ],
        "priority_plan": priority_plan,
    }
