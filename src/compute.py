#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FTSEMIB OVERNIGHT — PATTERN ANALYZER
GitHub Actions Auto-Update Version
"""

import numpy as np
import pandas as pd
import yfinance as yf
import warnings
import json
import os
from datetime import datetime

warnings.filterwarnings("ignore")

START_DATE = "2010-01-01"
ALLOWED_DAYS = [0, 1, 2, 3]  # Lun–Gio
OUTPUT_PATH = "docs/data/status.json"

# ========== FIX YAHOO DF ==========
def fix_yahoo_df(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join([str(x) for x in col]) for col in df.columns]
    else:
        df.columns = [str(c) for c in df.columns]
    return df

# ========== CLOSE EXTRACTOR ==========
def extract_single_close(df: pd.DataFrame) -> pd.Series:
    cols_low = [c.lower() for c in df.columns]
    for t in ["close", "adj close"]:
        if t in cols_low:
            return df[df.columns[cols_low.index(t)]]
    for i, c in enumerate(cols_low):
        if "close" in c:
            return df[df.columns[i]]
    for c in df.columns:
        if np.issubdtype(df[c].dtype, np.number):
            return df[c]
    raise RuntimeError("Nessuna colonna Close.")

# ========== LOAD FTSEMIB ==========
def load_ftsemib() -> pd.DataFrame:
    print("[*] Download FTSEMIB.MI…")
    df = yf.download("FTSEMIB.MI", start=START_DATE, interval="1d",
                     auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise RuntimeError("Errore: nessun dato FTSEMIB.")
    df = fix_yahoo_df(df)
    df = df.sort_index()
    close = extract_single_close(df)
    
    def find(words):
        for w in words:
            for col in df.columns:
                if w in col.lower():
                    return col
        return None
    
    o, h, l, v = find(["open"]), find(["high"]), find(["low"]), find(["vol"])
    if o and h and l:
        out = pd.DataFrame(index=df.index)
        out["Open"] = df[o]
        out["High"] = df[h]
        out["Low"] = df[l]
        out["Close"] = close
        out["Volume"] = df[v] if v else 0
        return out.dropna()
    
    print("[WARN] OHLC non trovati.")
    out = pd.DataFrame(index=df.index)
    out["Close"] = close
    out["Open"] = close.shift(1)
    out["High"] = out[["Open", "Close"]].max(axis=1)
    out["Low"] = out[["Open", "Close"]].min(axis=1)
    out["Volume"] = 0
    return out.dropna()

# ========== LOAD AUX ==========
def load_aux(symbol: str) -> pd.DataFrame | None:
    df = yf.download(symbol, start=START_DATE, interval="1d",
                     auto_adjust=False, progress=False)
    if df is None or df.empty:
        return None
    df = fix_yahoo_df(df)
    df = df.sort_index()
    c = extract_single_close(df)
    return pd.DataFrame({"Close": c})

# ========== BUILD DATASET ==========
def build_dataset() -> pd.DataFrame:
    ftse = load_ftsemib()
    df = ftse.copy()
    spy = load_aux("SPY")
    vix = load_aux("^VIX")
    if spy is not None:
        df = df.join(spy.rename(columns={"Close": "SPY_Close"}))
        df["spy_ret"] = df["SPY_Close"].pct_change()
    if vix is not None:
        df = df.join(vix.rename(columns={"Close": "VIX_Close"}))
        df["vix_ret"] = df["VIX_Close"].pct_change()
    
    df["Close_prev"] = df["Close"].shift(1)
    df["gap_open"] = df["Open"] / df["Close_prev"] - 1
    df["vol_ma"] = df["Volume"].rolling(20).mean()
    df["vol_std"] = df["Volume"].rolling(20).std()
    df["vol_z"] = (df["Volume"] - df["vol_ma"]) / df["vol_std"]
    df["Open_next"] = df["Open"].shift(-1)
    df["overnight_ret"] = df["Open_next"] / df["Close"] - 1
    df["dow"] = df.index.dayofweek
    return df.dropna()

# ========== MATCH TOP3 ==========
def match_top3(r: pd.Series) -> bool:
    cond = False
    if not pd.isna(r.get("spy_ret")):
        cond |= (0 <= r["gap_open"] < 0.01) and (0 <= r["spy_ret"] < 0.01)
    if not pd.isna(r.get("vix_ret")):
        cond |= (-0.10 <= r["vix_ret"] < -0.05)
    cond |= (-1.5 <= r["vol_z"] < -0.5)
    return bool(cond)

# ========== FILTERS ==========
def filters(r: pd.Series) -> bool:
    if not pd.isna(r.get("spy_ret")):
        if r["spy_ret"] < -0.005:
            return False
    if r["dow"] not in ALLOWED_DAYS:
        return False
    return True

# ========== BACKTEST ==========
def run_backtest(df: pd.DataFrame):
    df = df.copy()
    df["signal"] = df.apply(lambda r: match_top3(r) and filters(r), axis=1)
    trades = df[df["signal"]].copy()
    if trades.empty:
        return trades, pd.Series(dtype=float), 0.0, 0.0, 0.0, 0.0, 0.0
    
    trades["pnl"] = trades["overnight_ret"]
    trades["pnl_points"] = trades["overnight_ret"] * trades["Close"]
    trades["raw_points"] = trades["Open_next"] - trades["Close"]
    equity = (1 + trades["overnight_ret"]).cumprod()
    
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = equity.iloc[-1] ** (1 / years) - 1 if years > 0 else 0.0
    avg = float(trades["overnight_ret"].mean())
    avg_points = float(trades["pnl_points"].mean())
    win = float((trades["overnight_ret"] > 0).mean())
    avg_raw = float(trades["raw_points"].mean())
    return trades, equity, float(cagr), avg, win, avg_points, avg_raw

# ========== SYSTEM ==========
class System:
    def __init__(self, trades: pd.DataFrame):
        self.initial_capital = 100000.0
        self.trades = trades.copy()
        self.trades["pnl_$"] = self.trades["pnl"] * self.initial_capital
        self.trades["cum_pnl"] = self.trades["pnl_$"].cumsum()
        self.equity_curve = list(self.initial_capital + self.trades["cum_pnl"])
        peaks = np.maximum.accumulate(self.equity_curve)
        self.drawdown = (peaks - np.array(self.equity_curve)) / peaks * 100.0
        self.trades["result"] = ["WIN" if x > 0 else "LOSS" for x in self.trades["pnl_$"]]
        self.trades["trade"] = list(range(len(self.trades)))
        self.trades["position_pct"] = 100.0
        self.trades["equity_after"] = self.equity_curve

# ========== COMPUTE ALL ==========
def compute_all():
    print("[*] Building dataset…")
    df = build_dataset()
    print(f"[*] Rows: {len(df)}")
    
    print("[*] Running backtest…")
    trades, equity, cagr, avg, winrate, avg_points, avg_raw = run_backtest(df)
    
    last = df.iloc[-1]
    sig_bool = match_top3(last) and filters(last)
    last_date = last.name
    next_date = last_date + pd.Timedelta(days=1)
    
    signal = {
        "today": last_date.strftime("%Y-%m-%d"),
        "tomorrow": next_date.strftime("%Y-%m-%d"),
        "signal": "LONG" if sig_bool else "FLAT",
        "emoji": "🟢" if sig_bool else "🔴",
    }
    
    if trades.empty:
        metrics = {"trades": 0, "avg_pct": 0.0, "avg_points": 0.0, "avg_points_raw": 0.0,
                   "winrate_pct": 0.0, "cagr_pct": 0.0, "total_return_pct": 0.0}
        equity_series, trades_list = [], []
    else:
        system = System(trades)
        total_return_pct = float((equity.iloc[-1] - 1.0) * 100.0) if not equity.empty else 0.0
        metrics = {
            "trades": int(len(trades)),
            "avg_pct": float(avg * 100.0),
            "avg_points": float(avg_points),
            "avg_points_raw": float(avg_raw),
            "winrate_pct": float(winrate * 100.0),
            "cagr_pct": float(cagr * 100.0),
            "max_dd_pct": float(np.max(system.drawdown)) if len(system.drawdown) > 0 else 0.0,
            "total_return_pct": total_return_pct,
        }
        equity_series = [{"trade_index": int(idx), "date": ts.strftime("%Y-%m-%d"), "equity": float(eq)}
                         for idx, (ts, eq) in enumerate(zip(trades.index, system.equity_curve))]
        tdf = system.trades.reset_index().rename(columns={"index": "Date"}).tail(100)
        trades_list = [{"date": (dt.strftime("%Y-%m-%d") if isinstance(dt, pd.Timestamp) else str(dt)),
                        "pnl_pct": float(row["pnl"] * 100.0),
                        "pnl_points": float(row["pnl_points"]),
                        "pnl_raw": float(row["raw_points"]),
                        "pnl_dollar": float(row["pnl_$"]),
                        "result": str(row["result"]),
                        "equity_after": float(row["equity_after"])}
                       for _, row in tdf.iterrows()]
    
    result = {"metrics": metrics, "equity": equity_series, "trades": trades_list, "signal": signal,
              "updated_at": datetime.utcnow().isoformat()}
    return result

# ========== MAIN ==========
if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    print("[*] Starting computation…")
    data = compute_all()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[*] Output saved to {OUTPUT_PATH}")
    print("[*] Done!")
