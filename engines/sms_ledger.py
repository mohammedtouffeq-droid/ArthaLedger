"""UPI, Indian bank SMS, and bank-statement CSV ledger parser and cashflow analyzer."""
from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from statistics import median
from typing import Any, Dict, List

AMOUNT_RE = re.compile(
    r"(?:rs\.?|inr)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"\b(\d{1,2}[-/][A-Za-z0-9]{2,3}(?:[-/]\d{2,4})?|\d{4}-\d{2}-\d{2})\b"
)
MERCHANT_TO_RE = re.compile(
    r"(?:to|at|towards|from|vpa|info|for)\s+([A-Za-z0-9@._& -]{2,40}?)(?:\s+(?:on|via|ref|utr|upi|avl|bal|$)|[.,;]|$)",
    re.IGNORECASE,
)

CATEGORY_RULES: List[tuple[str, tuple[str, ...]]] = [
    ("Subscriptions & Cloud", ("autodebit", "subscription", "netflix", "spotify", "youtube", "github", "vercel", "aws", "icloud", "prime", "hotstar", "streaming")),
    ("Food & Dining", ("swiggy", "zomato", "chai", "cafe", "bakery", "tiffin", "canteen", "restaurant", "dominos", "kfc")),
    ("Groceries & Essentials", ("blinkit", "zepto", "bigbasket", "dmart", "kirana", "milk", "dairy", "mart", "instamart")),
    ("Transport & Fuel", ("uber", "ola", "rapido", "metro", "irctc", "petrol", "indian oil", "hpcl", "bpcl", "bus", "auto", "rail", "transit")),
    ("Utilities & Telecom", ("jio", "airtel", "bsnl", "electricity", "bescom", "tsspdcl", "water", "gas", "broadband", "recharge")),
    ("Education & Books", ("udemy", "coursera", "book", "textbook", "tuition", "college", "exam", "stationery", "xerox", "print")),
    ("Shopping & Electronics", ("amazon", "flipkart", "myntra", "robu", "croma", "electronics", "monitor")),
    ("Rent & Transfers", ("rent", "pg", "hostel", "dad", "mom", "transfer", "imps", "neft")),
]


def _classify_merchant(line_lower: str, tx_type: str) -> str:
    if tx_type == "credit":
        if any(re.search(rf"\b{re.escape(k)}\b", line_lower) for k in ("salary", "stipend", "freelance", "invoice", "settlement", "client")):
            return "Earned Income"
        if any(re.search(rf"\b{re.escape(k)}\b", line_lower) for k in ("refund", "cashback", "reversal")):
            return "Refund & Cashback"
        return "Allowance & Transfers In"
    for cat, keywords in CATEGORY_RULES:
        if any(re.search(rf"\b{re.escape(k)}\b", line_lower) for k in keywords):
            return cat
    return "General & Misc"


def _parse_amount_num(raw: Any) -> float:
    cleaned = re.sub(r"[^0-9.]", "", str(raw or "").replace(",", ""))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def csv_statement_to_lines(csv_text: str) -> str:
    """Converts common Indian bank/UPI CSV or TSV exports (HDFC, SBI, ICICI, PhonePe) into normalized lines."""
    raw = str(csv_text or "").lstrip("\ufeff").strip()
    if not raw:
        return ""
    all_lines = [ln for ln in raw.splitlines() if ln.strip()]
    header_idx = 0
    for idx, ln in enumerate(all_lines[:10]):
        low = ln.lower()
        if any(k in low for k in ("date", "narration", "description", "particular", "remarks")) and any(c in ln for c in (",", "\t", ";", "|")):
            header_idx = idx
            break
    table_text = "\n".join(all_lines[header_idx:])
    sample_line = all_lines[header_idx]
    delim = "\t" if "\t" in sample_line else (";" if sample_line.count(";") >= 2 else ("|" if sample_line.count("|") >= 2 else ","))

    reader = csv.DictReader(io.StringIO(table_text), delimiter=delim)
    if not reader.fieldnames:
        return ""
    fields = {f.lower().strip(): f for f in reader.fieldnames if f}
    date_col = next((fields[k] for k in fields if "date" in k), None)
    desc_col = next((fields[k] for k in fields if any(w in k for w in ("narration", "desc", "remark", "merchant", "particular", "title", "detail"))), None)
    debit_col = next((fields[k] for k in fields if ("debit" in k or "withdraw" in k or re.search(r"\bdr\b", k))), None)
    credit_col = next((fields[k] for k in fields if ("credit" in k or "deposit" in k or re.search(r"\bcr\b", k))), None)
    amt_col = next((fields[k] for k in fields if "amount" in k), None)
    type_col = next((fields[k] for k in fields if any(w in k for w in ("type", "cr/dr", "dr/cr", "mode"))), None)

    out_lines: List[str] = []
    for row in reader:
        dt = (row.get(date_col, "") if date_col else "").strip() or "01-Nov-2026"
        desc = (row.get(desc_col, "") if desc_col else "").strip() or "Bank Entry"
        dr = _parse_amount_num(row.get(debit_col, 0)) if debit_col else 0.0
        cr = _parse_amount_num(row.get(credit_col, 0)) if credit_col else 0.0
        if dr > 0:
            out_lines.append(f"Debited Rs.{dr:.2f} via UPI to {desc} on {dt}.")
        elif cr > 0:
            out_lines.append(f"Credited Rs.{cr:.2f} towards {desc} on {dt}.")
        elif amt_col:
            raw_amt_cell = str(row.get(amt_col, "")).strip()
            amt = _parse_amount_num(raw_amt_cell)
            if amt > 0:
                t_val = (str(row.get(type_col, "") if type_col else "") + " " + raw_amt_cell).lower()
                is_cr = bool(re.search(r"\b(cr|credit|in)\b", t_val))
                verb = "Credited" if is_cr else "Debited"
                prep = "towards" if is_cr else "via UPI to"
                out_lines.append(f"{verb} Rs.{amt:.2f} {prep} {desc} on {dt}.")
    return "\n".join(out_lines)


