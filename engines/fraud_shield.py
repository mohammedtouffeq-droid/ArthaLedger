"""Deterministic NPCI UPI URI, phishing SMS, APK malware, homoglyph, and payment fraud forensics."""
from __future__ import annotations

import re
import urllib.parse
from typing import Any, Dict, List

UPI_URI_RE = re.compile(r"upi://pay\?[^\s\"'<>]+", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?91[-.\s]?)?[6-9]\d{9}\b")
APK_RE = re.compile(r"\b[\w.-]+\.apk\b", re.IGNORECASE)
ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")

SHORTENER_DOMAINS = frozenset({
    "bit.ly", "tinyurl.com", "t.co", "rb.gy", "is.gd", "shorturl.at", "cutt.ly", "goo.gl"
})

URGENCY_TRIGGERS: List[tuple[str, int, str]] = [
    ("kyc", 22, "KYC suspension threat commonly used in account-takeover phishing"),
    ("lottery", 28, "Unsolicited lottery/cashback claim bait"),
    ("prize money", 25, "Fake reward/prize claim hook"),
    ("refund", 16, "Refund lure - legitimate merchants never send UPI collect links to issue refunds"),
    ("blocked", 18, "Artificial account-block fear trigger"),
    ("suspend", 18, "Fake account suspension threat"),
    ("enter pin", 35, "CRITICAL: Asking for UPI PIN to receive money is a guaranteed fraud pattern"),
    ("upi pin", 32, "CRITICAL: Legitimate inbound transfers never require entering your UPI PIN"),
    ("share otp", 35, "CRITICAL: Credential harvesting request for OTP"),
    ("remote access", 30, "Screen-share / AnyDesk scam pattern"),
    ("anydesk", 30, "Remote-control app fraud pattern"),
    ("teamviewer", 28, "Remote-control app fraud pattern"),
    ("urgent", 12, "Artificial urgency deadline pressure"),
    ("within 24 hours", 14, "Countdown coercion pattern"),
    ("electricity disconnect", 24, "Fake utility bill disconnection scam"),
    ("echallan", 24, "Fake traffic e-Challan APK / phishing bait"),
    ("e-challan", 24, "Fake traffic e-Challan APK / phishing bait"),
]

IMPERSONATION_HANDLES = (
    "helpdesk", "support", "kyc", "refund", "verify", "reward", "care", "rbi", "npci", "customercare", "cashback"
)


def _add_flag(flags: List[Dict[str, Any]], code: str, severity: str, weight: int, detail: str) -> int:
    flags.append({"citation": code, "severity": severity, "weight": weight, "detail": detail})
    return weight


