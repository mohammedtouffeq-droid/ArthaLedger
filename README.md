# ArthaLedger

**Evidence-Cited Personal & Small-Business Financial Intelligence Terminal for India**  
Built for **Arthaton 2026** (`AI for Finance`).

> **Demo Video (YouTube):** *[Upload under-5-minute working walkthrough to YouTube and paste Public/Unlisted URL here before submitting]*

---

## 1. What ArthaLedger Does

Most financial AI assistants guess arithmetic inside an LLM and fabricate advice without auditability. **ArthaLedger** flips that model with an **evidence-first, deterministic computation core**:

1. **UPI & Bank SMS Ledger (`engines/sms_ledger.py`):**  
   Parses Indian bank/UPI debit and credit alerts, categorizes spends across Indian merchants (Swiggy, Blinkit, Jio, Metro, utilities, rent), detects stealth recurring subscriptions and statistical outlier spends (`>= 2.8x` median), computes monthly burn rate, and exports RFC-4180 CSV statements with `[TXN-XX]` citation IDs.

2. **UPI Collect & Phishing Shield (`engines/fraud_shield.py`):**  
   Inspects suspicious payment SMS messages, `upi://pay?...` deep links, obfuscated URL shorteners (`bit.ly`, `tinyurl.com`), lookalike bank domains, remote-access lures (`AnyDesk`/`TeamViewer`), and PIN-for-refund traps — returning an explainable `0–100` risk score with `[FRAUD-...]` rule citations. Supports multimodal receipt/screenshot inspection when connected to Gemini or BharatCode Vision models.

3. **Indian Income Tax Regime & Wealth Optimizer (`engines/tax_wealth.py`):**  
   - Compares **Old Regime vs. New Regime (Section 115BAC, Union Budget 2025 slabs for FY 2025–26 / FY 2026–27)** including the Rs.75,000 salaried Standard Deduction, Section 87A rebate up to Rs.12,00,000 taxable income (Rs.12,75,000 salaried tax-free), marginal relief above Rs.12L, Sections 80C / 80D / 80CCD(1B) / HRA, and 4% Health & Education Cess.
   - Simulates step-up monthly **SIP compounding vs. inflation-adjusted purchasing power** and reducing-balance **Loan/EMI prepayment savings**.

4. **Historical & Synthetic NSE Paper Backtester (`engines/market_backtest.py`):**  
   Runs strictly non-advisory historical/synthetic index proxies (`NIFTY50_PROXY`, `IT_LARGE_CAP`, `BANK_INDEX_PROXY`) with SMA Crossover and Drawdown Dip Accumulation strategies (10 bps slippage model), computing Total Return %, CAGR %, Max Drawdown %, and Win Rate vs. Benchmark Buy-and-Hold.

5. **SME GST Invoice & 90-Day Cash Runway (`engines/sme_gst.py`):**  
   Computes intra-state (`CGST + SGST`) vs. inter-state (`IGST`) line items, offsets Input Tax Credit (`ITC`), and models 90-day Base vs. 35%-Delayed-Receivables cashflow stress.

6. **Citation-Grounded AI Financial Copilot (`engines/copilot.py`):**  
   Synthesizes insights across all active modules using verifiable citation tags (`[TXN-04]`, `[TAX-115BAC]`, `[FRAUD-LURE-01]`, `[BACKTEST-PAPER]`, `[GST-ITC-SET]`). Supports uploaded receipt/UPI screenshots via multimodal LLMs and includes a built-in deterministic fallback engine for zero-key reproducibility.

---

## 2. AI Models, APIs & Open-Source Libraries Used

| Component | Technology / Model | Usage |
|---|---|---|
| **Google Gemini API** | `gemini-2.5-flash` / `gemini-2.0-flash` | Natural-language financial reasoning and multimodal receipt/payment screenshot analysis |
| **BharatCode Model API** | `glm-5.3-flash` (vision + text), `deepseek-chat` | OpenAI-compatible multimodal screenshot/text audit via `https://bharatcode.ai/api/model/v1/chat/completions` |
| **Deterministic Engine Core** | Built-in `artha-deterministic-citation-v1` | Zero-key offline grounded fallback & verified arithmetic across all 5 modules |
| **Backend Runtime** | Python 3.12 Standard Library (`http.server`, `json`, `csv`, `urllib`, `pathlib`, `re`, `statistics`) | Zero external runtime package dependencies; Vercel serverless adapter (`api/index.py`) |
| **Frontend UI & Charts** | Vanilla HTML5, CSS3, ES6 JavaScript, Canvas 2D | Responsive desktop/mobile ledger interface with strict `script-src 'self'` CSP compliance |

---

## 3. Compliance & Safety Architecture

- **Synthetic Data Only:** All bundled personas (`sample_data.py`) use synthetic transactions, `.example` links, and non-live VPA placeholders (`@okexample`).
- **Zero Secrets in Repository:** Never commit API keys, bank details, PANs, or real UPI IDs. Keys may be supplied via local `.env` environment variables (`GEMINI_API_KEY` or `BHARATCODE_API_KEY`) or entered at runtime inside the browser UI's `sessionStorage` modal.
- **No Real Trading:** The Market Backtester runs exclusively on historical/synthetic proxy data and explicitly blocks live brokerage connectivity.
- **Hardened HTTP Server:** Enforces `Content-Security-Policy: script-src 'self'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Path.relative_to` traversal protection, and bounded `6 MB` payload ceilings.

---

## 4. How to Run Locally

```bash
# 1. Clone the repository
git clone https://github.com/mohammedtouffeq-droid/ArthaLedger.git
cd ArthaLedger

# 2. (Optional) Configure AI API keys in environment variables (app also works out of the box in Deterministic Mode)
# copy .env.example .env

# 3. Start the server (requires Python 3.10+, zero external runtime dependencies)
python app.py
```

Open **`http://127.0.0.1:8080`** in your browser. Click **Load Scenario** (`Student Budget`, `Salaried Engineer`, or `Local SME Trader`) to inspect every module end-to-end.

### Run Automated Tests

```bash
python -m unittest discover -s tests -v
```
