"""UPI and Indian bank SMS ledger parser, categorizer, and cashflow analyzer."""
from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from statistics import median
from typing import Any, Dict, List

AMOUNT_RE = re.compile(
    r"(?:rs\.?|inr|₹)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"\b(\d{1,2}[-/][A-Za-z0-9]{2,3}(?:[-/]\d{2,4})?|\d{4}-\d{2}-\d{2})\b"
)
MERCHANT_TO_RE = re.compile(
    r"(?:to|at|towards|vpa|info|for)\s+([A-Za-z0-9@._& -]{2,40}?)(?:\s+(?:on|via|ref|utr|upi|avl|bal|$)|[.,;]|$)",
    re.IGNORECASE,
)

CATEGORY_RULES: List[tuple[str, tuple[str, ...]]] = [
    ("Food & Dining", ("swiggy", "zomato", "chai", "cafe", "bakery", "tiffin", "canteen", "restaurant", "dominos", "kfc")),
    ("Groceries & Essentials", ("blinkit", "zepto", "bigbasket", "dmart", "kirana", "milk", "dairy", "mart", "instamart")),
    ("Transport & Fuel", ("uber", "ola", "rapido", "metro", "irctc", "petrol", "indian oil", "hpcl", "bpcl", "bus", "auto")),
    ("Utilities & Telecom", ("jio", "airtel", "vi ", "bsnl", "electricity", "bescom", "tsspdcl", "water", "gas", "broadband", "recharge")),
    ("Education & Books", ("udemy", "coursera", "book", "tuition", "college", "exam", "stationery", "xerox", "print")),
    ("Subscriptions & Cloud", ("netflix", "spotify", "youtube", "github", "vercel", "aws", "icloud", "prime", "hotstar")),
    ("Shopping & Electronics", ("amazon", "flipkart", "myntra", "robu", "croma", "electronics")),
    ("Rent & Transfers", ("rent", "pg ", "hostel", "dad", "mom", "transfer", "imps", "neft")),
]


def _classify_merchant(line_lower: str, tx_type: str) -> str:
    if tx_type == "credit":
        if any(k in line_lower for k in ("salary", "stipend", "freelance", "invoice", "settlement", "client")):
            return "Earned Income"
        if any(k in line_lower for k in ("refund", "cashback", "reversal")):
            return "Refund & Cashback"
        return "Allowance & Transfers In"
    for cat, keywords in CATEGORY_RULES:
        if any(k in line_lower for k in keywords):
            return cat
    return "General & Misc"


def parse_sms_ledger(raw_text: str, monthly_budget_target: float = 0.0) -> Dict[str, Any]:
    """Parses raw UPI/bank SMS lines or simple CSV entries into structured transactions."""
    lines = [ln.strip() for ln in str(raw_text or "").splitlines() if ln.strip()]
    transactions: List[Dict[str, Any]] = []
    category_totals: Dict[str, float] = defaultdict(float)
    merchant_counts: Dict[str, int] = defaultdict(int)
    debit_amounts: List[float] = []

    total_spent = 0.0
    total_income = 0.0

    for idx, line in enumerate(lines, 1):
        amt_match = AMOUNT_RE.search(line)
        if not amt_match:
            # Fallback: plain "Merchant, amount" format
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
            words = [w for w in re.split(r"[\s,|]+", line) if not re.match(r"^(rs|inr|₹|\d)", w, re.I)]
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
    for tx in transactions:
        if tx["type"] == "debit" and med_debit > 0 and tx["amount"] >= max(1500.0, med_debit * 2.8):
            anomalies.append({
                "citation": tx["id"],
                "reason": f"Outlier spend Rs.{tx['amount']:,.0f} at {tx['merchant']} ({tx['amount']/med_debit:.1f}x median transaction)",
            })
        if tx["type"] == "debit" and tx["category"] == "Subscriptions & Cloud":
            anomalies.append({
                "citation": tx["id"],
                "reason": f"Recurring subscription debit Rs.{tx['amount']:,.0f} ({tx['merchant']}) - verify active usage",
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