def analyze_payment_risk(payload_text: str, claimed_context: str = "") -> Dict[str, Any]:
    """Audits SMS alerts, links, APK lures, or upi://pay URIs and returns cited fraud findings and structural anatomy."""
    raw = str(payload_text or "").strip()
    ctx = str(claimed_context or "").strip()
    combined = f"{raw}\n{ctx}".strip()
    lower = combined.lower()

    if not raw:
        return {"success": False, "error": "Provide an SMS message, UPI link, or payment request text to audit."}

    flags: List[Dict[str, Any]] = []
    score = 0

    if ZERO_WIDTH_RE.search(combined) or any(0x0400 <= ord(ch) <= 0x04FF for ch in combined):
        score += _add_flag(
            flags,
            "FRAUD-HOMO-01",
            "CRITICAL",
            36,
            "Unicode homoglyph or zero-width stealth characters detected (IDN/brand spoofing evasion)",
        )

    apks = APK_RE.findall(combined)
    if apks:
        score += _add_flag(
            flags,
            "FRAUD-APK-01",
            "CRITICAL",
            45,
            f"Unsolicited Android sideload installer ({apks[0]}) detected - high risk of SMS/OTP stealer trojan",
        )

    upi_matches = UPI_URI_RE.findall(raw)
    parsed_upi: Dict[str, Any] = {}
    for idx, uri in enumerate(upi_matches, 1):
        parsed = urllib.parse.urlparse(uri)
        qs = urllib.parse.parse_qs(parsed.query)
        pa = (qs.get("pa", [""])[0] or "").strip()
        pn = (qs.get("pn", [""])[0] or "").strip()
        am_raw = (qs.get("am", [""])[0] or "").strip()
        tn = (qs.get("tn", [""])[0] or "").strip()
        mode = (qs.get("mode", [""])[0] or "").strip()

        parsed_upi = {"vpa": pa, "payee_name": pn, "amount": am_raw, "note": tn, "mode": mode}
        if not pa or "@" not in pa:
            score += _add_flag(flags, f"FRAUD-VPA-{idx:02d}", "HIGH", 25, "Malformed UPI VPA address without @handle")
        else:
            local_part, psp = pa.lower().split("@", 1)
            if any(h in local_part for h in IMPERSONATION_HANDLES):
                score += _add_flag(
                    flags,
                    f"FRAUD-IMP-{idx:02d}",
                    "CRITICAL",
                    32,
                    f"VPA local-part '{local_part}' uses impersonation keyword ('{psp}' handle)",
                )
            if pn and any(b in pn.lower() for b in ("refund", "lottery", "kyc", "prize", "customer care")):
                score += _add_flag(
                    flags,
                    f"FRAUD-PN-{idx:02d}",
                    "HIGH",
                    22,
                    f"Payee display name '{pn}' impersonates refund/support authority",
                )

        if am_raw:
            try:
                am_val = float(am_raw)
                if am_val >= 5000 and any(w in lower for w in ("refund", "receive", "cashback", "win", "prize", "credit")):
                    score += _add_flag(
                        flags,
                        f"FRAUD-AMT-{idx:02d}",
                        "CRITICAL",
                        30,
                        f"Outbound debit amount Rs.{am_val:,.0f} disguised as an inbound refund/credit",
                    )
            except ValueError:
                score += _add_flag(flags, f"FRAUD-AMT-{idx:02d}", "MEDIUM", 12, "Non-numeric UPI amount parameter")

    urls = URL_RE.findall(raw)
    detected_hosts: List[str] = []
    for idx, url in enumerate(urls, 1):
        host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
        if host:
            detected_hosts.append(host)
        if host in SHORTENER_DOMAINS:
            score += _add_flag(
                flags,
                f"FRAUD-URL-{idx:02d}",
                "HIGH",
                24,
                f"Obfuscated shortener link ({host}) hides final phishing domain",
            )
        elif host and not host.endswith(".gov.in") and any(
            k in host for k in ("sbi", "hdfc", "icici", "paytm", "phonepe", "uidai", "npci", "epfo")
        ) and not any(host == legit or host.endswith("." + legit) for legit in (
            "onlinesbi.sbi", "hdfcbank.com", "icicibank.com", "paytm.com", "phonepe.com", "uidai.gov.in", "npci.org.in"
        )):
            score += _add_flag(
                flags,
                f"FRAUD-DOM-{idx:02d}",
                "CRITICAL",
                34,
                f"Lookalike domain '{host}' spoofs a regulated bank or payment brand",
            )
        if url.lower().startswith("http://"):
            score += _add_flag(flags, f"FRAUD-TLS-{idx:02d}", "MEDIUM", 10, f"Unencrypted HTTP link ({host})")

    phones = PHONE_RE.findall(combined)
    if phones and any(k in lower for k in ("customer care", "helpline", "kyc", "support", "callback", "blocked")):
        score += _add_flag(
            flags,
            "FRAUD-TEL-01",
            "HIGH",
            22,
            f"Personal 10-digit mobile number ({phones[0]}) impersonating official bank customer care",
        )

    hit_num = 1
    for term, weight, detail in URGENCY_TRIGGERS:
        if term in lower:
            sev = "CRITICAL" if weight >= 30 else ("HIGH" if weight >= 20 else "MEDIUM")
            score += _add_flag(flags, f"FRAUD-LURE-{hit_num:02d}", sev, weight, detail)
            hit_num += 1

    capped_score = min(100, score)
    if capped_score >= 55:
        verdict = "HIGH_RISK_SCAM"
        action = "DO NOT APPROVE, INSTALL OR CLICK. Decline any UPI collect request and report the sender via National Cybercrime Helpline 1930 / chakshu.sancharsaathi.gov.in. Entering a UPI PIN always authorizes an outbound debit."
    elif capped_score >= 25:
        verdict = "CAUTION_VERIFY"
        action = "Do not act from links in SMS/WhatsApp. Independently verify inside your official bank/payment app before transferring or clicking."
    else:
        verdict = "LOW_RISK"
        action = "No obvious phishing URL, APK lure, or PIN-trap markers detected. Confirm the verified payee name before approving."

    channel = "Malicious APK Lure" if apks else ("UPI Intent URI" if parsed_upi else ("SMS + Web Link" if urls else "Plain Text Alert"))
    anatomy = [
        {"field": "Channel / Threat Vector", "value": channel},
        {"field": "Extracted VPA", "value": parsed_upi.get("vpa") or "None present"},
        {"field": "Display Payee / Requested", "value": f"{parsed_upi.get('payee_name') or '--'} | Rs.{parsed_upi['amount']}" if parsed_upi.get("amount") else (parsed_upi.get("payee_name") or "None present")},
        {"field": "Hosts / Domains", "value": ", ".join(detected_hosts) if detected_hosts else "No web hosts"},
        {"field": "Phones / APK IOCs", "value": ", ".join(apks + phones) if (apks or phones) else "None detected"},
        {"field": "PIN-For-Receipt Trap", "value": "DETECTED" if any("PIN" in f["detail"] for f in flags) else "Not detected"},
    ]

    return {
        "success": True,
        "risk_score": capped_score,
        "verdict": verdict,
        "recommended_action": action,
        "parsed_upi": parsed_upi,
        "detected_urls": urls[:6],
        "anatomy": anatomy,
        "flags": flags,
    }