def parse_sms_ledger(raw_text: str, monthly_budget_target: float = 0.0) -> Dict[str, Any]:
    """Parses raw UPI/bank SMS lines or CSV statements into categorized transactions with citations."""
    text = str(raw_text or "").lstrip("\ufeff").strip()
    first_lines = "\n".join(text.splitlines()[:10]).lower()
    if any(k in first_lines for k in ("date", "amount", "debit", "narration", "description", "withdrawal", "deposit")) and any(c in first_lines for c in (",", "\t", ";", "|")):
        converted = csv_statement_to_lines(text)
        if converted:
            text = converted

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    transactions: List[Dict[str, Any]] = []
    category_totals: Dict[str, float] = defaultdict(float)
    merchant_counts: Dict[str, int] = defaultdict(int)
    debit_amounts: List[float] = []

    total_spent = 0.0
    total_income = 0.0

    for idx, line in enumerate(lines, 1):
        amt_match = AMOUNT_RE.search(line)
        if not amt_match:
            num_match = re.search(r"(?:^|[,:\s])([0-9]+(?:\.[0-9]{1,2})?)\s*$", line)
            if not num_match:
                continue
            amount = float(num_match.group(1))
        else:
            amount = float(amt_match.group(1).replace(",", ""))

        if amount <= 0:
            continue

        lower = line.lower()
        is_credit = any(w in lower for w in ("credited", "received", "deposited", "cashback", "refund", "salary", "income"))
        is_debit = any(w in lower for w in ("debited", "paid", "spent", "sent", "withdrawn", "purchase", "upi/dr"))
        tx_type = "credit" if (is_credit and not is_debit) else "debit"

        date_m = DATE_RE.search(line)
        tx_date = date_m.group(1) if date_m else f"Entry {idx}"

        merch_m = MERCHANT_TO_RE.search(line)
        merchant = merch_m.group(1).strip(" .:-") if merch_m else ""
        if not merchant:
            words = [w for w in re.split(r"[\s,|]+", line) if not re.match(r"^(rs|inr|\d)", w, re.I)]
            merchant = " ".join(words[:3])[:32] or "UPI Counterparty"

        category = _classify_merchant(lower, tx_type)
        ref_id = f"TXN-{idx:02d}"

        if tx_type == "credit":
            total_income += amount
        else:
            total_spent += amount
            category_totals[category] += amount
            merchant_counts[merchant.upper()] += 1
            debit_amounts.append(amount)

        transactions.append({
            "id": ref_id,
            "date": tx_date,
            "type": tx_type,
            "amount": round(amount, 2),
            "merchant": merchant,
            "category": category,
            "raw_excerpt": line[:140],
        })

    med_debit = median(debit_amounts) if debit_amounts else 0.0
    anomalies: List[Dict[str, Any]] = []
    subscription_annual_total = 0.0
    for tx in transactions:
        if tx["type"] == "debit" and med_debit > 0 and tx["amount"] >= max(1500.0, med_debit * 2.8):
            anomalies.append({
                "citation": tx["id"],
                "severity": "HIGH",
                "reason": f"Outlier debit Rs.{tx['amount']:,.0f} at {tx['merchant']} ({tx['amount']/med_debit:.1f}x median spend)",
            })
        if tx["type"] == "debit" and tx["category"] == "Subscriptions & Cloud":
            subscription_annual_total += tx["amount"] * 12.0
            anomalies.append({
                "citation": tx["id"],
                "severity": "MEDIUM",
                "reason": f"Recurring subscription Rs.{tx['amount']:,.0f}/mo (Rs.{tx['amount']*12:,.0f}/yr) at {tx['merchant']}",
            })

    sorted_cats = sorted(
        (
            {
                "category": cat,
                "amount": round(val, 2),
                "share_pct": round((val / total_spent) * 100, 1) if total_spent > 0 else 0.0,
            }
            for cat, val in category_totals.items()
        ),
        key=lambda x: x["amount"],
        reverse=True,
    )

    net_cashflow = round(total_income - total_spent, 2)
    savings_rate_pct = round(((total_income - total_spent) / total_income) * 100, 1) if total_income > 0 else 0.0
    budget = float(monthly_budget_target or 0.0)
    budget_variance = round(budget - total_spent, 2) if budget > 0 else 0.0

    repeat_merchants = [
        {"merchant": m, "count": c}
        for m, c in sorted(merchant_counts.items(), key=lambda kv: kv[1], reverse=True)
        if c >= 2
    ][:5]

    return {
        "success": True,
        "transaction_count": len(transactions),
        "total_income": round(total_income, 2),
        "total_spent": round(total_spent, 2),
        "net_cashflow": net_cashflow,
        "savings_rate_pct": savings_rate_pct,
        "budget_target": round(budget, 2),
        "budget_variance": budget_variance,
        "median_debit": round(med_debit, 2),
        "subscription_annual_runrate": round(subscription_annual_total, 2),
        "categories": sorted_cats,
        "repeat_merchants": repeat_merchants,
        "anomalies": anomalies,
        "transactions": transactions,
    }


