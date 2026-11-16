# ArthaLedger

**Evidence-Cited Indian Personal & Small-Business Financial Intelligence Workbench**  
Built for **Arthaton 2026** (`AI for Finance`).

> **Demo Video (YouTube):** *[Upload under-5-minute working walkthrough to YouTube and paste Public/Unlisted URL here before submitting]*

---

## 1. What Makes ArthaLedger Different

Most AI finance wrappers send numbers to an LLM and hope arithmetic comes back right. **ArthaLedger** separates **verified computation** from **cited explanation & multimodal inspection**:

1. **UPI, Bank SMS & Multi-Bank Statement Auto-Scanner (`engines/sms_ledger.py`):**
   - Auto-detects delimiter (`,`, `\t`, `;`, `|`), strips UTF-8 BOM and bank metadata banners, parses HDFC/SBI/ICICI/PhonePe statement formats (`Withdrawal Amt.`/`Deposit Amt.`, `Cr/Dr` suffixes, `Narration`) or UPI SMS alerts, enforces word-boundary classification across categories and `Subscriptions & Cloud`, supports live search/filter + monthly budget cap utilization bar + quick inline entry, and exports RFC-4180 CSV statements.

2. **Real UPI QR Decoder, APK, Homoglyph & Gemini Vision Forensics (`engines/fraud_shield.py`):**
   - Decodes actual UPI QR code images (`cv2.QRCodeDetector` + Chromium `BarcodeDetector` + live `GET /api/fraud/sample_qr` PNG tester) AND extracts payment/SMS screenshots via live Gemini 3.5 Vision (`POST /api/fraud/vision_scan`), feeding into deterministic rules covering `.apk` malware lures (`FRAUD-APK-01`), Unicode zero-width/Cyrillic homoglyphs (`FRAUD-HOMO-01`), 10-digit personal helpline spoofs (`FRAUD-TEL-01`), and `upi://pay?...` Attack Anatomy (`0–100`).

3. **Budget 2025 Tax, Slab Waterfall, Goal Reverse-SIP, LTCG/STCG & Sec 112A Harvesting (`engines/tax_wealth.py`):**
   - Exact **Union Budget 2025 Section 115BAC (FY 2025–26 / FY 2026–27)** progressive slab waterfall table (`#taxSlabTableBody`), Rs.75,000 salaried Standard Deduction, Section 87A rebate up to Rs.12,00,000 taxable income, marginal relief, **Algebraic Deduction Breakeven**, step-up SIP nominal vs. real curve, **Inflation-Adjusted Goal Reverse-SIP Solver**, **Equity MF LTCG (12.5%) / STCG (20%) Calculator**, **Section 112A Rs.1,25,000 Annual Zero-Tax Harvesting Simulator**, and Loan/EMI prepayment amortization.

4. **Live Public AMFI Mutual Funds, Head-to-Head Quant Compare & Paper Backtester (`engines/market_backtest.py`):**
   - Queries official public AMFI Indian Mutual Fund schemes via `https://api.mfapi.in`, backtests SMA Crossover and Drawdown Dip Accumulation strategies (non-advisory, zero live trading), runs **AMFI Fund-vs-Fund Head-to-Head Comparison (`POST /api/market/compare`)** with Base-100 normalized curves, Sharpe Ratio, Max Drawdown %, **Pearson Return Correlation (r)** overlap warning, and **Direct vs. Regular Plan 1% Trail Commission Leakage**.

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
