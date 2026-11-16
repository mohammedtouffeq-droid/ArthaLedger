"""Live AMFI Indian Mutual Fund analyzer & historical/synthetic paper-trading backtester (non-advisory)."""
from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from statistics import stdev
from typing import Any, Dict, List

POPULAR_INDIAN_FUNDS: List[Dict[str, str]] = [
    {"schemeCode": "120716", "schemeName": "UTI Nifty 50 Index Fund - Direct Plan - Growth"},
    {"schemeCode": "122639", "schemeName": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth"},
    {"schemeCode": "118989", "schemeName": "HDFC Mid Cap Fund - Direct Plan - Growth Option"},
    {"schemeCode": "125497", "schemeName": "SBI Small Cap Fund - Direct Plan - Growth"},
    {"schemeCode": "120503", "schemeName": "Axis ELSS Tax Saver Fund - Direct Plan - Growth Option"},
    {"schemeCode": "119091", "schemeName": "HDFC Liquid Fund - Direct Plan - Growth Option"},
    {"schemeCode": "120684", "schemeName": "ICICI Prudential Nifty Next 50 Index Fund - Direct Plan - Growth"},
    {"schemeCode": "119788", "schemeName": "SBI Gold Fund - Direct Plan - Growth"},
]

BENCHMARK_SERIES: Dict[str, Dict[str, Any]] = {
    "NIFTY50_PROXY": {
        "label": "NIFTY 50 Historical Proxy (52W Benchmark Series)",
        "prices": [
            22450, 22610, 22390, 22840, 23120, 23010, 23480, 23760, 23540, 23920,
            24250, 24610, 24480, 24190, 23820, 23310, 23050, 23490, 23880, 24150,
            24520, 24980, 25340, 25120, 24790, 24360, 24020, 24290, 24680, 25040,
            25410, 25760, 25590, 25940, 26280, 26550,
        ],
    },
    "IT_LARGE_CAP": {
        "label": "NSE IT Basket Proxy (Mean-Reverting Export Cycle)",
        "prices": [
            3420, 3490, 3550, 3480, 3390, 3310, 3260, 3340, 3460, 3580,
            3690, 3780, 3720, 3610, 3530, 3440, 3380, 3450, 3570, 3690,
            3820, 3910, 3860, 3790, 3740, 3830, 3940, 4020, 3970, 4080,
            4160, 4210, 4150, 4260, 4340, 4410,
        ],
    },
    "BANK_INDEX_PROXY": {
        "label": "Banking & PSU Proxy (Rate-Cycle Volatile Series)",
        "prices": [
            47800, 48300, 47950, 47200, 46600, 47100, 48200, 49100, 49850, 50400,
            51200, 50700, 49600, 48400, 47900, 48700, 49500, 50100, 50900, 51800,
            52400, 51900, 51100, 50400, 50950, 51700, 52600, 53100, 52700, 53400,
            53900, 54250, 53800, 54500, 55100, 55600,
        ],
    },
}

_MF_CACHE: Dict[str, Any] = {}


def search_amfi_funds(query: str) -> Dict[str, Any]:
    """Searches official public Indian AMFI mutual funds via api.mfapi.in with curated fallback."""
    q = str(query or "").strip()
    if not q:
        return {"success": True, "source": "curated_popular", "funds": POPULAR_INDIAN_FUNDS}

    cache_key = f"search:{q.lower()}"
    if cache_key in _MF_CACHE:
        return _MF_CACHE[cache_key]

    try:
        url = "https://api.mfapi.in/mf/search?q=" + urllib.parse.quote(q)
        req = urllib.request.Request(url, headers={"User-Agent": "ArthaLedger/2.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            items = json.loads(resp.read().decode("utf-8"))
        funds = [
            {"schemeCode": str(x["schemeCode"]), "schemeName": str(x["schemeName"])}
            for x in (items if isinstance(items, list) else [])[:15]
            if x.get("schemeCode") and x.get("schemeName")
        ]
        res = {"success": True, "source": "live_amfi_api", "funds": funds}
        _MF_CACHE[cache_key] = res
        return res
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        ql = q.lower()
        filtered = [f for f in POPULAR_INDIAN_FUNDS if ql in f["schemeName"].lower()] or POPULAR_INDIAN_FUNDS
        return {"success": True, "source": "offline_fallback", "funds": filtered}


def simulate_direct_vs_regular(monthly_sip: float = 15000.0, years: int = 15, gross_return_pct: float = 12.5, commission_drag_pct: float = 1.0) -> Dict[str, Any]:
    """Quantifies wealth lost over time to 1% Regular Mutual Fund distributor trail commission."""
    def _fv(r_ann: float) -> float:
        r_m = r_ann / 100.0 / 12.0
        bal = 0.0
        for _ in range(years * 12):
            bal = (bal + monthly_sip) * (1.0 + r_m)
        return bal

    direct_val = _fv(gross_return_pct)
    regular_val = _fv(max(0.0, gross_return_pct - commission_drag_pct))
    return {
        "direct_corpus": round(direct_val, 2),
        "regular_corpus": round(regular_val, 2),
        "commission_leakage": round(max(0.0, direct_val - regular_val), 2),
        "years": years,
        "monthly_sip": round(monthly_sip, 2),
    }


def _load_amfi_or_fallback(amfi_scheme_code: str, fallback_sym: str) -> tuple[List[float], List[str], str, str, str]:
    """Loads up to 52 weekly-sampled live AMFI NAV bars, falling back cleanly to synthetic series offline."""
    sym = fallback_sym if fallback_sym in BENCHMARK_SERIES else "NIFTY50_PROXY"
    code = re.sub(r"[^0-9]", "", str(amfi_scheme_code or ""))
    if not code:
        return list(BENCHMARK_SERIES[sym]["prices"]), [], sym, BENCHMARK_SERIES[sym]["label"], "synthetic_benchmark_proxy"

    try:
        cache_k = f"nav:{code}"
        if cache_k in _MF_CACHE:
            nav_payload = _MF_CACHE[cache_k]
        else:
            req = urllib.request.Request(f"https://api.mfapi.in/mf/{code}", headers={"User-Agent": "ArthaLedger/3.0"})
            with urllib.request.urlopen(req, timeout=7) as resp:
                nav_payload = json.loads(resp.read().decode("utf-8"))
            _MF_CACHE[cache_k] = nav_payload

        raw_rows = list(reversed((nav_payload.get("data") or [])[:260]))
        sampled = raw_rows[::5] if len(raw_rows) > 80 else raw_rows
        nav_prices = [float(r["nav"]) for r in sampled if float(r.get("nav") or 0) > 0]
        if len(nav_prices) >= 12:
            dates = [str(r.get("date", "")) for r in sampled[: len(nav_prices)]]
            meta = nav_payload.get("meta") or {}
            label = str(meta.get("scheme_name") or f"AMFI Mutual Fund {code}")
            return nav_prices, dates, f"AMFI:{code}", label, "live_amfi_public_nav"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, KeyError):
        pass

    return (
        list(BENCHMARK_SERIES[sym]["prices"]),
        [],
        sym,
        BENCHMARK_SERIES[sym]["label"] + " (AMFI Offline Fallback)",
        "synthetic_benchmark_proxy",
    )


def _series_quant_metrics(prices: List[float]) -> Dict[str, Any]:
    """Computes total return, CAGR, annualized volatility, Sharpe ratio, and max drawdown on a price array."""
    if len(prices) < 4:
        return {"total_return_pct": 0.0, "cagr_pct": 0.0, "ann_vol_pct": 0.0, "sharpe_ratio": 0.0, "max_drawdown_pct": 0.0, "rets": []}
    rets: List[float] = []
    peak = prices[0]
    max_dd = 0.0
    for i, px in enumerate(prices):
        if px > peak:
            peak = px
        dd = ((peak - px) / peak) * 100.0 if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
        if i > 0 and prices[i - 1] > 0:
            rets.append((px - prices[i - 1]) / prices[i - 1])
    total_ret = ((prices[-1] - prices[0]) / prices[0]) * 100.0 if prices[0] > 0 else 0.0
    yrs = max(len(prices) / 52.0, 0.25)
    cagr = (((prices[-1] / prices[0]) ** (1.0 / yrs)) - 1.0) * 100.0 if prices[0] > 0 else 0.0
    ann_vol = stdev(rets) * math.sqrt(52.0) * 100.0 if len(rets) >= 3 else 0.0
    mean_ann = (sum(rets) / len(rets)) * 52.0 * 100.0 if rets else 0.0
    sharpe = (mean_ann - 6.5) / ann_vol if ann_vol > 0.05 else 0.0
    return {
        "total_return_pct": round(total_ret, 2),
        "cagr_pct": round(cagr, 2),
        "ann_vol_pct": round(ann_vol, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "rets": rets,
    }


def _compute_sharpe(equity_curve: List[Dict[str, Any]], bars_per_year: float = 52.0) -> tuple[float, float]:
    if len(equity_curve) < 4:
        return 0.0, 0.0
    rets = []
    for i in range(1, len(equity_curve)):
        prev = float(equity_curve[i - 1]["strategy_equity"] or 1.0)
        cur = float(equity_curve[i]["strategy_equity"] or prev)
        if prev > 0:
            rets.append((cur - prev) / prev)
    if len(rets) < 3:
        return 0.0, 0.0
    ann_vol = stdev(rets) * math.sqrt(bars_per_year) * 100.0
    mean_ann = (sum(rets) / len(rets)) * bars_per_year * 100.0
    sharpe = (mean_ann - 6.5) / ann_vol if ann_vol > 0.05 else 0.0
    return round(ann_vol, 2), round(sharpe, 2)


def run_paper_backtest(
    symbol: str = "NIFTY50_PROXY",
    strategy: str = "sma_crossover",
    initial_capital: float = 100000.0,
    fast_window: int = 3,
    slow_window: int = 7,
    custom_prices: List[float] | None = None,
    amfi_scheme_code: str = "",
) -> Dict[str, Any]:
    """
    Runs a strictly historical/paper-trading simulation on either live public AMFI NAV history
    or built-in synthetic benchmark proxies (10 bps cost, zero live brokerage orders).
    """
    sym = symbol if symbol in BENCHMARK_SERIES else "NIFTY50_PROXY"
    data_source = "synthetic_benchmark_proxy"
    dates: List[str] = []

    if amfi_scheme_code:
        prices, dates, sym, label, data_source = _load_amfi_or_fallback(amfi_scheme_code, sym)
    elif custom_prices and len(custom_prices) >= 12:
        prices = [float(p) for p in custom_prices if float(p) > 0]
        label = "Custom Historical Close Series"
        data_source = "user_custom_series"
    else:
        prices = list(BENCHMARK_SERIES[sym]["prices"])
        label = BENCHMARK_SERIES[sym]["label"]

    capital = max(1000.0, float(initial_capital or 100000.0))
    fast_w = max(2, min(10, int(fast_window or 3)))
    slow_w = max(fast_w + 1, min(18, int(slow_window or 7)))
    fee_rate = 0.001

    cash = capital
    units = 0.0
    trades: List[Dict[str, Any]] = []
    equity_curve: List[Dict[str, Any]] = []
    peak_equity = capital
    max_drawdown_pct = 0.0

    strat = strategy if strategy in ("sma_crossover", "dip_accumulation") else "sma_crossover"

    for i, price in enumerate(prices):
        if strat == "sma_crossover" and i >= slow_w:
            fast_sma = sum(prices[i - fast_w + 1 : i + 1]) / fast_w
            slow_sma = sum(prices[i - slow_w + 1 : i + 1]) / slow_w
            if fast_sma > slow_sma and units == 0.0 and cash > 0:
                units = (cash * (1.0 - fee_rate)) / price
                cash = 0.0
                trades.append({"week": i + 1, "side": "BUY_PAPER", "price": price, "units": round(units, 4)})
            elif fast_sma < slow_sma and units > 0.0:
                proceeds = (units * price) * (1.0 - fee_rate)
                entry_price = next((t["price"] for t in reversed(trades) if t["side"] == "BUY_PAPER"), price)
                pnl_pct = ((price - entry_price) / entry_price) * 100.0
                cash = proceeds
                units = 0.0
                trades.append({"week": i + 1, "side": "SELL_PAPER", "price": price, "pnl_pct": round(pnl_pct, 2)})
        elif strat == "dip_accumulation":
            if i == 0:
                deploy = cash * 0.30
                units += (deploy * (1.0 - fee_rate)) / price
                cash -= deploy
                trades.append({"week": 1, "side": "BUY_PAPER", "price": price, "units": round(units, 4)})
            elif i >= 4 and cash > capital * 0.05:
                recent_high = max(prices[max(0, i - 4) : i])
                if price <= recent_high * 0.975:
                    deploy = cash * 0.45
                    bought = (deploy * (1.0 - fee_rate)) / price
                    units += bought
                    cash -= deploy
                    trades.append({"week": i + 1, "side": "DIP_BUY_PAPER", "price": price, "units": round(bought, 4)})

        equity = cash + units * price
        if equity > peak_equity:
            peak_equity = equity
        dd_pct = ((peak_equity - equity) / peak_equity) * 100.0 if peak_equity > 0 else 0.0
        if dd_pct > max_drawdown_pct:
            max_drawdown_pct = dd_pct

        bh_equity = (capital * (1.0 - fee_rate) / prices[0]) * price
        equity_curve.append({
            "period": i + 1,
            "date": dates[i] if i < len(dates) else f"W{i + 1}",
            "price": round(price, 2),
            "strategy_equity": round(equity, 2),
            "buy_hold_equity": round(bh_equity, 2),
            "drawdown_pct": round(dd_pct, 2),
        })

    final_equity = equity_curve[-1]["strategy_equity"]
    bh_final = equity_curve[-1]["buy_hold_equity"]
    total_return_pct = ((final_equity - capital) / capital) * 100.0
    bh_return_pct = ((bh_final - capital) / capital) * 100.0

    yrs = max(len(prices) / 52.0, 0.25)
    cagr_pct = (((final_equity / capital) ** (1.0 / yrs)) - 1.0) * 100.0
    ann_vol_pct, sharpe_ratio = _compute_sharpe(equity_curve, bars_per_year=52.0)

    closed_sells = [t for t in trades if "pnl_pct" in t]
    wins = sum(1 for t in closed_sells if t["pnl_pct"] > 0)
    win_rate_pct = (wins / len(closed_sells) * 100.0) if closed_sells else (100.0 if final_equity >= capital else 0.0)
    direct_drag = simulate_direct_vs_regular(monthly_sip=round(capital / 10.0, -2) or 5000.0, years=15)

    return {
        "success": True,
        "paper_trading_only": True,
        "data_source": data_source,
        "disclaimer": "Historical/public AMFI NAV or synthetic paper simulation only. Zero live orders.",
        "symbol": sym,
        "label": label,
        "strategy": strat,
        "periods": len(prices),
        "initial_capital": round(capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "annualized_cagr_pct": round(cagr_pct, 2),
        "annualized_volatility_pct": ann_vol_pct,
        "sharpe_ratio": sharpe_ratio,
        "benchmark_return_pct": round(bh_return_pct, 2),
        "alpha_vs_benchmark_pct": round(total_return_pct - bh_return_pct, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "win_rate_pct": round(win_rate_pct, 1),
        "direct_vs_regular": direct_drag,
        "trade_count": len(trades),
        "trades": trades[:18],
        "equity_curve": equity_curve,
    }


def compare_amfi_funds(scheme_a: str = "120716", scheme_b: str = "122639") -> Dict[str, Any]:
    """Compares two live public AMFI schemes (rebased 100 curve, CAGR, Sharpe, Max Drawdown & return correlation)."""
    code_a = re.sub(r"[^0-9]", "", str(scheme_a or "")) or "120716"
    code_b = re.sub(r"[^0-9]", "", str(scheme_b or "")) or "122639"

    px_a, dates_a, sym_a, label_a, src_a = _load_amfi_or_fallback(code_a, "NIFTY50_PROXY")
    px_b, dates_b, sym_b, label_b, src_b = _load_amfi_or_fallback(code_b, "BANK_INDEX_PROXY")

    n = min(len(px_a), len(px_b))
    if n < 4:
        return {"success": False, "error": "Insufficient historical NAV bars to compare these schemes."}

    a_sub = px_a[-n:]
    b_sub = px_b[-n:]
    d_sub = (dates_a[-n:] if len(dates_a) >= n else (dates_b[-n:] if len(dates_b) >= n else [f"W{i + 1}" for i in range(n)]))

    m_a = _series_quant_metrics(a_sub)
    m_b = _series_quant_metrics(b_sub)
    ra, rb = m_a["rets"], m_b["rets"]

    corr = 0.0
    if len(ra) >= 4 and len(ra) == len(rb):
        ma = sum(ra) / len(ra)
        mb = sum(rb) / len(rb)
        num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
        den_a = math.sqrt(sum((x - ma) ** 2 for x in ra))
        den_b = math.sqrt(sum((y - mb) ** 2 for y in rb))
        if den_a > 0 and den_b > 0:
            corr = round(max(-1.0, min(1.0, num / (den_a * den_b))), 2)

    if corr >= 0.78:
        overlap_note = f"HIGH OVERLAP (r={corr:.2f}): Both funds move nearly identically; diversifying with Debt/Gold reduces concentration risk."
    elif corr >= 0.45:
        overlap_note = f"MODERATE CORRELATION (r={corr:.2f}): Partial diversification across equity styles."
    else:
        overlap_note = f"STRONG DIVERSIFICATION (r={corr:.2f}): Low return correlation helps smooth portfolio drawdowns."

    base_a, base_b = a_sub[0] or 1.0, b_sub[0] or 1.0
    series = [
        {
            "period": i + 1,
            "date": d_sub[i] if i < len(d_sub) else f"W{i + 1}",
            "fund_a_indexed": round((a_sub[i] / base_a) * 100.0, 2),
            "fund_b_indexed": round((b_sub[i] / base_b) * 100.0, 2),
        }
        for i in range(n)
    ]

    return {
        "success": True,
        "periods": n,
        "correlation": corr,
        "overlap_note": overlap_note,
        "winner_sharpe": label_a if m_a["sharpe_ratio"] >= m_b["sharpe_ratio"] else label_b,
        "winner_return": label_a if m_a["total_return_pct"] >= m_b["total_return_pct"] else label_b,
        "fund_a": {
            "symbol": sym_a,
            "label": label_a,
            "data_source": src_a,
            **{k: v for k, v in m_a.items() if k != "rets"},
        },
        "fund_b": {
            "symbol": sym_b,
            "label": label_b,
            "data_source": src_b,
            **{k: v for k, v in m_b.items() if k != "rets"},
        },
        "series": series,
    }
