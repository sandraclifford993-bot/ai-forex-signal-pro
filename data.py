import requests
import pandas as pd

def fetch_candles(pair, api_key, outputsize=250):
    response = requests.get(
        "https://api.twelvedata.com/time_series",
        params={"symbol": pair, "interval": "5min", "outputsize": outputsize,
                "apikey": api_key, "format": "JSON"},
        timeout=25
    )
    response.raise_for_status()
    payload = response.json()
    if "values" not in payload:
        raise RuntimeError(payload.get("message", "Market data unavailable"))
    df = pd.DataFrame(payload["values"])
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    df = df.dropna().sort_values("datetime").reset_index(drop=True)
    if len(df) < 205:
        raise RuntimeError("Not enough candle history")
    return df
