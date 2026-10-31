import pandas as pd
import numpy as np

def analyze(pair, df):
    x = df.copy()
    c = x.close
    x["ema9"] = c.ewm(span=9, adjust=False).mean()
    x["ema21"] = c.ewm(span=21, adjust=False).mean()
    x["ema50"] = c.ewm(span=50, adjust=False).mean()
    x["ema200"] = c.ewm(span=200, adjust=False).mean()
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    x["rsi"] = 100 - 100/(1 + up/dn.replace(0, np.nan))
    m = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    x["macd"] = m
    x["macd_sig"] = m.ewm(span=9, adjust=False).mean()
    tr = pd.concat([x.high-x.low, (x.high-c.shift()).abs(), (x.low-c.shift()).abs()], axis=1).max(axis=1)
    x["atr"] = tr.rolling(14).mean()
    plus = x.high.diff().clip(lower=0)
    minus = (-x.low.diff()).clip(lower=0)
    atr = tr.ewm(alpha=1/14, adjust=False).mean()
    pdi = 100*plus.ewm(alpha=1/14, adjust=False).mean()/atr
    mdi = 100*minus.ewm(alpha=1/14, adjust=False).mean()/atr
    dx = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)
    x["adx"] = dx.ewm(alpha=1/14, adjust=False).mean()
    x["bb_mid"] = c.rolling(20).mean()
    x = x.dropna()
    if len(x) < 3:
        raise RuntimeError("Indicator history incomplete")
    r, prev = x.iloc[-2], x.iloc[-3]  # last completed 5m candle
    bull = bear = 0
    why = []
    if r.ema9 > r.ema21 > r.ema50 > r.ema200: bull += 25; why.append("bullish EMA alignment")
    if r.ema9 < r.ema21 < r.ema50 < r.ema200: bear += 25; why.append("bearish EMA alignment")
    if r.macd > r.macd_sig and r.macd > prev.macd: bull += 20; why.append("bullish MACD")
    if r.macd < r.macd_sig and r.macd < prev.macd: bear += 20; why.append("bearish MACD")
    if 50 < r.rsi < 68: bull += 15; why.append("bullish RSI zone")
    if 32 < r.rsi < 50: bear += 15; why.append("bearish RSI zone")
    if r.adx >= 20:
        bull += 10; bear += 10
    if r.close > r.bb_mid: bull += 10
    if r.close < r.bb_mid: bear += 10
    if r.close > r.open: bull += 10
    if r.close < r.open: bear += 10
    spike = r.atr > 0 and (r.high-r.low) > 2.5*r.atr
    if spike or r.adx < 15:
        decision, score, reason = "NO TRADE", max(bull,bear), "Volatility spike or weak trend"
    elif bull >= 70 and bull >= bear+15:
        decision, score, reason = "CALL", bull, "; ".join(why)
    elif bear >= 70 and bear >= bull+15:
        decision, score, reason = "PUT", bear, "; ".join(why)
    else:
        decision, score, reason = "NO TRADE", max(bull,bear), "Insufficient confirmation"
    return {"pair": pair, "decision": decision, "score": int(score),
            "entry_price": float(r.close), "candle_time": r.datetime.isoformat(),
            "rsi": round(float(r.rsi),1), "adx": round(float(r.adx),1), "reason": reason}
