# ArthaLedger

**Evidence-Cited Indian Personal & Small-Business Financial Intelligence Workbench**  
Built for **Arthaton 2026** (`AI for Finance`).

> **Demo Video (YouTube):** *[Upload under-5-minute working walkthrough to YouTube and paste Public/Unlisted URL here before submitting]*

---

## 1. What Makes ArthaLedger Different

Most AI finance wrappers send numbers to an LLM and hope arithmetic comes back right. **ArthaLedger** separates **verified computation** from **cited explanation & multimodal inspection**:

1. **UPI, Bank SMS & CSV Ledger (`engines/sms_ledger.py`):**
   - Imports bank-statement CSV files (`Date, Description, Debit, Credit`) or UPI SMS alerts, enforces word-boundary classification across categories and `Subscriptions & Cloud`, supports live search/filter + monthly budget cap utilization bar + quick inline transaction entry, flags statistical outlier debits (`>= 2.8x` median), and exports RFC-4180 CSV statements.

2. **UPI Collect, APK, Homoglyph & Screenshot Forensics (`engines/fraud_shield.py`):**
   - Breaks payment links, SMS/WhatsApp alerts, Android sideload bait (`.apk` trojans like `eChallan_RTO_Verify.apk`), Unicode zero-width/Cyrillic homoglyphs (`FRAUD-HOMO-01`), personal 10-digit helpline numbers (`FRAUD-TEL-01`), and `upi://pay?...` collect URIs into a structural **Attack Anatomy** grid and rule-cited risk weights (`0–100`), plus direct screenshot upload for multimodal AI inspection.

3. **Budget 2025 Indian Income Tax, Slab Waterfall, Goal Reverse-SIP & LTCG/STCG (`engines/tax_wealth.py`):**
   - Exact **Union Budget 2025 Section 115BAC (FY 2025–26 / FY 2026–27)** progressive slab waterfall table (`#taxSlabTableBody`), Rs.75,000 salaried Standard Deduction, Section 87A rebate up to Rs.12,00,000 taxable income (Rs.12.75L salaried tax-free), marginal relief above Rs.12L, 4% Cess, **Algebraic Deduction Breakeven Point**, monthly post-tax take-home, step-up SIP nominal vs. real purchasing power curve, **Inflation-Adjusted Goal Reverse-SIP Solver** (`solve_goal_sip`), **Equity MF LTCG (12.5% above Rs.1.25L) / STCG (20%) Tax Estimator** (`estimate_equity_mf_tax`), and Loan/EMI prepayment amortization.

4. **Live Public AMFI Mutual Funds & Historical Paper Backtester (`engines/market_backtest.py`):**
   - Queries official public AMFI Indian Mutual Fund schemes via `https://api.mfapi.in` (with offline historical benchmark fallback), backtests SMA Crossover and Drawdown Dip Accumulation strategies (non-advisory, zero live trading), computes **Sharpe Ratio, Annualized Volatility %, CAGR, Max Drawdown %**, and quantifies **Direct vs. Regular Plan 1% Trail Commission Leakage**.

5. **Interactive SME GST Invoice & 90-Day Working Capital Stress (`engines/sme_gst.py`):**
   - Dynamic multi-line invoice builder (`0/5/12/18/28%` slabs), Intra-state (`CGST + SGST`) vs. Inter-state (`IGST`), Input Tax Credit offset, and 90-day Base vs. 35%-Delayed-Receivables cash runway simulation.

6. **Multi-Turn Grounded AI Copilot & Interactive Product Guide (`engines/copilot.py` & `static/`):**
   - Computes a **5-Pillar Financial Health Index (`0–100`)**, supports multi-turn conversation memory with interactive citation badges (`[TXN-04]`, `[TAX-115BAC]`, `[FRAUD-APK-01]`, `[MF-DIRECT-DRAG]`, `[GST-ITC-SET]`) that jump directly to referenced transactions/modules, emits 1-click **"Apply What-If Simulation"** actions, and opens with a clean collapsible SVG analyst welcome guide featuring smooth scroll-parallax depth (`requestAnimationFrame`) and top scroll-progress choreography. Supports **Google Gemini** (`gemini-3.5-flash-lite` / `gemini-3-flash-preview` / `gemini-3.8-flash`), **BharatCode API** (`glm-5.3-flash` vision + text), and an offline deterministic grounded engine.

---

## 2. AI Models, APIs & Data Sources Used

| Component | Model / Endpoint | Role |
|---|---|---|
| **Google Gemini API** | `gemini-3.5-flash-lite` / `gemini-3-flash-preview` / `gemini-3.8-flash` | Multi-turn grounded synthesis & multimodal receipt/payment screenshot inspection |
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
