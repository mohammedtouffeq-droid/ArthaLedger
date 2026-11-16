"""Citation-grounded Financial AI Copilot with Gemini, BharatCode GLM 5.3 Flash (vision), Health Scoring, and deterministic action proposals."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List

GEMINI_MODELS = ("gemini-2.5-flash", "gemini-2.0-flash")
BHARATCODE_MODELS = ("glm-5.3-flash", "deepseek-chat")
ALLOWED_IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/webp"})
BASE64_DATA_URL_RE = re.compile(r"^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\s]+)$", re.IGNORECASE)

SYSTEM_PROMPT = (
    "You are ArthaLedger Copilot, an evidence-first Indian personal and small-business finance analyst. "
    "Ground every figure strictly in the verified telemetry JSON provided. Always include exact inline "
    "citation tags like [TXN-01], [TAX-115BAC], [TAX-87A-NEW], [TAX-BREAKEVEN], [FRAUD-AUDIT], "
    "[FRAUD-LURE-01], [BACKTEST-PAPER], [MF-DIRECT-DRAG], or [GST-ITC-SET] when referencing figures. "
    "Never hallucinate INR numbers, never suggest real-money live stock trading, and keep formatting "
    "concise, analytical, and free of emojis."
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
    hygiene_pts = 25 if risk_score >= 55 else 20  # Detecting scam pre-payment protects funds

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
        actions.append({
            "label": f"Inspect Flagged Entry {first_id}",
            "tab": "ledger",
            "highlight_txn": first_id,
        })

    if tax.get("recommended_regime"):
        citations.extend(["TAX-115BAC", "TAX-BREAKEVEN"])

    if fraud.get("risk_score", 0) >= 25:
        citations.append("FRAUD-AUDIT")
        actions.append({
            "label": "Open Scam Anatomy Breakdown",
            "tab": "fraud",
        })

    if backtest.get("direct_vs_regular"):
        citations.extend(["BACKTEST-PAPER", "MF-DIRECT-DRAG"])
        actions.append({
            "label": "Run Drawdown Dip Strategy",
            "tab": "market",
            "patch": {"btStrategySelect": "dip_accumulation"},
        })

    if sme.get("grand_invoice_total"):
        citations.extend(["GST-ITC-SET", "WC-STRESS-90D"])

    return actions, sorted(set(citations))


def _build_deterministic_answer(question: str, context: Dict[str, Any], has_image: bool) -> Dict[str, Any]:
    """Produces a targeted, conversational or executive diagnostic strictly from computed telemetry."""
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
            f"- [CASHFLOW] Monthly surplus Rs.{net_cf:,.0f} (Recurring subscriptions tracked: Rs.{sub_yr:,.0f}/yr).\n"
            f"- [FRAUD-AUDIT] Active payment audit risk: {risk}/100.\n\n"
            "Ask a specific question (for example: 'Audit my subscriptions', 'How much tax can I save?', "
            "'Verify this UPI scam link', or click 'Full Money Audit' above). To enable live conversational LLM + screenshot OCR, add a Gemini or BharatCode GLM 5.3 Flash key under AI Keys."
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
            bullets.append(
                f"[SUB-BURN] Recurring subscriptions total Rs.{sub_yr:,.0f}/year annualized across flagged debits."
            )
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
            "[VISION-PENDING] Payment/receipt screenshot attached. Add a Gemini or BharatCode GLM 5.3 Flash key "
            "in AI Keys (session-only) to run multimodal OCR inspection."
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


def _call_gemini(api_key: str, model: str, question: str, context_json: str, img_mime: str, img_b64: str) -> str:
    chosen = model if model in GEMINI_MODELS else GEMINI_MODELS[0]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{chosen}:generateContent"
    parts: List[Dict[str, Any]] = [
        {"text": f"Context Telemetry JSON:\n{context_json}\n\nUser Question: {question}"}
    ]
    if img_b64 and img_mime:
        parts.append({"inlineData": {"mimeType": img_mime, "data": img_b64}})

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 900},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    candidates = data.get("candidates") or []
    parts_out = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
    return "\n".join(str(p.get("text", "")) for p in parts_out if p.get("text")).strip()


def _call_bharatcode(api_key: str, model: str, question: str, context_json: str, img_mime: str, img_b64: str) -> str:
    chosen = model if model in BHARATCODE_MODELS else "glm-5.3-flash"
    url = "https://bharatcode.ai/api/model/v1/chat/completions"

    text_block = f"Context Telemetry JSON:\n{context_json}\n\nUser Question: {question}"
    if img_b64 and img_mime and chosen == "glm-5.3-flash":
        user_content: Any = [
            {"type": "text", "text": text_block},
            {"type": "image_url", "image_url": {"url": f"data:{img_mime};base64,{img_b64}"}},
        ]
    else:
        user_content = text_block

    payload = {
        "model": chosen,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "max_tokens": 900,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
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
) -> Dict[str, Any]:
    """Routes grounded Q&A (+ optional image) to Gemini, BharatCode GLM 5.3 Flash, or Deterministic Engine."""
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
            chosen_m = model if model in GEMINI_MODELS else GEMINI_MODELS[0]
            try:
                reply = _call_gemini(gemini_key, chosen_m, q, context_json, img_mime, img_b64)
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
                fallback = _build_deterministic_answer(q, ctx, has_img)
                fallback["fallback_reason"] = f"Gemini fallback: {exc}"
                return fallback

        if (prov in ("bharatcode", "auto")) and bc_key:
            chosen_m = model if model in BHARATCODE_MODELS else "glm-5.3-flash"
            try:
                reply = _call_bharatcode(bc_key, chosen_m, q, context_json, img_mime, img_b64)
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
