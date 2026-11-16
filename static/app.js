(function () {
    'use strict';

    const STATE = {
        personaId: 'student_budget',
        telemetry: {
            ledger: null,
            fraud: null,
            tax: null,
            sip: null,
            emi: null,
            backtest: null,
            sme: null,
        },
        aiSettings: {
            provider: 'auto',
            model: 'gemini-2.5-flash',
            apiKey: '',
        },
        attachedImageData: '',
        attachedImageMime: 'image/png',
    };

    try {
        STATE.aiSettings.provider = sessionStorage.getItem('artha_provider') || 'auto';
        STATE.aiSettings.model = sessionStorage.getItem('artha_model') || 'gemini-2.5-flash';
        STATE.aiSettings.apiKey = sessionStorage.getItem('artha_api_key') || '';
    } catch (_) {}

    const TAB_TITLES = {
        ledger: 'UPI Ledger & Burn Telemetry',
        fraud: 'UPI Collect & Phishing Shield',
        tax: 'Tax Regime & Wealth Engineering',
        market: 'Historical NSE Paper Backtester',
        sme: 'SME GST Invoice & 90-Day Runway',
        copilot: 'Evidence-Cited Financial Copilot',
    };

    function fmtInr(val) {
        const n = Number(val || 0);
        const absStr = Math.round(Math.abs(n)).toLocaleString('en-IN');
        return (n < 0 ? '-Rs.' : 'Rs.') + absStr;
    }

    async function postJson(url, body, extraHeaders) {
        const res = await fetch(url, {
            method: 'POST',
            headers: Object.assign({ 'Content-Type': 'application/json' }, extraHeaders || {}),
            body: JSON.stringify(body || {}),
        });
        return res.json();
    }

    function redrawTabCharts(tabName) {
        if (tabName === 'ledger' && STATE.telemetry.ledger) {
            drawBarChart('ledgerChart', STATE.telemetry.ledger.categories, 'category', 'amount', '#10b981');
        } else if (tabName === 'tax' && STATE.telemetry.sip) {
            drawDualLineChart(
                'wealthChart',
                STATE.telemetry.sip.series,
                'nominal_value',
                'real_value_today_inr',
                'Nominal Value',
                'Real Purchasing Power',
                '#10b981',
                '#e8a317'
            );
        } else if (tabName === 'market' && STATE.telemetry.backtest) {
            drawDualLineChart(
                'backtestChart',
                STATE.telemetry.backtest.equity_curve,
                'strategy_equity',
                'buy_hold_equity',
                'Paper Strategy',
                'Benchmark Hold',
                '#10b981',
                '#38bdf8'
            );
        } else if (tabName === 'sme' && STATE.telemetry.sme) {
            drawDualLineChart(
                'smeChart',
                STATE.telemetry.sme.projection_90d,
                'base_cash',
                'delayed_receivables_cash',
                'Base 90D Cash',
                'Delayed-Receivable Stress',
                '#10b981',
                '#ef4444'
            );
        }
    }

    function setTab(tabName) {
        document.querySelectorAll('.nav-btn').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });
        document.querySelectorAll('.view-panel').forEach((panel) => {
            panel.classList.toggle('active', panel.id === 'view-' + tabName);
        });
        const heading = document.getElementById('activeViewTitle');
        if (heading) heading.textContent = TAB_TITLES[tabName] || 'ArthaLedger';
        requestAnimationFrame(() => redrawTabCharts(tabName));
    }

    function prepareCanvas(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;
        const rect = canvas.getBoundingClientRect();
        const width = Math.max(280, Math.floor(rect.width || 560));
        const height = Number(canvas.getAttribute('height')) || 220;
        const dpr = Math.min(2, window.devicePixelRatio || 1);
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = '#0b1118';
        ctx.fillRect(0, 0, width, height);
        return { ctx, width, height };
    }

    function drawBarChart(canvasId, items, labelKey, valKey, colorHex) {
        const c = prepareCanvas(canvasId);
        if (!c) return;
        const { ctx, width, height } = c;
        if (!items || !items.length) {
            ctx.fillStyle = '#64748b';
            ctx.font = '12px IBM Plex Mono, monospace';
            ctx.fillText('No category telemetry yet.', 18, height / 2);
            return;
        }
        const top = items.slice(0, 6);
        const maxVal = Math.max(1, ...top.map((d) => Number(d[valKey] || 0)));
        const rowH = Math.floor((height - 28) / top.length);
        const labelW = Math.min(165, Math.floor(width * 0.36));
        const barMaxW = Math.max(60, width - labelW - 95);

        ctx.font = '11px Inter, sans-serif';
        top.forEach((d, idx) => {
            const y = 16 + idx * rowH;
            const v = Number(d[valKey] || 0);
            const bw = Math.max(3, Math.round((v / maxVal) * barMaxW));
            ctx.fillStyle = '#cbd5e1';
            ctx.fillText(String(d[labelKey]).slice(0, 22), 12, y + 14);
            ctx.fillStyle = 'rgba(148,163,184,0.12)';
            ctx.fillRect(labelW, y + 4, barMaxW, 13);
            ctx.fillStyle = colorHex || '#10b981';
            ctx.fillRect(labelW, y + 4, bw, 13);
            ctx.fillStyle = '#f8fafc';
            ctx.font = '11px IBM Plex Mono, monospace';
            ctx.fillText(fmtInr(v), labelW + barMaxW + 8, y + 14);
            ctx.font = '11px Inter, sans-serif';
        });
    }

    function drawDualLineChart(canvasId, series, keyA, keyB, labelA, labelB, colorA, colorB) {
        const c = prepareCanvas(canvasId);
        if (!c) return;
        const { ctx, width, height } = c;
        if (!series || series.length < 2) {
            ctx.fillStyle = '#64748b';
            ctx.font = '12px IBM Plex Mono, monospace';
            ctx.fillText('Run simulation to inspect curve.', 18, height / 2);
            return;
        }
        const padL = 62, padR = 16, padT = 30, padB = 26;
        const plotW = Math.max(100, width - padL - padR);
        const plotH = Math.max(80, height - padT - padB);
        const allVals = [];
        series.forEach((p) => {
            allVals.push(Number(p[keyA] || 0));
            if (keyB) allVals.push(Number(p[keyB] || 0));
        });
        const minV = Math.min(...allVals);
        const maxV = Math.max(minV + 1, ...allVals);

        // Horizontal grid lines
        ctx.strokeStyle = 'rgba(148, 163, 184, 0.14)';
        ctx.lineWidth = 1;
        for (let g = 0; g <= 3; g++) {
            const gy = padT + (plotH * g) / 3;
            ctx.beginPath();
            ctx.moveTo(padL, gy);
            ctx.lineTo(width - padR, gy);
            ctx.stroke();
            const tickVal = maxV - ((maxV - minV) * g) / 3;
            ctx.fillStyle = '#64748b';
            ctx.font = '10px IBM Plex Mono, monospace';
            ctx.fillText(Math.round(tickVal).toLocaleString('en-IN'), 6, gy + 3);
        }

        function traceLine(fieldKey, strokeHex) {
            ctx.strokeStyle = strokeHex;
            ctx.lineWidth = 2;
            ctx.beginPath();
            series.forEach((pt, idx) => {
                const x = padL + (idx / (series.length - 1)) * plotW;
                const val = Number(pt[fieldKey] || 0);
                const y = padT + plotH - ((val - minV) / (maxV - minV)) * plotH;
                if (idx === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.stroke();
        }

        if (keyB) traceLine(keyB, colorB || '#94a3b8');
        traceLine(keyA, colorA || '#10b981');

        // Legend
        ctx.font = '11px IBM Plex Mono, monospace';
        ctx.fillStyle = colorA || '#10b981';
        ctx.fillText(labelA, padL, 16);
        if (keyB && labelB) {
            ctx.fillStyle = colorB || '#94a3b8';
            ctx.fillText(labelB, padL + 165, 16);
        }
    }

    async function runLedgerAnalysis() {
        const rawText = document.getElementById('smsLedgerInput').value;
        const budget = Number(document.getElementById('monthlyBudgetInput').value || 0);
        const data = await postJson('/api/ledger/analyze', {
            raw_text: rawText,
            monthly_budget_target: budget,
        });
        STATE.telemetry.ledger = data;

        const kpiCash = document.getElementById('kpiNetCashflow');
        const kpiMeta = document.getElementById('kpiCashflowMeta');
        kpiCash.textContent = fmtInr(data.net_cashflow);
        kpiMeta.textContent = `In ${fmtInr(data.total_income)} | Out ${fmtInr(data.total_spent)} (${data.savings_rate_pct}% saved)`;

        document.getElementById('ledgerSummaryBanner').textContent =
            `Parsed ${data.transaction_count} transactions. Spend: ${fmtInr(data.total_spent)} vs Budget: ${fmtInr(data.budget_target)}.`;
        document.getElementById('ledgerTxnCount').textContent = `${data.transaction_count} Entries`;

        drawBarChart('ledgerChart', data.categories, 'category', 'amount', '#10b981');

        const anomList = document.getElementById('ledgerAnomaliesList');
        anomList.replaceChildren();
        const anoms = data.anomalies || [];
        if (!anoms.length) {
            const li = document.createElement('li');
            li.className = 'sev-SAFE';
            li.textContent = 'No outlier spikes or flagged subscriptions detected in current feed.';
            anomList.appendChild(li);
        } else {
            anoms.forEach((a) => {
                const li = document.createElement('li');
                li.textContent = `[${a.citation}] ${a.reason}`;
                anomList.appendChild(li);
            });
        }

        const tbody = document.getElementById('ledgerTableBody');
        tbody.replaceChildren();
        (data.transactions || []).forEach((tx) => {
            const tr = document.createElement('tr');
            [tx.id, tx.date, tx.type.toUpperCase(), tx.category, tx.merchant].forEach((val) => {
                const td = document.createElement('td');
                td.textContent = String(val);
                tr.appendChild(td);
            });
            const amtTd = document.createElement('td');
            amtTd.className = 'num';
            amtTd.textContent = (tx.type === 'credit' ? '+' : '-') + fmtInr(tx.amount);
            tr.appendChild(amtTd);
            tbody.appendChild(tr);
        });
    }

    async function exportLedgerCsv() {
        const res = await fetch('/api/ledger/export.csv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                raw_text: document.getElementById('smsLedgerInput').value,
                monthly_budget_target: Number(document.getElementById('monthlyBudgetInput').value || 0),
            }),
        });
        const csvText = await res.text();
        const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'arthaledger_transactions.csv';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    }

    async function runFraudAudit() {
        const payloadText = document.getElementById('fraudPayloadInput').value;
        const contextText = document.getElementById('fraudContextInput').value;
        const data = await postJson('/api/fraud/audit', {
            payload_text: payloadText,
            claimed_context: contextText,
        });
        if (!data.success) return;
        STATE.telemetry.fraud = data;

        const score = Number(data.risk_score || 0);
        document.getElementById('kpiFraudScore').textContent = `${score} / 100`;
        document.getElementById('kpiFraudMeta').textContent = data.verdict;
        document.getElementById('fraudRiskNumber').textContent = `${score} / 100`;

        const bar = document.getElementById('fraudRiskBar');
        bar.style.width = `${score}%`;
        bar.style.backgroundColor = score >= 55 ? '#ef4444' : (score >= 25 ? '#e8a317' : '#10b981');

        const badge = document.getElementById('fraudVerdictBadge');
        badge.textContent = data.verdict;
        badge.className = 'verdict-badge ' + (score >= 55 ? 'high-risk' : (score >= 25 ? 'caution' : 'low-risk'));

        document.getElementById('fraudActionBox').textContent = data.recommended_action;

        const list = document.getElementById('fraudFlagsList');
        list.replaceChildren();
        const flags = data.flags || [];
        if (!flags.length) {
            const li = document.createElement('li');
            li.className = 'sev-SAFE';
            li.textContent = 'Zero heuristic phishing URLs or collect-PIN triggers found.';
            list.appendChild(li);
        } else {
            flags.forEach((f) => {
                const li = document.createElement('li');
                li.className = f.severity === 'CRITICAL' ? 'sev-CRITICAL' : '';
                li.textContent = `[${f.citation}] [${f.severity} +${f.weight}] ${f.detail}`;
                list.appendChild(li);
            });
        }
    }

    async function runTaxAndWealth() {
        const taxPayload = {
            gross_income: Number(document.getElementById('taxGrossInput').value || 0),
            is_salaried: document.getElementById('taxSalariedInput').value === 'true',
            deduction_80c: Number(document.getElementById('tax80cInput').value || 0),
            deduction_80d: Number(document.getElementById('tax80dInput').value || 0),
            hra_exemption: Number(document.getElementById('taxHraInput').value || 0),
            nps_80ccd1b: Number(document.getElementById('taxNpsInput').value || 0),
        };
        const sipPayload = {
            monthly_sip: Number(document.getElementById('sipMonthlyInput').value || 0),
            years: Number(document.getElementById('sipYearsInput').value || 10),
            annual_return_pct: Number(document.getElementById('sipReturnInput').value || 12),
            annual_step_up_pct: 10,
            inflation_pct: 6,
        };
        const emiPayload = {
            principal: Number(document.getElementById('emiPrincipalInput').value || 100000),
            annual_interest_pct: Number(document.getElementById('emiRateInput').value || 9),
            tenure_months: 120,
            extra_monthly_prepay: Number(document.getElementById('emiExtraInput').value || 0),
        };

        const [taxData, sipData, emiData] = await Promise.all([
            postJson('/api/tax/compare', taxPayload),
            postJson('/api/wealth/sip', sipPayload),
            postJson('/api/wealth/emi', emiPayload),
        ]);

        STATE.telemetry.tax = taxData;
        STATE.telemetry.sip = sipData;
        STATE.telemetry.emi = emiData;

        const bestTax = Math.min(taxData.new_regime.total_tax, taxData.old_regime.total_tax);
        document.getElementById('kpiTaxLiability').textContent = fmtInr(bestTax);
        document.getElementById('kpiTaxMeta').textContent =
            `${taxData.recommended_regime === 'NEW_REGIME' ? 'New Regime' : 'Old Regime'} saves ${fmtInr(taxData.net_tax_savings)}`;
        document.getElementById('taxWinnerBadge').textContent =
            taxData.recommended_regime === 'NEW_REGIME' ? 'USE NEW REGIME' : 'USE OLD REGIME';

        const cardsWrap = document.getElementById('taxComparisonCards');
        cardsWrap.replaceChildren();
        [
            { l: 'NEW REGIME TAX', v: fmtInr(taxData.new_regime.total_tax) },
            { l: 'OLD REGIME TAX', v: fmtInr(taxData.old_regime.total_tax) },
            { l: 'NOMINAL SIP CORPUS', v: fmtInr(sipData.projected_nominal_corpus) },
            { l: 'INFLATION-ADJUSTED', v: fmtInr(sipData.projected_real_corpus) },
        ].forEach((c) => {
            const div = document.createElement('div');
            div.className = 'mini-stat';
            const lbl = document.createElement('div');
            lbl.className = 'mini-stat-label';
            lbl.textContent = c.l;
            const val = document.createElement('div');
            val.className = 'mini-stat-val';
            val.textContent = c.v;
            div.appendChild(lbl);
            div.appendChild(val);
            cardsWrap.appendChild(div);
        });

        drawDualLineChart(
            'wealthChart',
            sipData.series,
            'nominal_value',
            'real_value_today_inr',
            'Nominal Value',
            'Real Purchasing Power',
            '#10b981',
            '#e8a317'
        );

        document.getElementById('emiSavingsSummary').textContent =
            `EMI Amortization: Base EMI ${fmtInr(emiData.monthly_emi)}/mo. Adding ${fmtInr(emiPayload.extra_monthly_prepay)}/mo saves ${emiData.months_saved} months and ${fmtInr(emiData.interest_saved)} interest.`;
    }

    async function runBacktest() {
        const payload = {
            symbol: document.getElementById('btSymbolSelect').value,
            strategy: document.getElementById('btStrategySelect').value,
            initial_capital: Number(document.getElementById('btCapitalInput').value || 100000),
            fast_window: Number(document.getElementById('btFastInput').value || 3),
            slow_window: Number(document.getElementById('btSlowInput').value || 7),
        };
        const data = await postJson('/api/market/backtest', payload);
        STATE.telemetry.backtest = data;

        document.getElementById('kpiBacktestReturn').textContent = `${data.total_return_pct}%`;
        document.getElementById('kpiBacktestMeta').textContent = `${data.symbol} | Max DD ${data.max_drawdown_pct}%`;

        const row = document.getElementById('backtestMetricsRow');
        row.replaceChildren();
        [
            { l: 'FINAL PAPER EQUITY', v: fmtInr(data.final_equity) },
            { l: 'STRATEGY RETURN', v: `${data.total_return_pct}%` },
            { l: 'BENCHMARK BUY & HOLD', v: `${data.benchmark_return_pct}%` },
            { l: 'MAX DRAWDOWN', v: `${data.max_drawdown_pct}%` },
            { l: 'WIN RATE / TRADES', v: `${data.win_rate_pct}% (${data.trade_count})` },
        ].forEach((m) => {
            const d = document.createElement('div');
            d.className = 'mini-stat';
            const l = document.createElement('div');
            l.className = 'mini-stat-label';
            l.textContent = m.l;
            const v = document.createElement('div');
            v.className = 'mini-stat-val';
            v.textContent = m.v;
            d.appendChild(l);
            d.appendChild(v);
            row.appendChild(d);
        });

        drawDualLineChart(
            'backtestChart',
            data.equity_curve,
            'strategy_equity',
            'buy_hold_equity',
            'Paper Strategy',
            'Benchmark Hold',
            '#10b981',
            '#38bdf8'
        );

        const tb = document.getElementById('backtestTradesBody');
        tb.replaceChildren();
        (data.trades || []).forEach((t) => {
            const tr = document.createElement('tr');
            const c1 = document.createElement('td');
            c1.textContent = `W${t.week}`;
            const c2 = document.createElement('td');
            c2.textContent = t.side;
            const c3 = document.createElement('td');
            c3.className = 'num';
            c3.textContent = Number(t.price).toLocaleString('en-IN');
            const c4 = document.createElement('td');
            c4.className = 'num';
            c4.textContent = t.pnl_pct !== undefined ? `${t.pnl_pct}%` : `${t.units} u`;
            tr.append(c1, c2, c3, c4);
            tb.appendChild(tr);
        });
    }

    async function runSmeAnalysis() {
        let items = [];
        try {
            items = JSON.parse(document.getElementById('smeItemsInput').value || '[]');
        } catch (_) {
            return;
        }
        const payload = {
            supply_type: document.getElementById('smeSupplySelect').value,
            input_tax_credit: Number(document.getElementById('smeItcInput').value || 0),
            opening_cash: Number(document.getElementById('smeOpeningCash').value || 0),
            monthly_fixed_costs: Number(document.getElementById('smeFixedCost').value || 1),
            expected_monthly_collections: Number(document.getElementById('smeCollections').value || 0),
            pending_receivables: Number(document.getElementById('smeReceivables').value || 0),
            items: items,
        };
        const data = await postJson('/api/sme/gst', payload);
        STATE.telemetry.sme = data;

        document.getElementById('smeRunwayBadge').textContent = `${data.stress_runway_days} Days Stress Runway`;
        const cards = document.getElementById('smeSummaryCards');
        cards.replaceChildren();
        [
            { l: 'INVOICE GRAND TOTAL', v: fmtInr(data.grand_invoice_total) },
            { l: 'GROSS GST OUTPUT', v: fmtInr(data.gross_gst) },
            { l: 'ITC OFFSET USED', v: fmtInr(data.itc_utilized) },
            { l: 'NET GST PAYABLE', v: fmtInr(data.net_gst_payable) },
        ].forEach((c) => {
            const d = document.createElement('div');
            d.className = 'mini-stat';
            const l = document.createElement('div');
            l.className = 'mini-stat-label';
            l.textContent = c.l;
            const v = document.createElement('div');
            v.className = 'mini-stat-val';
            v.textContent = c.v;
            d.append(l, v);
            cards.appendChild(d);
        });

        drawDualLineChart(
            'smeChart',
            data.projection_90d,
            'base_cash',
            'delayed_receivables_cash',
            'Base 90D Cash',
            'Delayed-Receivable Stress',
            '#10b981',
            '#ef4444'
        );

        const tb = document.getElementById('smeLinesBody');
        tb.replaceChildren();
        (data.lines || []).forEach((ln) => {
            const tr = document.createElement('tr');
            const c1 = document.createElement('td');
            c1.textContent = ln.line_id;
            const c2 = document.createElement('td');
            c2.textContent = ln.name;
            const c3 = document.createElement('td');
            c3.className = 'num';
            c3.textContent = fmtInr(ln.taxable_value);
            const c4 = document.createElement('td');
            c4.className = 'num';
            c4.textContent = `${ln.gst_rate_pct}%`;
            const c5 = document.createElement('td');
            c5.className = 'num';
            c5.textContent = fmtInr(ln.line_total);
            tr.append(c1, c2, c3, c4, c5);
            tb.appendChild(tr);
        });
    }

    async function askCopilot(questionText) {
        const q = (questionText || '').trim();
        if (!q) return;
        const out = document.getElementById('copilotOutput');
        out.textContent = 'Running grounded telemetry synthesis...';
        const data = await postJson(
            '/api/copilot/ask',
            {
                question: q,
                context: STATE.telemetry,
                provider: STATE.aiSettings.provider,
                model: STATE.aiSettings.model,
                image_data: STATE.attachedImageData,
                image_mime: STATE.attachedImageMime,
            },
            STATE.aiSettings.apiKey ? { 'X-User-AI-Key': STATE.aiSettings.apiKey } : {}
        );
        document.getElementById('copilotProviderStatus').textContent =
            `Engine: ${data.provider_used || 'deterministic'} (${data.model_used || 'local'})`;
        out.textContent = data.reply || data.error || 'No response received.';
    }

    async function loadPersona(personaId) {
        const res = await fetch('/api/personas?id=' + encodeURIComponent(personaId));
        const data = await res.json();
        if (!data.success || !data.persona) return;
        const p = data.persona;
        STATE.personaId = p.id;

        document.getElementById('monthlyBudgetInput').value = p.monthly_budget_target;
        document.getElementById('smsLedgerInput').value = p.sms_ledger;
        document.getElementById('fraudPayloadInput').value = p.fraud_sample;

        document.getElementById('taxGrossInput').value = p.tax_inputs.gross_income;
        document.getElementById('taxSalariedInput').value = String(p.tax_inputs.is_salaried);
        document.getElementById('tax80cInput').value = p.tax_inputs.deduction_80c;
        document.getElementById('tax80dInput').value = p.tax_inputs.deduction_80d;
        document.getElementById('taxHraInput').value = p.tax_inputs.hra_exemption;
        document.getElementById('taxNpsInput').value = p.tax_inputs.nps_80ccd1b;

        document.getElementById('sipMonthlyInput').value = p.sip_inputs.monthly_sip;
        document.getElementById('sipYearsInput').value = p.sip_inputs.years;
        document.getElementById('sipReturnInput').value = p.sip_inputs.annual_return_pct;

        document.getElementById('emiPrincipalInput').value = p.emi_inputs.principal;
        document.getElementById('emiRateInput').value = p.emi_inputs.annual_interest_pct;
        document.getElementById('emiExtraInput').value = p.emi_inputs.extra_monthly_prepay;

        const smeDefaults = p.sme_inputs || {
            supply_type: 'intra_state',
            input_tax_credit: 6800,
            opening_cash: 145000,
            monthly_fixed_costs: 62000,
            expected_monthly_collections: 108000,
            pending_receivables: 72000,
            items: [
                { name: 'Hardware Prototype Unit', qty: 2, unit_price: 15000, gst_rate: 18 },
                { name: 'Cloud Setup & Support', qty: 1, unit_price: 8500, gst_rate: 18 },
            ],
        };
        document.getElementById('smeSupplySelect').value = smeDefaults.supply_type;
        document.getElementById('smeItcInput').value = smeDefaults.input_tax_credit;
        document.getElementById('smeOpeningCash').value = smeDefaults.opening_cash;
        document.getElementById('smeFixedCost').value = smeDefaults.monthly_fixed_costs;
        document.getElementById('smeCollections').value = smeDefaults.expected_monthly_collections;
        document.getElementById('smeReceivables').value = smeDefaults.pending_receivables;
        document.getElementById('smeItemsInput').value = JSON.stringify(smeDefaults.items, null, 2);

        await Promise.all([
            runLedgerAnalysis(),
            runFraudAudit(),
            runTaxAndWealth(),
            runBacktest(),
            runSmeAnalysis(),
        ]);
    }

    function bindEvents() {
        document.querySelectorAll('.nav-btn').forEach((btn) => {
            btn.addEventListener('click', () => setTab(btn.dataset.tab));
        });
        document.getElementById('btnLoadPersona').addEventListener('click', () => {
            loadPersona(document.getElementById('personaSelect').value);
        });
        document.getElementById('btnAnalyzeLedger').addEventListener('click', runLedgerAnalysis);
        document.getElementById('btnExportCsv').addEventListener('click', exportLedgerCsv);
        document.getElementById('btnRunFraudAudit').addEventListener('click', runFraudAudit);
        document.getElementById('btnComputeTaxWealth').addEventListener('click', runTaxAndWealth);
        document.getElementById('btnRunBacktest').addEventListener('click', runBacktest);
        document.getElementById('btnComputeSme').addEventListener('click', runSmeAnalysis);

        document.querySelectorAll('[data-fraud-preset]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const mode = btn.dataset.fraudPreset;
                const input = document.getElementById('fraudPayloadInput');
                if (mode === 'kyc') {
                    input.value = 'URGENT: Your demo bank KYC is suspended within 24 hours. Update immediately via http://bit.ly/demo-kyc-check and enter UPI PIN to avoid freeze.';
                } else if (mode === 'collect') {
                    input.value = 'upi://pay?pa=cashback-helpdesk@okexample&pn=Lottery%20Refund&am=19999&mode=02&tn=Enter%20UPI%20PIN%20to%20claim%20refund';
                } else {
                    input.value = 'upi://pay?pa=metro.transit@okaxis&pn=City%20Metro%20Rail&am=120&tn=Monthly%20Smartcard%20Topup';
                }
                runFraudAudit();
            });
        });

        document.querySelectorAll('[data-copilot-q]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const q = btn.dataset.copilotQ;
                document.getElementById('copilotQuestionInput').value = q;
                askCopilot(q);
            });
        });

        document.getElementById('copilotForm').addEventListener('submit', (ev) => {
            ev.preventDefault();
            askCopilot(document.getElementById('copilotQuestionInput').value);
        });

        document.getElementById('copilotImageInput').addEventListener('change', (ev) => {
            const file = ev.target.files && ev.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = () => {
                STATE.attachedImageData = String(reader.result || '');
                STATE.attachedImageMime = file.type || 'image/png';
                document.getElementById('copilotImageStatus').textContent = `Attached: ${file.name}`;
                document.getElementById('btnClearImage').classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        });

        document.getElementById('btnClearImage').addEventListener('click', () => {
            STATE.attachedImageData = '';
            document.getElementById('copilotImageInput').value = '';
            document.getElementById('copilotImageStatus').textContent = 'No image attached';
            document.getElementById('btnClearImage').classList.add('hidden');
        });

        const modal = document.getElementById('settingsModal');
        document.getElementById('btnOpenSettings').addEventListener('click', () => {
            document.getElementById('aiProviderSelect').value = STATE.aiSettings.provider;
            document.getElementById('aiModelSelect').value = STATE.aiSettings.model;
            document.getElementById('aiApiKeyInput').value = STATE.aiSettings.apiKey;
            modal.classList.remove('hidden');
        });
        document.getElementById('btnCloseSettings').addEventListener('click', () => modal.classList.add('hidden'));
        modal.addEventListener('click', (ev) => {
            if (ev.target === modal) modal.classList.add('hidden');
        });
        document.addEventListener('keydown', (ev) => {
            if (ev.key === 'Escape' && !modal.classList.contains('hidden')) {
                modal.classList.add('hidden');
            }
        });
        window.addEventListener('resize', () => {
            const activeBtn = document.querySelector('.nav-btn.active');
            if (activeBtn) redrawTabCharts(activeBtn.dataset.tab);
        });
        document.getElementById('btnClearSessionKey').addEventListener('click', () => {
            STATE.aiSettings.apiKey = '';
            document.getElementById('aiApiKeyInput').value = '';
            try { sessionStorage.removeItem('artha_api_key'); } catch (_) {}
        });
        document.getElementById('btnSaveSettings').addEventListener('click', () => {
            STATE.aiSettings.provider = document.getElementById('aiProviderSelect').value;
            STATE.aiSettings.model = document.getElementById('aiModelSelect').value;
            STATE.aiSettings.apiKey = document.getElementById('aiApiKeyInput').value.trim();
            try {
                sessionStorage.setItem('artha_provider', STATE.aiSettings.provider);
                sessionStorage.setItem('artha_model', STATE.aiSettings.model);
                sessionStorage.setItem('artha_api_key', STATE.aiSettings.apiKey);
            } catch (_) {}
            modal.classList.add('hidden');
            document.getElementById('copilotProviderStatus').textContent =
                `Engine: ${STATE.aiSettings.provider} (${STATE.aiSettings.model})`;
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        bindEvents();
        loadPersona('student_budget');
    });
})();
