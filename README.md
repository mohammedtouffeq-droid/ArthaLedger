# ArthaLedger

**Evidence-Cited Indian Personal & Small-Business Financial Intelligence Workbench**  
Built for **Arthaton 2026** (`AI for Finance`).

> **Demo Video (YouTube):** *[Upload under-5-minute working walkthrough to YouTube and paste Public/Unlisted URL here before submitting]*

---

## 1. What Makes ArthaLedger Different

Most AI finance wrappers send numbers to an LLM and hope arithmetic comes back right. **ArthaLedger** separates **verified computation** from **cited explanation & multimodal inspection**:

1. **UPI, Bank SMS & CSV Ledger (`engines/sms_ledger.py`):**
   - Imports bank-statement CSV files (`Date, Description, Debit, Credit`) or UPI SMS alerts, supports live search/filter + quick inline transaction entry, flags statistical outlier debits (`>= 2.8x` median) and recurring subscriptions with annualized cost, and exports RFC-4180 CSV statements.

2. **UPI Collect, SMS & Screenshot Forensics (`engines/fraud_shield.py`):**
   - Breaks any payment link or `upi://pay?...` collect URI into a structural **Attack Anatomy** grid (Channel, VPA handle, Payee Display Name, Requested Amount, Spoofed/Shortener Domain, PIN-For-Receipt Trap) and emits rule-cited risk weights (`0–100`), plus direct screenshot upload for multimodal AI inspection.

3. **Budget 2025 Indian Income Tax, Crossover Solver & SIP/EMI Optimizer (`engines/tax_wealth.py`):**
   - Exact **Union Budget 2025 Section 115BAC (FY 2025–26 / FY 2026–27)** progressive slabs, Rs.75,000 salaried Standard Deduction, Section 87A rebate up to Rs.12,00,000 taxable income (Rs.12.75L salaried tax-free), marginal relief above Rs.12L, 4% Cess, **Algebraic Deduction Breakeven Point**, monthly post-tax take-home, step-up SIP nominal vs. real purchasing power curve, and Loan/EMI prepayment amortization.

4. **Live Public AMFI Mutual Funds & Historical Paper Backtester (`engines/market_backtest.py`):**
   - Queries official public AMFI Indian Mutual Fund schemes via `https://api.mfapi.in` (with offline historical benchmark fallback), backtests SMA Crossover and Drawdown Dip Accumulation strategies (non-advisory, zero live trading), computes **Sharpe Ratio, Annualized Volatility %, CAGR, Max Drawdown %**, and quantifies **Direct vs. Regular Plan 1% Trail Commission Leakage**.

5. **Interactive SME GST Invoice & 90-Day Working Capital Stress (`engines/sme_gst.py`):**
   - Dynamic multi-line invoice builder (`0/5/12/18/28%` slabs), Intra-state (`CGST + SGST`) vs. Inter-state (`IGST`), Input Tax Credit offset, and 90-day Base vs. 35%-Delayed-Receivables cash runway simulation.

6. **Perplexity-Style Grounded AI Copilot (`engines/copilot.py`):**
   - Computes a **5-Pillar Financial Health Index (`0–100`)**, anchors every insight to interactive citation badges (`[TXN-04]`, `[TAX-115BAC]`, `[FRAUD-LURE-01]`, `[MF-DIRECT-DRAG]`, `[GST-ITC-SET]`) that jump directly to the referenced transaction/module, and emits 1-click **"Apply What-If Simulation"** actions. Supports **Google Gemini** (`gemini-2.5-flash`), **BharatCode API** (`glm-5.3-flash` vision + text), and an offline deterministic grounded engine.

---

## 2. AI Models, APIs & Data Sources Used

| Component | Model / Endpoint | Role |
|---|---|---|
| **Google Gemini API** | `gemini-2.5-flash` / `gemini-2.0-flash` | Financial synthesis & multimodal receipt/payment screenshot inspection |
| **BharatCode Model API** | `glm-5.3-flash`, `deepseek-chat` | OpenAI-compatible multimodal & text auditing via `https://bharatcode.ai/api/model/v1/chat/completions` |
| **Public Market Feed** | AMFI India (`https://api.mfapi.in`) | Real public historical Mutual Fund NAVs for non-advisory paper backtesting |
| **Deterministic Grounding** | Built-in `artha-deterministic-citation-v2` | Reproducible offline financial reasoning & 5-pillar Financial Health Index |
| **Runtime & Deployment** | Python 3.12 Standard Library + Vercel WSGI (`api/index.py`) | Zero external pip dependencies for core app; `script-src 'self'` strict CSP |

---

## 3. Compliance & Security

- **Synthetic / Public Data Only:** All default scenarios use synthetic alerts and `.example` / `@okexample` placeholders. Never place real PAN, bank details, UPI PINs, or broker keys in code.
- **No Real Trades:** Market simulation runs strictly on public AMFI NAVs or synthetic benchmark proxies.
- **Zero Repo Secrets:** API keys can be loaded from gitignored `.env` (`GEMINI_API_KEY` / `BHARATCODE_API_KEY`) or provided per-tab inside browser `sessionStorage`.

---

## 4. How to Run Locally & Test

```bash
git clone https://github.com/mohammedtouffeq-droid/ArthaLedger.git
cd ArthaLedger
python app.py
```

Open **`http://127.0.0.1:8080`** in your browser. Use the top bar to switch personas, toggle Paper/Dark theme, or click **Print Dossier** for an instant PDF/print audit report.

### Run Automated Test Suite

```bash
python -m unittest discover -s tests -v
```
