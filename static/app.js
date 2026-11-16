(function () {
    'use strict';

    const STATE = {
        personaId: 'student_budget',
        smeItems: [
            { name: 'Hardware Prototype Unit', qty: 2, unit_price: 15000, gst_rate: 18 },
            { name: 'Cloud Calibration Service', qty: 1, unit_price: 8500, gst_rate: 18 },
        ],
        telemetry: {
            ledger: null,
            fraud: null,
            tax: null,
            sip: null,
            emi: null,
            backtest: null,
            comparison: null,
            news_impact: null,
            harvest: null,
            qr_scan: null,
            sme: null,
        },
        aiSettings: { provider: 'auto', model: 'gemini-3.5-flash-lite', apiKey: '' },
        copilotHistory: [],
        attachedImageData: '',
        attachedImageMime: 'image/png',
        highlightedTxnId: '',
        serverHealth: { gemini_env_configured: false, bharatcode_env_configured: false },
    };

    try {
        STATE.aiSettings.provider = sessionStorage.getItem('artha_provider') || 'auto';
        const savedModel = sessionStorage.getItem('artha_model') || 'gemini-3.5-flash-lite';
        STATE.aiSettings.model = savedModel.startsWith('gemini-2.') ? 'gemini-3.5-flash-lite' : savedModel;
        STATE.aiSettings.apiKey = sessionStorage.getItem('artha_api_key') || '';
    } catch (_) {}

    const TAB_TITLES = {
        ledger: 'UPI Ledger & Burn Telemetry',
        fraud: 'UPI Collect, APK & Screenshot Forensics',
        tax: 'Budget 2025 Tax & SIP Wealth Engineering',
        market: 'Live AMFI Mutual Funds & Paper Backtester',
        sme: 'SME GST Invoice & 90-Day Liquidity Stress',
    };

    let toastTimer = null;
    function showToast(msg, isError) {
        const el = document.getElementById('statusToast');
        if (!el) return;
        el.textContent = msg;
        el.classList.toggle('is-error', Boolean(isError));
        el.classList.remove('hidden');
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(() => el.classList.add('hidden'), 3600);
    }

    function fmtInr(val) {
        const n = Number(val || 0);
        const absStr = Math.round(Math.abs(n)).toLocaleString('en-IN');
        return (n < 0 ? '-Rs.' : 'Rs.') + absStr;
    }

    async function apiRequest(url, options) {
        try {
            const res = await fetch(url, options);
            const txt = await res.text();
            let parsed = null;
            try { parsed = JSON.parse(txt); } catch (_) {}
            if (!res.ok) {
                const errMsg = (parsed && parsed.error) ? parsed.error : `Server returned HTTP ${res.status}`;
                showToast(errMsg, true);
                return null;
            }
            const statusDot = document.getElementById('serverLiveStatus');
            if (statusDot) statusDot.textContent = 'Engine Live';
            return parsed !== null ? parsed : txt;
        } catch (_) {
            const statusDot = document.getElementById('serverLiveStatus');
            if (statusDot) statusDot.textContent = 'Connection Offline';
            showToast('Backend unreachable. Run python app.py to reconnect.', true);
            return null;
        }
    }

    async function postJson(url, body, extraHeaders) {
        return apiRequest(url, {
            method: 'POST',
            headers: Object.assign({ 'Content-Type': 'application/json' }, extraHeaders || {}),
            body: JSON.stringify(body || {}),
        });
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

    function cssVar(name, fallback) {
        const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return v || fallback;
    }

    function prepareCanvas(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;
        if (!canvas.dataset.logicalHeight) {
            canvas.dataset.logicalHeight = String(Number(canvas.getAttribute('height')) || 220);
        }
        const rect = canvas.getBoundingClientRect();
        const width = Math.max(260, Math.floor(rect.width || 520));
        const height = Number(canvas.dataset.logicalHeight) || 220;
        const dpr = Math.min(2, window.devicePixelRatio || 1);
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        canvas.style.height = `${height}px`;
        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
        ctx.fillStyle = cssVar('--bg-subpanel', '#f7f9f6');
        ctx.fillRect(0, 0, width, height);
        return { canvas, ctx, width, height };
    }

    function attachLineHover(canvas, tipEl, series, xForIdx, describePt) {
        if (!canvas || !tipEl || !series.length) return;
        canvas.onmousemove = (ev) => {
            const rect = canvas.getBoundingClientRect();
            const mx = ev.clientX - rect.left;
            let bestIdx = 0;
            let bestDist = Infinity;
            series.forEach((_, i) => {
                const d = Math.abs(xForIdx(i) - mx);
                if (d < bestDist) { bestDist = d; bestIdx = i; }
            });
            tipEl.textContent = describePt(series[bestIdx], bestIdx);
            tipEl.style.left = Math.min(rect.width - 185, Math.max(8, xForIdx(bestIdx) - 55)) + 'px';
            tipEl.style.top = '8px';
            tipEl.classList.remove('hidden');
        };
        canvas.onmouseleave = () => tipEl.classList.add('hidden');
    }

    function drawBarChart(canvasId, tipId, items) {
        const prep = prepareCanvas(canvasId);
        if (!prep) return;
        const { canvas, ctx, width, height } = prep;
        const tip = document.getElementById(tipId);
        if (!items || !items.length) {
            ctx.fillStyle = cssVar('--text-soft', '#6c827b');
            ctx.font = '12px IBM Plex Mono, monospace';
            ctx.fillText('No debit categories parsed yet.', 16, height / 2);
            return;
        }
        const top = items.slice(0, 6);
        const maxVal = Math.max(1, ...top.map((d) => Number(d.amount || 0)));
        const rowH = Math.floor((height - 22) / top.length);
        const labelW = Math.min(155, Math.max(116, Math.floor(width * 0.41)));
        const barMaxW = Math.max(46, width - labelW - 76);
        const maxLabelChars = labelW < 128 ? 15 : 21;
        const textClr = cssVar('--text', '#0f2a24');
        const barClr = cssVar('--emerald', '#0d8a5f');
        const trackClr = cssVar('--border', 'rgba(15,42,36,0.12)');

        ctx.font = '11px Inter, sans-serif';
        top.forEach((d, idx) => {
            const y = 14 + idx * rowH;
            const v = Number(d.amount || 0);
            const bw = Math.max(3, Math.round((v / maxVal) * barMaxW));
            const rawCat = String(d.category);
            const shortCat = rawCat.length > maxLabelChars ? rawCat.slice(0, maxLabelChars - 1) + '.' : rawCat;
            ctx.fillStyle = textClr;
            ctx.fillText(shortCat, 10, y + 14);
            ctx.fillStyle = trackClr;
            ctx.fillRect(labelW, y + 4, barMaxW, 13);
            ctx.fillStyle = barClr;
            ctx.fillRect(labelW, y + 4, bw, 13);
            ctx.font = '11px IBM Plex Mono, monospace';
            ctx.fillText(fmtInr(v), labelW + barMaxW + 8, y + 14);
            ctx.font = '11px Inter, sans-serif';
        });

        if (tip) {
            canvas.onmousemove = (ev) => {
                const rect = canvas.getBoundingClientRect();
                const idx = Math.floor((ev.clientY - rect.top - 14) / rowH);
                if (idx >= 0 && idx < top.length) {
                    const row = top[idx];
                    tip.textContent = `${row.category}: ${fmtInr(row.amount)} (${row.share_pct}%)`;
                    tip.style.left = '12px';
                    tip.style.top = Math.max(4, 14 + idx * rowH - 18) + 'px';
                    tip.classList.remove('hidden');
                } else {
                    tip.classList.add('hidden');
                }
            };
            canvas.onmouseleave = () => tip.classList.add('hidden');
        }
    }

    function drawDualLineChart(canvasId, tipId, series, keyA, keyB, labelA, labelB, colorA, colorB, formatTip) {
        const prep = prepareCanvas(canvasId);
        if (!prep) return;
        const { canvas, ctx, width, height } = prep;
        const tip = document.getElementById(tipId);
        if (!series || series.length < 2) {
            ctx.fillStyle = cssVar('--text-soft', '#6c827b');
            ctx.font = '12px IBM Plex Mono, monospace';
            ctx.fillText('Run calculation to view curve.', 16, height / 2);
            return;
        }
        const padL = 62, padR = 14, padT = 28, padB = 22;
        const plotW = Math.max(90, width - padL - padR);
        const plotH = Math.max(70, height - padT - padB);
        const allVals = [];
        series.forEach((p) => {
            allVals.push(Number(p[keyA] || 0));
            if (keyB) allVals.push(Number(p[keyB] || 0));
        });
        const minV = Math.min(...allVals);
        const maxV = Math.max(minV + 1, ...allVals);
        const xForIdx = (i) => padL + (i / (series.length - 1)) * plotW;

        ctx.strokeStyle = cssVar('--border', 'rgba(15,42,36,0.12)');
        ctx.lineWidth = 1;
        for (let g = 0; g <= 3; g++) {
            const gy = padT + (plotH * g) / 3;
            ctx.beginPath();
            ctx.moveTo(padL, gy);
            ctx.lineTo(width - padR, gy);
            ctx.stroke();
            const tickVal = maxV - ((maxV - minV) * g) / 3;
            ctx.fillStyle = cssVar('--text-soft', '#6c827b');
            ctx.font = '10px IBM Plex Mono, monospace';
            ctx.fillText(Math.round(tickVal).toLocaleString('en-IN'), 6, gy + 3);
        }

        function traceLine(fieldKey, strokeHex) {
            ctx.strokeStyle = strokeHex;
            ctx.lineWidth = 2.2;
            ctx.beginPath();
            series.forEach((pt, idx) => {
                const x = xForIdx(idx);
                const val = Number(pt[fieldKey] || 0);
                const y = padT + plotH - ((val - minV) / (maxV - minV)) * plotH;
                if (idx === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.stroke();
        }

        if (keyB) traceLine(keyB, colorB);
        traceLine(keyA, colorA);

        ctx.font = '11px IBM Plex Mono, monospace';
        ctx.fillStyle = colorA;
        ctx.fillText(labelA, padL, 16);
        if (keyB && labelB) {
            const labelAXEnd = padL + Math.ceil(ctx.measureText(labelA).width) + 22;
            const legendBX = Math.max(padL + 150, labelAXEnd);
            ctx.fillStyle = colorB;
            if (legendBX + ctx.measureText(labelB).width <= width - 8) {
                ctx.fillText(labelB, legendBX, 16);
            } else {
                ctx.fillText(labelB.slice(0, 14), legendBX, 16);
            }
        }
        if (tip && formatTip) attachLineHover(canvas, tip, series, xForIdx, formatTip);
    }

    function redrawTabCharts(tabName) {
        const green = cssVar('--emerald', '#0d8a5f');
        const amber = cssVar('--amber', '#c97a08');
        const blue = cssVar('--blue', '#0284c7');
        const red = cssVar('--crimson', '#c82333');
        if (tabName === 'ledger' && STATE.telemetry.ledger) {
            drawBarChart('ledgerChart', 'ledgerChartTip', STATE.telemetry.ledger.categories);
        } else if (tabName === 'tax' && STATE.telemetry.sip) {
            drawDualLineChart(
                'wealthChart', 'wealthChartTip', STATE.telemetry.sip.series,
                'nominal_value', 'real_value_today_inr', 'Nominal Value', 'Real Purchasing Power',
                green, amber,
                (p) => `Yr ${p.year}: Nom ${fmtInr(p.nominal_value)} | Real ${fmtInr(p.real_value_today_inr)}`
            );
        } else if (tabName === 'market') {
            if (STATE.telemetry.backtest) {
                drawDualLineChart(
                    'backtestChart', 'backtestChartTip', STATE.telemetry.backtest.equity_curve,
                    'strategy_equity', 'buy_hold_equity', 'Paper Strategy', 'Benchmark Hold',
                    green, blue,
                    (p) => `${p.date}: Strat ${fmtInr(p.strategy_equity)} | B&H ${fmtInr(p.buy_hold_equity)} | DD -${p.drawdown_pct}%`
                );
            }
            if (STATE.telemetry.comparison && STATE.telemetry.comparison.series) {
                drawDualLineChart(
                    'compareChart', 'compareChartTip', STATE.telemetry.comparison.series,
                    'fund_a_indexed', 'fund_b_indexed',
                    (STATE.telemetry.comparison.fund_a.label || 'Fund A').slice(0, 22),
                    (STATE.telemetry.comparison.fund_b.label || 'Fund B').slice(0, 22),
                    green, amber,
                    (p) => `${p.date}: Fund A ${p.fund_a_indexed} | Fund B ${p.fund_b_indexed} (Base 100)`
                );
            }
        } else if (tabName === 'sme' && STATE.telemetry.sme) {
            drawDualLineChart(
                'smeChart', 'smeChartTip', STATE.telemetry.sme.projection_90d,
                'base_cash', 'delayed_receivables_cash', 'Base 90D', 'Delayed Receivables',
                green, red,
                (p) => `${p.month}: Base ${fmtInr(p.base_cash)} | Stress ${fmtInr(p.delayed_receivables_cash)}`
            );
        }
    }

    async function refreshHealthScore() {
        const res = await postJson('/api/health_score', { context: STATE.telemetry });
        if (!res || !res.success) return;
        const score = Number(res.score || 0);
        document.getElementById('healthScoreNum').innerHTML = `${score}<span>/100</span>`;
        document.getElementById('railHealthGrade').textContent = res.grade || '--';
        const circle = document.getElementById('healthGaugeCircle');
        if (circle) {
            const circ = 163.36;
            circle.style.strokeDashoffset = String(circ * (1 - score / 100));
            circle.style.stroke = score >= 80 ? cssVar('--emerald', '#0d8a5f') : (score >= 60 ? cssVar('--amber', '#c97a08') : cssVar('--crimson', '#c82333'));
        }
    }

    function renderLedgerTable() {
        const data = STATE.telemetry.ledger;
        if (!data) return;
        const query = (document.getElementById('ledgerSearchInput').value || '').trim().toLowerCase();
        const typeF = document.getElementById('ledgerTypeFilter').value;
        const filtered = (data.transactions || []).filter((tx) => {
            if (typeF !== 'all' && tx.type !== typeF) return false;
            if (query && !(`${tx.merchant} ${tx.category} ${tx.id}`.toLowerCase().includes(query))) return false;
            return true;
        });

        const tbody = document.getElementById('ledgerTableBody');
        tbody.replaceChildren();
        filtered.forEach((tx) => {
            const tr = document.createElement('tr');
            if (STATE.highlightedTxnId && tx.id === STATE.highlightedTxnId) {
                tr.className = 'highlighted-row';
            }
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
        document.getElementById('ledgerTxnCount').textContent = `${filtered.length} / ${data.transaction_count} Entries`;
    }

    async function runLedgerAnalysis() {
        const rawText = document.getElementById('smsLedgerInput').value;
        const budget = Number(document.getElementById('monthlyBudgetInput').value || 0);
        const data = await postJson('/api/ledger/analyze', { raw_text: rawText, monthly_budget_target: budget });
        if (!data) return;
        STATE.telemetry.ledger = data;

        document.getElementById('kpiNetCashflow').textContent = fmtInr(data.net_cashflow);
        document.getElementById('kpiCashflowMeta').textContent = `In ${fmtInr(data.total_income)} | Out ${fmtInr(data.total_spent)} (${data.savings_rate_pct}% saved)`;
        document.getElementById('ledgerSummaryBanner').textContent =
            `Parsed ${data.transaction_count} transactions. Spend: ${fmtInr(data.total_spent)} vs Cap: ${fmtInr(data.budget_target)}.`;
        document.getElementById('ledgerSubAnnualBadge').textContent = `Subs: ${fmtInr(data.subscription_annual_runrate || 0)}/yr`;

        const utilPct = budget > 0 ? Math.min(100, Math.round((data.total_spent / budget) * 100)) : 0;
        document.getElementById('budgetUtilLabel').textContent = `${utilPct}% (${fmtInr(data.total_spent)} / ${fmtInr(budget)})`;
        const utilBar = document.getElementById('budgetUtilBar');
        utilBar.style.width = `${utilPct}%`;
        utilBar.style.backgroundColor = utilPct >= 95 ? cssVar('--crimson', '#c82333') : (utilPct >= 75 ? cssVar('--amber', '#c97a08') : cssVar('--emerald', '#0d8a5f'));

        drawBarChart('ledgerChart', 'ledgerChartTip', data.categories);
        const anomList = document.getElementById('ledgerAnomaliesList');
        anomList.replaceChildren();
        const anoms = data.anomalies || [];
        if (!anoms.length) {
            const li = document.createElement('li');
            li.className = 'sev-SAFE';
            li.textContent = 'No outlier spikes or stealth subscriptions flagged.';
            anomList.appendChild(li);
        } else {
            anoms.forEach((a) => {
                const li = document.createElement('li');
                li.className = a.severity === 'HIGH' ? 'sev-CRITICAL' : '';
                li.textContent = `[${a.citation}] ${a.reason}`;
                anomList.appendChild(li);
            });
        }
        renderLedgerTable();
        refreshHealthScore();
    }

    function renderFraudResult(data) {
        if (!data || !data.success) return;
        STATE.telemetry.fraud = data;

        const score = Number(data.risk_score || 0);
        document.getElementById('kpiFraudScore').textContent = `${score} / 100`;
        document.getElementById('kpiFraudMeta').textContent = data.verdict;
        document.getElementById('fraudRiskNumber').textContent = `${score} / 100`;

        const bar = document.getElementById('fraudRiskBar');
        bar.style.width = `${score}%`;
        bar.style.backgroundColor = score >= 55 ? cssVar('--crimson', '#c82333') : (score >= 25 ? cssVar('--amber', '#c97a08') : cssVar('--emerald', '#0d8a5f'));

        const badge = document.getElementById('fraudVerdictBadge');
        badge.textContent = data.verdict;
        badge.className = 'verdict-badge ' + (score >= 55 ? 'high-risk' : (score >= 25 ? 'caution' : 'low-risk'));
        document.getElementById('fraudActionBox').textContent = data.recommended_action;

        const anat = document.getElementById('fraudAnatomyGrid');
        anat.replaceChildren();
        (data.anatomy || []).forEach((cell) => {
            const div = document.createElement('div');
            div.className = 'anatomy-cell';
            const k = document.createElement('div'); k.className = 'anatomy-k'; k.textContent = cell.field;
            const v = document.createElement('div'); v.className = 'anatomy-v'; v.textContent = cell.value;
            div.append(k, v);
            anat.appendChild(div);
        });

        const list = document.getElementById('fraudFlagsList');
        list.replaceChildren();
        const flags = data.flags || [];
        if (!flags.length) {
            const li = document.createElement('li');
            li.className = 'sev-SAFE';
            li.textContent = 'Zero heuristic phishing URLs, APK lures, or collect-PIN triggers found.';
            list.appendChild(li);
        } else {
            flags.forEach((f) => {
                const li = document.createElement('li');
                li.className = f.severity === 'CRITICAL' ? 'sev-CRITICAL' : '';
                li.textContent = `[${f.citation}] [${f.severity} +${f.weight}] ${f.detail}`;
                list.appendChild(li);
            });
        }
        refreshHealthScore();
    }

    async function runFraudAudit() {
        const payloadText = document.getElementById('fraudPayloadInput').value;
        const contextText = document.getElementById('fraudContextInput').value;
        const data = await postJson('/api/fraud/audit', { payload_text: payloadText, claimed_context: contextText });
        if (data && data.success) renderFraudResult(data);
    }

    async function tryDecodeQrClientSide(dataUrl) {
        if (!('BarcodeDetector' in window)) return '';
        try {
            const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
            const img = new Image();
            img.src = dataUrl;
            await new Promise((res, rej) => { img.onload = res; img.onerror = rej; });
            const codes = await detector.detect(img);
            return (codes && codes[0] && codes[0].rawValue) ? String(codes[0].rawValue).trim() : '';
        } catch (_) {
            return '';
        }
    }

    async function scanFraudImagePayload(dataUrl, mime, labelName) {
        STATE.attachedImageData = dataUrl;
        STATE.attachedImageMime = mime || 'image/png';
        document.getElementById('fraudImageLabel').textContent = `Scanning: ${labelName}...`;
        document.getElementById('copilotImageStatus').textContent = labelName;
        document.getElementById('btnClearImage').classList.remove('hidden');

        const browserQr = await tryDecodeQrClientSide(dataUrl);
        const res = await postJson(
            '/api/fraud/vision_scan',
            {
                image_data: dataUrl,
                image_mime: mime || 'image/png',
                browser_qr_text: browserQr,
                provider: STATE.aiSettings.provider,
                model: STATE.aiSettings.model,
            },
            STATE.aiSettings.apiKey ? { 'X-User-AI-Key': STATE.aiSettings.apiKey } : {}
        );
        if (!res || !res.success) {
            document.getElementById('fraudImageLabel').textContent = `Scan incomplete: ${labelName}`;
            return;
        }
        STATE.telemetry.qr_scan = { method: res.detection_method, decoded_payload: res.decoded_payload };
        document.getElementById('fraudPayloadInput').value = res.decoded_payload;
        document.getElementById('fraudImageLabel').textContent = `Decoded (${res.detection_method}): ${labelName}`;
        const banner = document.getElementById('fraudQrScanBanner');
        banner.textContent = `Decoded via ${res.detection_method}: ${res.decoded_payload}`;
        banner.classList.remove('hidden');
        if (res.audit) renderFraudResult(res.audit);
        showToast(`QR / Image decoded (${res.audit ? res.audit.verdict : 'OK'}).`, false);
    }

    async function scanDemoQrSample(kind) {
        try {
            const resp = await fetch(`/api/fraud/sample_qr?kind=${encodeURIComponent(kind)}`);
            if (!resp.ok) {
                showToast('Could not generate sample QR PNG.', true);
                return;
            }
            const blob = await resp.blob();
            const reader = new FileReader();
            reader.onload = () => scanFraudImagePayload(String(reader.result || ''), 'image/png', `sample_${kind}_upi_qr.png`);
            reader.readAsDataURL(blob);
        } catch (_) {
            showToast('Failed to fetch sample QR image.', true);
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
        const goalPayload = {
            target_today_inr: Number(document.getElementById('goalTargetInput').value || 1000000),
            annual_return_pct: sipPayload.annual_return_pct,
            years: sipPayload.years,
            inflation_pct: 6,
            gain_amount: Number(document.getElementById('capGainInput').value || 0),
            holding_months: Number(document.getElementById('capMonthsInput').value || 18),
        };

        const [taxData, sipData, emiData, goalData] = await Promise.all([
            postJson('/api/tax/compare', taxPayload),
            postJson('/api/wealth/sip', sipPayload),
            postJson('/api/wealth/emi', emiPayload),
            postJson('/api/wealth/goal', goalPayload),
        ]);
        if (!taxData || !sipData || !emiData) return;

        STATE.telemetry.tax = taxData;
        STATE.telemetry.sip = sipData;
        STATE.telemetry.emi = emiData;

        const bestTax = Math.min(taxData.new_regime.total_tax, taxData.old_regime.total_tax);
        document.getElementById('kpiTaxLiability').textContent = fmtInr(bestTax);
        document.getElementById('kpiTaxMeta').textContent =
            `${taxData.recommended_regime === 'NEW_REGIME' ? 'New Regime' : 'Old Regime'} saves ${fmtInr(taxData.net_tax_savings)}`;
        document.getElementById('taxWinnerBadge').textContent =
            taxData.recommended_regime === 'NEW_REGIME' ? 'NEW REGIME WINS' : 'OLD REGIME WINS';
        document.getElementById('taxBreakevenBanner').textContent = taxData.summary;

        const cards = document.getElementById('taxComparisonCards');
        cards.replaceChildren();
        [
            { l: 'NEW REGIME TAX', v: fmtInr(taxData.new_regime.total_tax) },
            { l: 'OLD REGIME TAX', v: fmtInr(taxData.old_regime.total_tax) },
            { l: 'MONTHLY TAKE-HOME', v: fmtInr(taxData.monthly_take_home) },
            { l: 'INFLATION-ADJ SIP', v: fmtInr(sipData.projected_real_corpus) },
        ].forEach((c) => {
            const d = document.createElement('div');
            d.className = 'mini-stat';
            const l = document.createElement('div'); l.className = 'mini-stat-label'; l.textContent = c.l;
            const v = document.createElement('div'); v.className = 'mini-stat-val'; v.textContent = c.v;
            d.append(l, v);
            cards.appendChild(d);
        });

        const slabBody = document.getElementById('taxSlabTableBody');
        slabBody.replaceChildren();
        (taxData.new_regime.slabs || []).forEach((s) => {
            const tr = document.createElement('tr');
            const c1 = document.createElement('td'); c1.textContent = s.slab;
            const c2 = document.createElement('td'); c2.className = 'num'; c2.textContent = `${s.rate_pct}%`;
            const c3 = document.createElement('td'); c3.className = 'num'; c3.textContent = fmtInr(s.taxable_in_slab);
            const c4 = document.createElement('td'); c4.className = 'num'; c4.textContent = fmtInr(s.tax);
            tr.append(c1, c2, c3, c4);
            slabBody.appendChild(tr);
        });

        if (goalData && goalData.success) {
            const g = goalData.goal;
            const cg = goalData.capital_gains_tax;
            document.getElementById('goalAndCgSummary').textContent =
                `Goal Planner: Today Rs.${Math.round(g.target_today_inr).toLocaleString('en-IN')} inflates to ${fmtInr(g.inflation_adjusted_target)} in ${g.years}Y -> Required SIP: ${fmtInr(g.required_monthly_sip)}/mo. Equity Tax (${cg.regime_label}): Est Tax ${fmtInr(cg.estimated_tax_with_cess)}, Post-Tax Profit ${fmtInr(cg.post_tax_gain)}.`;
            const hv = goalData.harvest;
            const hvBox = document.getElementById('harvestSummaryBox');
            if (hv && hvBox) {
                STATE.telemetry.harvest = hv;
                hvBox.textContent =
                    `Sec 112A Tax-Harvesting (${hv.years}Y Plan): Booking Rs.1,25,000 exempt LTCG annually saves ${fmtInr(hv.net_tax_saved)} tax (Tax drops from ${fmtInr(hv.tax_without_harvest)} to ${fmtInr(hv.tax_with_harvest)} across ${fmtInr(hv.total_exempt_step_up)} basis step-up).`;
                hvBox.classList.remove('hidden');
            }
        }

        redrawTabCharts('tax');
        document.getElementById('emiSavingsSummary').textContent =
            `EMI Schedule: Base EMI ${fmtInr(emiData.monthly_emi)}/mo. Adding ${fmtInr(emiPayload.extra_monthly_prepay)}/mo cuts tenure by ${emiData.months_saved} months and saves ${fmtInr(emiData.interest_saved)} interest.`;
        refreshHealthScore();
    }

    async function searchAmfiFunds() {
        const q = (document.getElementById('amfiSearchInput').value || '').trim();
        const res = await apiRequest('/api/market/mf_search?q=' + encodeURIComponent(q), { method: 'GET' });
        if (!res || !res.funds) return;
        const sel = document.getElementById('amfiSchemeSelect');
        sel.replaceChildren();
        res.funds.forEach((f) => {
            const opt = document.createElement('option');
            opt.value = f.schemeCode;
            opt.textContent = `${f.schemeName} (${f.schemeCode})`;
            sel.appendChild(opt);
        });
        const def = document.createElement('option');
        def.value = '';
        def.textContent = '-- Fallback: Built-in Historical Index Proxy --';
        sel.appendChild(def);
        if (res.funds.length) {
            sel.value = res.funds[0].schemeCode;
            showToast(`Loaded ${res.funds.length} AMFI funds (${res.source}).`, false);
            await runBacktest();
        }
    }

    async function runBacktest() {
        const payload = {
            symbol: document.getElementById('btSymbolSelect').value,
            strategy: document.getElementById('btStrategySelect').value,
            initial_capital: Number(document.getElementById('btCapitalInput').value || 100000),
            fast_window: Number(document.getElementById('btFastInput').value || 3),
            slow_window: Number(document.getElementById('btSlowInput').value || 7),
            amfi_scheme_code: document.getElementById('amfiSchemeSelect').value,
        };
        const data = await postJson('/api/market/backtest', payload);
        if (!data) return;
        STATE.telemetry.backtest = data;

        document.getElementById('kpiBacktestReturn').textContent = `${data.total_return_pct}% | S:${data.sharpe_ratio}`;
        const srcBadge = data.data_source === 'live_amfi_public_nav' ? 'LIVE AMFI NAV' : 'PROXY SERIES';
        document.getElementById('kpiBacktestMeta').textContent = `${data.symbol} | ${srcBadge}`;

        const row = document.getElementById('backtestMetricsRow');
        row.replaceChildren();
        [
            { l: 'PAPER EQUITY', v: fmtInr(data.final_equity) },
            { l: 'RETURN VS B&H', v: `${data.total_return_pct}% vs ${data.benchmark_return_pct}%` },
            { l: 'SHARPE / VOL', v: `${data.sharpe_ratio} / ${data.annualized_volatility_pct}%` },
            { l: 'MAX DRAWDOWN', v: `-${data.max_drawdown_pct}%` },
            { l: 'DATA SOURCE', v: srcBadge },
        ].forEach((m) => {
            const d = document.createElement('div');
            d.className = 'mini-stat';
            const l = document.createElement('div'); l.className = 'mini-stat-label'; l.textContent = m.l;
            const v = document.createElement('div'); v.className = 'mini-stat-val'; v.textContent = m.v;
            d.append(l, v);
            row.appendChild(d);
        });

        const drag = data.direct_vs_regular || {};
        document.getElementById('directVsRegularBox').textContent =
            `Direct vs Regular Plan Audit (${drag.years || 15}Y @ ${fmtInr(drag.monthly_sip)}/mo): Direct corpus ${fmtInr(drag.direct_corpus)} vs Regular ${fmtInr(drag.regular_corpus)} -> Commission leakage avoided: ${fmtInr(drag.commission_leakage)}.`;

        redrawTabCharts('market');
        const tb = document.getElementById('backtestTradesBody');
        tb.replaceChildren();
        (data.trades || []).forEach((t) => {
            const tr = document.createElement('tr');
            const c1 = document.createElement('td'); c1.textContent = `Bar ${t.week}`;
            const c2 = document.createElement('td'); c2.textContent = t.side;
            const c3 = document.createElement('td'); c3.className = 'num'; c3.textContent = Number(t.price).toLocaleString('en-IN');
            const c4 = document.createElement('td'); c4.className = 'num'; c4.textContent = t.pnl_pct !== undefined ? `${t.pnl_pct}%` : `${t.units} u`;
            tr.append(c1, c2, c3, c4);
            tb.appendChild(tr);
        });
        refreshHealthScore();
    }

    let compareReqSeq = 0;
    async function runFundComparison() {
        const reqId = ++compareReqSeq;
        const btn = document.getElementById('btnCompareFunds');
        const schemeA = document.getElementById('cmpFundASelect').value;
        const schemeB = document.getElementById('cmpFundBSelect').value;
        if (btn) { btn.disabled = true; btn.textContent = 'Comparing...'; }
        const data = await postJson('/api/market/compare', { scheme_a: schemeA, scheme_b: schemeB });
        if (btn) { btn.disabled = false; btn.textContent = 'Compare Live Funds'; }
        if (reqId !== compareReqSeq || !data || !data.success) return;
        STATE.telemetry.comparison = data;

        const row = document.getElementById('compareMetricsRow');
        row.replaceChildren();
        [
            { l: 'FUND A RETURN / SHARPE', v: `${data.fund_a.total_return_pct}% | S:${data.fund_a.sharpe_ratio}` },
            { l: 'FUND B RETURN / SHARPE', v: `${data.fund_b.total_return_pct}% | S:${data.fund_b.sharpe_ratio}` },
            { l: 'MAX DD (A vs B)', v: `-${data.fund_a.max_drawdown_pct}% vs -${data.fund_b.max_drawdown_pct}%` },
            { l: 'CORRELATION (r)', v: String(data.correlation) },
        ].forEach((m) => {
            const d = document.createElement('div');
            d.className = 'mini-stat';
            const l = document.createElement('div'); l.className = 'mini-stat-label'; l.textContent = m.l;
            const v = document.createElement('div'); v.className = 'mini-stat-val'; v.textContent = m.v;
            d.append(l, v);
            row.appendChild(d);
        });
        document.getElementById('compareOverlapBanner').textContent =
            `${data.overlap_note} Risk-Adjusted Sharpe Leader: ${data.winner_sharpe}.`;
        redrawTabCharts('market');
    }

    async function runNewsImpact() {
        const btn = document.getElementById('btnFetchNewsImpact');
        const sel = document.getElementById('amfiSchemeSelect');
        const schemeTitle = sel && sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex].text : 'RBI Nifty 50 Indian mutual funds';
        if (btn) { btn.disabled = true; btn.textContent = 'Scanning News...'; }
        const data = await postJson('/api/market/news_impact', { asset_focus: schemeTitle });
        if (btn) { btn.disabled = false; btn.textContent = 'Refresh Macro News'; }
        if (!data || !data.success) return;
        STATE.telemetry.news_impact = data;

        const srcLabel = data.news_source === 'live_google_news_india_rss' ? 'LIVE INDIA RSS' : 'MACRO DIGEST';
        const row = document.getElementById('newsMetricsRow');
        row.replaceChildren();
        [
            { l: 'SENTIMENT INDEX', v: `${data.sentiment_score >= 0 ? '+' : ''}${data.sentiment_score} / 100` },
            { l: 'MACRO REGIME', v: data.regime },
            { l: 'EQUITY SHOCK EST', v: `${data.projected_equity_impact_pct >= 0 ? '+' : ''}${data.projected_equity_impact_pct}%` },
            { l: 'GOLD HEDGE SHIFT', v: `${data.projected_gold_hedge_pct >= 0 ? '+' : ''}${data.projected_gold_hedge_pct}% (${srcLabel})` },
        ].forEach((m) => {
            const d = document.createElement('div');
            d.className = 'mini-stat';
            const l = document.createElement('div'); l.className = 'mini-stat-label'; l.textContent = m.l;
            const v = document.createElement('div'); v.className = 'mini-stat-val'; v.textContent = m.v;
            d.append(l, v);
            row.appendChild(d);
        });
        document.getElementById('newsImpactSummary').textContent = data.summary;

        const list = document.getElementById('newsHeadlinesList');
        list.replaceChildren();
        (data.headlines || []).forEach((h) => {
            const li = document.createElement('li');
            li.className = h.sentiment_tag === 'BEARISH' ? 'sev-CRITICAL' : (h.sentiment_tag === 'BULLISH' ? 'sev-SAFE' : '');
            li.textContent = `[${h.sentiment_tag} ${h.score_delta >= 0 ? '+' : ''}${h.score_delta}] ${h.title} (${h.published})`;
            list.appendChild(li);
        });
    }

    function renderSmeItemRows() {
        const container = document.getElementById('smeItemRowsContainer');
        container.replaceChildren();
        STATE.smeItems.forEach((item, idx) => {
            const row = document.createElement('div');
            row.className = 'sme-item-row';

            const nameIn = document.createElement('input');
            nameIn.type = 'text'; nameIn.value = item.name; nameIn.placeholder = 'Item description';
            nameIn.addEventListener('input', (e) => { STATE.smeItems[idx].name = e.target.value; });

            const qtyIn = document.createElement('input');
            qtyIn.type = 'number'; qtyIn.min = '1'; qtyIn.value = item.qty;
            qtyIn.addEventListener('input', (e) => { STATE.smeItems[idx].qty = Number(e.target.value || 1); });

            const priceIn = document.createElement('input');
            priceIn.type = 'number'; priceIn.min = '0'; priceIn.value = item.unit_price;
            priceIn.addEventListener('input', (e) => { STATE.smeItems[idx].unit_price = Number(e.target.value || 0); });

            const gstSel = document.createElement('select');
            [0, 5, 12, 18, 28].forEach((r) => {
                const o = document.createElement('option');
                o.value = String(r); o.textContent = `${r}% GST`;
                if (Number(item.gst_rate) === r) o.selected = true;
                gstSel.appendChild(o);
            });
            gstSel.addEventListener('change', (e) => { STATE.smeItems[idx].gst_rate = Number(e.target.value); });

            const delBtn = document.createElement('button');
            delBtn.type = 'button'; delBtn.className = 'btn btn-outline'; delBtn.textContent = 'Remove';
            delBtn.addEventListener('click', () => {
                if (STATE.smeItems.length > 1) {
                    STATE.smeItems.splice(idx, 1);
                    renderSmeItemRows();
                    runSmeAnalysis();
                }
            });

            row.append(nameIn, qtyIn, priceIn, gstSel, delBtn);
            container.appendChild(row);
        });
    }

    async function runSmeAnalysis() {
        const payload = {
            supply_type: document.getElementById('smeSupplySelect').value,
            input_tax_credit: Number(document.getElementById('smeItcInput').value || 0),
            opening_cash: Number(document.getElementById('smeOpeningCash').value || 0),
            monthly_fixed_costs: Number(document.getElementById('smeFixedCost').value || 1),
            expected_monthly_collections: Number(document.getElementById('smeCollections').value || 0),
            pending_receivables: Number(document.getElementById('smeReceivables').value || 0),
            items: STATE.smeItems,
        };
        const data = await postJson('/api/sme/gst', payload);
        if (!data) return;
        STATE.telemetry.sme = data;

        document.getElementById('smeRunwayBadge').textContent = `${data.stress_runway_days} Days Stress Runway`;
        const cards = document.getElementById('smeSummaryCards');
        cards.replaceChildren();
        [
            { l: 'INVOICE TOTAL', v: fmtInr(data.grand_invoice_total) },
            { l: 'GROSS GST', v: fmtInr(data.gross_gst) },
            { l: 'ITC OFFSET', v: fmtInr(data.itc_utilized) },
            { l: 'NET GST PAYABLE', v: fmtInr(data.net_gst_payable) },
        ].forEach((c) => {
            const d = document.createElement('div');
            d.className = 'mini-stat';
            const l = document.createElement('div'); l.className = 'mini-stat-label'; l.textContent = c.l;
            const v = document.createElement('div'); v.className = 'mini-stat-val'; v.textContent = c.v;
            d.append(l, v);
            cards.appendChild(d);
        });

        redrawTabCharts('sme');
        const tb = document.getElementById('smeLinesBody');
        tb.replaceChildren();
        (data.lines || []).forEach((ln) => {
            const tr = document.createElement('tr');
            const c1 = document.createElement('td'); c1.textContent = ln.line_id;
            const c2 = document.createElement('td'); c2.textContent = ln.name;
            const c3 = document.createElement('td'); c3.className = 'num'; c3.textContent = fmtInr(ln.taxable_value);
            const c4 = document.createElement('td'); c4.className = 'num'; c4.textContent = `${ln.gst_rate_pct}%`;
            const c5 = document.createElement('td'); c5.className = 'num'; c5.textContent = fmtInr(ln.line_total);
            tr.append(c1, c2, c3, c4, c5);
            tb.appendChild(tr);
        });
    }

    function jumpToCitation(code) {
        if (code.startsWith('TXN-')) {
            STATE.highlightedTxnId = code;
            setTab('ledger');
            renderLedgerTable();
            showToast(`Highlighted cited transaction ${code}`, false);
        } else if (code.startsWith('TAX-')) {
            setTab('tax');
        } else if (code.startsWith('FRAUD-')) {
            setTab('fraud');
        } else if (code.startsWith('BACKTEST') || code.startsWith('MF-')) {
            setTab('market');
        } else if (code.startsWith('GST') || code.startsWith('WC-')) {
            setTab('sme');
        }
    }

    async function applyCopilotAction(act) {
        if (act.highlight_txn) STATE.highlightedTxnId = act.highlight_txn;
        if (act.tab) setTab(act.tab);
        if (act.patch) {
            Object.entries(act.patch).forEach(([elId, val]) => {
                const el = document.getElementById(elId);
                if (el) el.value = String(val);
            });
            if (act.tab === 'tax') {
                document.getElementById('sipMonthlyRange').value = document.getElementById('sipMonthlyInput').value;
                document.getElementById('sipMonthlyLabel').textContent = `${fmtInr(document.getElementById('sipMonthlyInput').value)} / mo`;
                await runTaxAndWealth();
            } else if (act.tab === 'market') {
                await runBacktest();
            }
        }
        if (act.highlight_txn) renderLedgerTable();
        showToast(`Applied: ${act.label}`, false);
    }

    function appendCopilotBubble(role, text, metaLabel) {
        const out = document.getElementById('copilotOutput');
        const box = document.createElement('div');
        box.className = 'chat-msg ' + (role === 'user' ? 'msg-user' : 'msg-assistant');
        if (metaLabel) {
            const meta = document.createElement('div');
            meta.className = 'msg-meta';
            meta.textContent = metaLabel;
            box.appendChild(meta);
        }
        const bodySpan = document.createElement('div');
        bodySpan.textContent = text;
        box.appendChild(bodySpan);
        out.appendChild(box);
        out.scrollTop = out.scrollHeight;
        return box;
    }

    async function askCopilot(questionText) {
        const q = (questionText || '').trim();
        if (!q) return;
        const btn = document.getElementById('btnAskCopilot');
        const inputEl = document.getElementById('copilotQuestionInput');
        btn.disabled = true;
        inputEl.value = '';
        appendCopilotBubble('user', q);
        const pendingEl = appendCopilotBubble('assistant', 'Synthesizing telemetry and live citations...', 'COMPUTING');

        const data = await postJson(
            '/api/copilot/ask',
            {
                question: q,
                context: STATE.telemetry,
                history: STATE.copilotHistory.slice(-6),
                provider: STATE.aiSettings.provider,
                model: STATE.aiSettings.model,
                image_data: STATE.attachedImageData,
                image_mime: STATE.attachedImageMime,
            },
            STATE.aiSettings.apiKey ? { 'X-User-AI-Key': STATE.aiSettings.apiKey } : {}
        );
        btn.disabled = false;
        pendingEl.remove();

        if (!data) {
            appendCopilotBubble('assistant', 'Request failed. Check server status.', 'ERROR');
            return;
        }
        const modelTag = `${data.provider_used || 'deterministic'} (${data.model_used || 'local'})`;
        document.getElementById('copilotProviderStatus').textContent = `Engine: ${modelTag}`;
        appendCopilotBubble('assistant', data.reply || data.error || 'No response.', modelTag.toUpperCase());

        STATE.copilotHistory.push({ role: 'user', content: q });
        if (data.reply) STATE.copilotHistory.push({ role: 'assistant', content: data.reply });

        const citeBar = document.getElementById('copilotCitationsBar');
        citeBar.replaceChildren();
        const cites = data.citations || [];
        citeBar.classList.toggle('hidden', !cites.length);
        cites.forEach((c) => {
            const p = document.createElement('button');
            p.type = 'button'; p.className = 'cite-pill'; p.textContent = `[${c}]`;
            p.addEventListener('click', () => jumpToCitation(c));
            citeBar.appendChild(p);
        });

        const actBar = document.getElementById('copilotActionsBar');
        actBar.replaceChildren();
        const acts = data.actions || [];
        actBar.classList.toggle('hidden', !acts.length);
        acts.forEach((act) => {
            const ab = document.createElement('button');
            ab.type = 'button'; ab.className = 'action-apply-btn'; ab.textContent = act.label;
            ab.addEventListener('click', () => applyCopilotAction(act));
            actBar.appendChild(ab);
        });
    }

    async function loadPersona(personaId) {
        const btn = document.getElementById('btnLoadPersona');
        btn.disabled = true;
        const data = await apiRequest('/api/personas?id=' + encodeURIComponent(personaId), { method: 'GET' });
        btn.disabled = false;
        if (!data || !data.success || !data.persona) return;
        const p = data.persona;
        STATE.personaId = p.id;
        STATE.highlightedTxnId = '';

        document.getElementById('monthlyBudgetInput').value = p.monthly_budget_target;
        document.getElementById('smsLedgerInput').value = p.sms_ledger;
        document.getElementById('fraudPayloadInput').value = p.fraud_sample;

        document.getElementById('taxGrossInput').value = p.tax_inputs.gross_income;
        document.getElementById('taxGrossRange').value = Math.min(5000000, Math.max(200000, p.tax_inputs.gross_income));
        document.getElementById('taxGrossLabel').textContent = fmtInr(p.tax_inputs.gross_income);
        document.getElementById('taxSalariedInput').value = String(p.tax_inputs.is_salaried);
        document.getElementById('tax80cInput').value = p.tax_inputs.deduction_80c;
        document.getElementById('tax80dInput').value = p.tax_inputs.deduction_80d;
        document.getElementById('taxHraInput').value = p.tax_inputs.hra_exemption;
        document.getElementById('taxNpsInput').value = p.tax_inputs.nps_80ccd1b;

        document.getElementById('sipMonthlyInput').value = p.sip_inputs.monthly_sip;
        document.getElementById('sipMonthlyRange').value = Math.min(100000, Math.max(500, p.sip_inputs.monthly_sip));
        document.getElementById('sipMonthlyLabel').textContent = `${fmtInr(p.sip_inputs.monthly_sip)} / mo`;
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
                { name: 'Cloud Calibration Service', qty: 1, unit_price: 8500, gst_rate: 18 },
            ],
        };
        document.getElementById('smeSupplySelect').value = smeDefaults.supply_type;
        document.getElementById('smeItcInput').value = smeDefaults.input_tax_credit;
        document.getElementById('smeOpeningCash').value = smeDefaults.opening_cash;
        document.getElementById('smeFixedCost').value = smeDefaults.monthly_fixed_costs;
        document.getElementById('smeCollections').value = smeDefaults.expected_monthly_collections;
        document.getElementById('smeReceivables').value = smeDefaults.pending_receivables;
        STATE.smeItems = smeDefaults.items.map((x) => Object.assign({}, x));
        renderSmeItemRows();

        await Promise.all([runLedgerAnalysis(), runFraudAudit(), runTaxAndWealth(), runBacktest(), runFundComparison(), runNewsImpact(), runSmeAnalysis()]);
        showToast(`Loaded scenario: ${p.name}`, false);
    }

    async function checkServerHealth() {
        const h = await apiRequest('/api/health', { method: 'GET' });
        if (!h || !h.ai_providers) return;
        STATE.serverHealth = h.ai_providers;
        const note = document.getElementById('serverEnvStatusNote');
        const statusEl = document.getElementById('copilotProviderStatus');
        if (h.ai_providers.gemini_env_configured) {
            if (statusEl) statusEl.textContent = 'Engine: Gemini 3.5 Live Ready';
            if (note) note.textContent = 'Server GEMINI_API_KEY detected cleanly via local .env (zero secrets in GitHub). Requests use live Gemini 3.5 Flash Lite + deterministic citations.';
        } else if (h.ai_providers.bharatcode_env_configured) {
            if (statusEl) statusEl.textContent = 'Engine: BharatCode GLM 5.3 Live';
            if (note) note.textContent = 'Server BHARATCODE_API_KEY detected via local .env.';
        } else {
            if (statusEl) statusEl.textContent = 'Engine: Deterministic Cited Mode';
            if (note) note.textContent = 'All math computes locally. Enter an optional Gemini or BharatCode GLM 5.3 Flash key below (sessionStorage only) for live LLM & screenshot vision.';
        }
    }

    function initScrollMotion() {
        const bar = document.getElementById('scrollProgressBar');
        const grid = document.getElementById('welcomeGridLayer');
        const charEl = document.getElementById('welcomeCharacterLayer');
        let ticking = false;

        function onScrollFrame() {
            ticking = false;
            const sy = window.scrollY || 0;
            const docH = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
            if (bar) bar.style.width = `${Math.min(100, Math.round((sy / docH) * 100))}%`;
            if (grid) grid.style.transform = `translate3d(0, ${Math.round(sy * 0.14)}px, 0)`;
            if (charEl) charEl.style.transform = `translate3d(0, ${Math.round(-Math.min(14, sy * 0.06))}px, 0)`;
        }

        window.addEventListener('scroll', () => {
            if (!ticking) {
                ticking = true;
                requestAnimationFrame(onScrollFrame);
            }
        }, { passive: true });

        if ('IntersectionObserver' in window) {
            const els = document.querySelectorAll('.scroll-reveal');
            const obs = new IntersectionObserver((entries) => {
                entries.forEach((en) => {
                    if (en.isIntersecting) {
                        en.target.classList.remove('is-pre-reveal');
                        obs.unobserve(en.target);
                    }
                });
            }, { threshold: 0.05 });
            els.forEach((el) => {
                const r = el.getBoundingClientRect();
                if (r.top > window.innerHeight) el.classList.add('is-pre-reveal');
                obs.observe(el);
            });
        }
    }

    function bindEvents() {
        document.querySelectorAll('.nav-btn').forEach((btn) => {
            btn.addEventListener('click', () => setTab(btn.dataset.tab));
        });
        document.getElementById('btnLoadPersona').addEventListener('click', () => {
            loadPersona(document.getElementById('personaSelect').value);
        });
        document.getElementById('btnStartGuidedCheck').addEventListener('click', async () => {
            await loadPersona(document.getElementById('personaSelect').value);
            await askCopilot('Full Money Audit: summarize top savings, tax breakeven, and fraud checks.');
        });
        document.getElementById('btnToggleWelcome').addEventListener('click', () => {
            const band = document.getElementById('welcomeGuideBand');
            const collapsed = band.classList.toggle('collapsed');
            document.getElementById('btnToggleWelcome').textContent = collapsed ? 'Expand Welcome' : 'Collapse Intro';
        });
        document.getElementById('btnPrintDossier').addEventListener('click', () => window.print());
        document.getElementById('btnToggleTheme').addEventListener('click', () => {
            const html = document.documentElement;
            const next = html.getAttribute('data-theme') === 'dark' ? 'paper' : 'dark';
            html.setAttribute('data-theme', next);
            document.getElementById('btnToggleTheme').textContent = next === 'dark' ? 'Paper Mode' : 'Dark Mode';
            const active = document.querySelector('.nav-btn.active');
            if (active) redrawTabCharts(active.dataset.tab);
        });

        document.getElementById('btnAnalyzeLedger').addEventListener('click', runLedgerAnalysis);
        document.getElementById('ledgerSearchInput').addEventListener('input', renderLedgerTable);
        document.getElementById('ledgerTypeFilter').addEventListener('change', renderLedgerTable);
        document.getElementById('btnQuickAddTx').addEventListener('click', () => {
            const merch = (document.getElementById('quickTxMerchant').value || '').trim();
            const amt = Number(document.getElementById('quickTxAmount').value || 0);
            const t = document.getElementById('quickTxType').value;
            if (!merch || amt <= 0) {
                showToast('Enter both merchant name and positive amount.', true);
                return;
            }
            const verb = t === 'credit' ? `Credited Rs.${amt.toFixed(2)} towards ${merch}` : `Debited Rs.${amt.toFixed(2)} via UPI to ${merch}`;
            const ta = document.getElementById('smsLedgerInput');
            ta.value = `${verb} on 16-Nov-2026.\n` + ta.value;
            document.getElementById('quickTxMerchant').value = '';
            document.getElementById('quickTxAmount').value = '';
            runLedgerAnalysis();
        });
        document.getElementById('ledgerCsvUpload').addEventListener('change', (ev) => {
            const f = ev.target.files && ev.target.files[0];
            if (!f) return;
            const isPdf = f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf');
            const rd = new FileReader();
            rd.onload = async () => {
                if (isPdf) {
                    showToast(`Scanning bank statement PDF: ${f.name}...`, false);
                    const data = await postJson(
                        '/api/ledger/parse_pdf',
                        {
                            pdf_data: String(rd.result || ''),
                            monthly_budget_target: Number(document.getElementById('monthlyBudgetInput').value || 0),
                            provider: STATE.aiSettings.provider,
                            model: STATE.aiSettings.model,
                        },
                        STATE.aiSettings.apiKey ? { 'X-User-AI-Key': STATE.aiSettings.apiKey } : {}
                    );
                    if (data && data.normalized_feed) {
                        document.getElementById('smsLedgerInput').value = data.normalized_feed;
                        await runLedgerAnalysis();
                        showToast(`Extracted ${data.transaction_count} transactions from PDF (${data.extraction_source || 'Gemini'}).`, false);
                    }
                    return;
                }
                const data = await postJson('/api/ledger/parse_csv', {
                    csv_text: String(rd.result || ''),
                    monthly_budget_target: Number(document.getElementById('monthlyBudgetInput').value || 0),
                });
                if (data && data.normalized_feed) {
                    document.getElementById('smsLedgerInput').value = data.normalized_feed;
                    await runLedgerAnalysis();
                    showToast(`Imported ${data.transaction_count} statement rows.`, false);
                }
            };
            if (isPdf) rd.readAsDataURL(f);
            else rd.readAsText(f);
        });
        document.getElementById('btnExportCsv').addEventListener('click', async () => {
            const res = await fetch('/api/ledger/export.csv', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    raw_text: document.getElementById('smsLedgerInput').value,
                    monthly_budget_target: Number(document.getElementById('monthlyBudgetInput').value || 0),
                }),
            });
            const csvText = await res.text();
            const url = URL.createObjectURL(new Blob([csvText], { type: 'text/csv;charset=utf-8' }));
            const a = document.createElement('a');
            a.href = url; a.download = 'arthaledger_statement.csv';
            document.body.appendChild(a); a.click(); a.remove();
            URL.revokeObjectURL(url);
        });

        document.getElementById('btnRunFraudAudit').addEventListener('click', runFraudAudit);
        document.querySelectorAll('[data-fraud-preset]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const mode = btn.dataset.fraudPreset;
                const input = document.getElementById('fraudPayloadInput');
                if (mode === 'kyc') {
                    input.value = 'URGENT: Your demo bank KYC is suspended within 24 hours. Update immediately via http://bit.ly/demo-kyc-check and enter UPI PIN to avoid freeze.';
                } else if (mode === 'collect') {
                    input.value = 'upi://pay?pa=cashback-helpdesk@okexample&pn=Lottery%20Refund&am=19999&mode=02&tn=Enter%20UPI%20PIN%20to%20claim%20refund';
                } else if (mode === 'apk') {
                    input.value = 'Notice: Traffic e-Challan pending Rs.2,500. Download eChallan_RTO_Verify.apk or call bank support helpline 9876543210 immediately.';
                } else if (mode === 'anydesk') {
                    input.value = 'Install AnyDesk remote access support to verify your Rs.18,000 OLX advance payment and approve collect.';
                } else {
                    input.value = 'upi://pay?pa=metro.transit@okaxis&pn=City%20Metro%20Rail&am=120&tn=Monthly%20Smartcard%20Topup';
                }
                runFraudAudit();
            });
        });

        document.getElementById('fraudImageUpload').addEventListener('change', (ev) => {
            const f = ev.target.files && ev.target.files[0];
            if (!f) return;
            const rd = new FileReader();
            rd.onload = () => scanFraudImagePayload(String(rd.result || ''), f.type || 'image/png', f.name);
            rd.readAsDataURL(f);
        });
        document.getElementById('btnScanDemoScamQr').addEventListener('click', () => scanDemoQrSample('scam'));
        document.getElementById('btnScanDemoSafeQr').addEventListener('click', () => scanDemoQrSample('safe'));

        const taxRange = document.getElementById('taxGrossRange');
        const taxNum = document.getElementById('taxGrossInput');
        let taxTimer = null;
        taxRange.addEventListener('input', () => {
            taxNum.value = taxRange.value;
            document.getElementById('taxGrossLabel').textContent = fmtInr(taxRange.value);
            if (taxTimer) clearTimeout(taxTimer);
            taxTimer = setTimeout(runTaxAndWealth, 140);
        });
        const sipRange = document.getElementById('sipMonthlyRange');
        const sipNum = document.getElementById('sipMonthlyInput');
        sipRange.addEventListener('input', () => {
            sipNum.value = sipRange.value;
            document.getElementById('sipMonthlyLabel').textContent = `${fmtInr(sipRange.value)} / mo`;
            if (taxTimer) clearTimeout(taxTimer);
            taxTimer = setTimeout(runTaxAndWealth, 140);
        });
        document.getElementById('btnComputeTaxWealth').addEventListener('click', runTaxAndWealth);

        document.getElementById('btnSearchAmfi').addEventListener('click', searchAmfiFunds);
        document.getElementById('amfiSchemeSelect').addEventListener('change', runBacktest);
        document.getElementById('btnRunBacktest').addEventListener('click', runBacktest);
        document.getElementById('btnCompareFunds').addEventListener('click', runFundComparison);
        document.getElementById('btnFetchNewsImpact').addEventListener('click', runNewsImpact);
        document.getElementById('cmpFundASelect').addEventListener('change', runFundComparison);
        document.getElementById('cmpFundBSelect').addEventListener('change', runFundComparison);

        document.getElementById('btnAddSmeItem').addEventListener('click', () => {
            STATE.smeItems.push({ name: 'New Line Item', qty: 1, unit_price: 2500, gst_rate: 18 });
            renderSmeItemRows();
            runSmeAnalysis();
        });
        document.getElementById('btnComputeSme').addEventListener('click', runSmeAnalysis);

        document.querySelectorAll('[data-copilot-q]').forEach((btn) => {
            btn.addEventListener('click', () => {
                askCopilot(btn.dataset.copilotQ);
            });
        });
        document.getElementById('copilotForm').addEventListener('submit', (ev) => {
            ev.preventDefault();
            askCopilot(document.getElementById('copilotQuestionInput').value);
        });
        document.getElementById('btnClearCopilotChat').addEventListener('click', () => {
            STATE.copilotHistory = [];
            const out = document.getElementById('copilotOutput');
            out.replaceChildren();
            appendCopilotBubble('assistant', 'Conversation cleared. Ready for next cited query.');
            document.getElementById('copilotCitationsBar').classList.add('hidden');
            document.getElementById('copilotActionsBar').classList.add('hidden');
        });
        document.getElementById('copilotImageInput').addEventListener('change', (ev) => {
            const file = ev.target.files && ev.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = () => {
                STATE.attachedImageData = String(reader.result || '');
                STATE.attachedImageMime = file.type || 'image/png';
                document.getElementById('copilotImageStatus').textContent = file.name;
                document.getElementById('btnClearImage').classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        });
        document.getElementById('btnClearImage').addEventListener('click', () => {
            STATE.attachedImageData = '';
            document.getElementById('copilotImageInput').value = '';
            document.getElementById('copilotImageStatus').textContent = 'No image';
            document.getElementById('btnClearImage').classList.add('hidden');
        });

        const dock = document.getElementById('copilotDock');
        document.getElementById('btnMobileCopilot').addEventListener('click', () => dock.classList.add('mobile-open'));
        document.getElementById('btnCloseMobileCopilot').addEventListener('click', () => dock.classList.remove('mobile-open'));

        const modal = document.getElementById('settingsModal');
        document.getElementById('btnOpenSettings').addEventListener('click', () => {
            document.getElementById('aiProviderSelect').value = STATE.aiSettings.provider;
            document.getElementById('aiModelSelect').value = STATE.aiSettings.model;
            document.getElementById('aiApiKeyInput').value = STATE.aiSettings.apiKey;
            modal.classList.remove('hidden');
        });
        document.getElementById('btnCloseSettings').addEventListener('click', () => modal.classList.add('hidden'));
        modal.addEventListener('click', (ev) => { if (ev.target === modal) modal.classList.add('hidden'); });
        document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') modal.classList.add('hidden'); });
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
            document.getElementById('copilotProviderStatus').textContent = `Engine: ${STATE.aiSettings.provider} (${STATE.aiSettings.model})`;
            showToast('AI provider settings saved for current tab.', false);
        });

        window.addEventListener('resize', () => {
            const active = document.querySelector('.nav-btn.active');
            if (active) redrawTabCharts(active.dataset.tab);
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        bindEvents();
        initScrollMotion();
        checkServerHealth();
        loadPersona('student_budget');
    });
})();
