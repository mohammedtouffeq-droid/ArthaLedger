"""Citation-grounded Financial AI Copilot with Gemini, BharatCode GLM 5.3 Flash (vision), and deterministic fallback."""
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
    "Use ONLY the verified telemetry provided in the context JSON. Always cite exact IDs like [TXN-01], "
    "[TAX-115BAC], [TAX-87A-NEW], [FRAUD-LURE-01], [BACKTEST], or [GST-ITC-SET] when stating numbers. "
    "Never invent INR figures, never recommend real-money live stock trades, and keep formatting crisp, "
    "professional, and free of emojis."
)


def _sanitize_image(image_data: str, image_mime: str = "image/png") -> tuple[str, str]:
    raw = str(image_data or "").strip()
    if not raw:
        return "", ""
    m = BASE64_DATA_URL_RE.match(raw)
    if m:
        mime = m.group(1).lower()
        b64 = re.sub(r"\s+", "", m.group(2))
        return mime, b64
    mime = image_mime.lower() if image_mime.lower() in ALLOWED_IMAGE_MIMES else "image/png"
    b64 = re.sub(r"\s+", "", raw)
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", b64 or ""):
        return "", ""
    return mime, b64


def _build_deterministic_answer(question: str, context: Dict[str, Any], has_image: bool) -> Dict[str, Any]:
    """Generates a deterministic, cited analysis solely from computed engine telemetry."""
    q_lower = str(question or "").lower()
    bullets: List[str] = []
    citations: List[str] = []

    ledger = context.get("ledger") or {}
    tax = context.get("tax") or {}
    fraud = context.get("fraud") or {}
    backtest = context.get("backtest") or {}
    sme = context.get("sme") or {}

    if ledger.get("transaction_count"):
        spent = float(ledger.get("total_spent", 0))
        income = float(ledger.get("total_income", 0))
        net = float(ledger.get("net_cashflow", 0))
        top_cats = ledger.get("categories") or []
        top_str = ", ".join(f"{c['category']}: Rs.{c['amount']:,.0f} ({c['share_pct']}%)" for c in top_cats[:3])
        bullets.append(
            f"Cashflow summary: Income Rs.{income:,.0f} vs Spend Rs.{spent:,.0f} (Net Rs.{net:,.0f}). "
            f"Top categories: {top_str or 'N/A'}."
        )
        for anom in (ledger.get("anomalies") or [])[:3]:
            bullets.append(f"[{anom['citation']}] {anom['reason']}")
            citations.append(anom["citation"])

    if tax.get("recommended_regime"):
        rec_label = "New Tax Regime (Sec 115BAC)" if tax["recommended_regime"] == "NEW_REGIME" else "Old Tax Regime"
        bullets.append(
            f"[TAX-115BAC][TAX-87A-NEW] Recommended: {rec_label}. "
            f"New Tax: Rs.{tax['new_regime']['total_tax']:,.0f} vs Old Tax: Rs.{tax['old_regime']['total_tax']:,.0f} "
            f"(Savings: Rs.{tax['net_tax_savings']:,.0f})."
        )
        citations.extend(["TAX-115BAC", "TAX-87A-NEW"])

    if fraud.get("verdict"):
        bullets.append(
            f"[FRAUD-AUDIT] Verdict: {fraud['verdict']} (Risk Score {fraud['risk_score']}/100). "
            f"Action: {fraud['recommended_action']}"
        )
        for fl in (fraud.get("flags") or [])[:3]:
            bullets.append(f"[{fl['citation']}] ({fl['severity']}) {fl['detail']}")
            citations.append(fl["citation"])

    if backtest.get("final_equity"):
        bullets.append(
            f"[BACKTEST-PAPER] Historical simulation ({backtest.get('symbol')} / {backtest.get('strategy')}): "
            f"Return {backtest.get('total_return_pct')}% vs Benchmark {backtest.get('benchmark_return_pct')}%, "
            f"Max Drawdown {backtest.get('max_drawdown_pct')}%."
        )
        citations.append("BACKTEST-PAPER")

    if sme.get("grand_invoice_total"):
        bullets.append(
            f"[GST-ITC-SET][WC-STRESS-90D] Invoice Total Rs.{sme['grand_invoice_total']:,.0f}, "
            f"Net GST Payable after ITC Rs.{sme['net_gst_payable']:,.0f}, "
            f"Receivable-Stress Cash Runway: {sme['stress_runway_days']} days."
        )
        citations.extend(["GST-ITC-SET", "WC-STRESS-90D"])

    if has_image:
        bullets.append(
            "Screenshot received: deterministic text engine analyzed structured state telemetry. "
            "Configure a Gemini or BharatCode GLM 5.3 Flash API key in Settings for OCR/vision inspection of screenshots."
        )

    if not bullets:
        bullets.append(
            "Run any module (Ledger, Fraud Shield, Tax Optimizer, Paper Backtester, or SME GST) first to ground "
            "the copilot with verifiable INR telemetry."
        )

    focus_note = f"Query Focus: '{question.strip()[:120]}'\n" if q_lower else ""
    reply_text = focus_note + "\n".join(f"- {b}" for b in bullets)

    return {
        "success": True,
        "provider_used": "deterministic",
        "model_used": "artha-deterministic-citation-v1",
        "reply": reply_text,
        "citations": sorted(set(citations)),
    }


def _call_gemini(
    api_key: str,
    model: str,
    question: str,
    context_json: str,
    img_mime: str,
    img_b64: str,
) -> str:
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


def _call_bharatcode(
    api_key: str,
    model: str,
    question: str,
    context_json: str,
    img_mime: str,
    img_b64: str,
) -> str:
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
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
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

    prov = str(provider or "auto").strip().lower()
    gemini_key = (user_api_key if prov == "gemini" else "") or os.environ.get("GEMINI_API_KEY", "").strip()
    bc_key = (user_api_key if prov == "bharatcode" else "") or os.environ.get("BHARATCODE_API_KEY", "").strip()
    if prov == "auto" and user_api_key.strip():
        # Heuristic routing if single custom key supplied under auto
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
                    return {
                        "success": True,
                        "provider_used": "gemini",
                        "model_used": chosen_m,
                        "reply": reply,
                        "citations": sorted(set(re.findall(r"\[([A-Z0-9_-]{3,24})\]", reply))),
                    }
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
                fallback = _build_deterministic_answer(q, ctx, has_img)
                fallback["fallback_reason"] = f"Gemini request fallback: {exc}"
                return fallback

        if (prov in ("bharatcode", "auto")) and bc_key:
            chosen_m = model if model in BHARATCODE_MODELS else "glm-5.3-flash"
            try:
                reply = _call_bharatcode(bc_key, chosen_m, q, context_json, img_mime, img_b64)
                if reply:
                    return {
                        "success": True,
                        "provider_used": "bharatcode",
                        "model_used": chosen_m,
                        "reply": reply,
                        "citations": sorted(set(re.findall(r"\[([A-Z0-9_-]{3,24})\]", reply))),
                    }
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
                fallback = _build_deterministic_answer(q, ctx, has_img)
                fallback["fallback_reason"] = f"BharatCode API fallback: {exc}"
                return fallback

    return _build_deterministic_answer(q, ctx, has_img)