def export_ledger_csv(transactions: List[Dict[str, Any]]) -> str:
    """Renders parsed transactions into clean RFC-4180 CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Citation ID", "Date", "Type", "Category", "Merchant", "Amount (INR)"])
    for tx in transactions:
        writer.writerow([
            tx.get("id", ""),
            tx.get("date", ""),
            tx.get("type", ""),
            tx.get("category", ""),
            tx.get("merchant", ""),
            tx.get("amount", 0.0),
        ])
    return buf.getvalue()


def generate_sample_bank_pdf() -> bytes:
    """Generates a valid synthetic Indian bank statement PDF binary in pure Python for live judge testing."""
    lines = [
        "ARTHALEDGER SYNTHETIC INDIAN BANK PASSBOOK STATEMENT (DEMO ONLY)",
        "Account Holder: Artha Demo Student | Period: 01-Nov-2026 to 15-Nov-2026",
        "01-Nov-2026 | Credited Rs.28500.00 towards Internship Stipend & Freelance Settlement.",
        "03-Nov-2026 | Debited Rs.449.00 via UPI to Swiggy Instamart Order.",
        "05-Nov-2026 | Debited Rs.199.00 via UPI Autodebit to Spotify Premium Subscription.",
        "07-Nov-2026 | Debited Rs.649.00 via UPI Autodebit to Cloud Streaming Bundle Subscription.",
        "09-Nov-2026 | Debited Rs.2150.00 via UPI to Engineering Textbooks & Lab Printouts.",
        "12-Nov-2026 | Debited Rs.5200.00 via UPI to Hostel Mess & Room Rent Share.",
    ]
    ops = ["BT", "/F1 10 Tf", "40 740 Td"]
    for idx, line in enumerate(lines):
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if idx > 0:
            ops.append("0 -18 Td")
        ops.append(f"({safe}) Tj")
    ops.append("ET")
    stream_bytes = "\n".join(ops).encode("latin-1")

    objs = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        f"4 0 obj << /Length {len(stream_bytes)} >> stream\n".encode("latin-1") + stream_bytes + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]

    buf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(buf))
        buf.extend(obj)

    xref_pos = len(buf)
    buf.extend(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for off in offsets[1:]:
        buf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    buf.extend(
        f"trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    return bytes(buf)
