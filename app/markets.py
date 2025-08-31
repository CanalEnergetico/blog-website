import requests
from flask import current_app

def _key():
    return current_app.config.get("TWELVEDATA_API_KEY", "")

def td_price_batch(symbols_csv: str) -> dict:
    url = f"https://api.twelvedata.com/price?symbol={symbols_csv}&apikey={_key()}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

def td_timeseries_daily(symbol: str, outputsize: int = 2) -> dict:
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1day&outputsize={outputsize}&apikey={_key()}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

def parse_last_ts(ts_json: dict):
    vals = ts_json.get("values") or []
    if not vals:
        return None, None
    d = vals[0].get("datetime", "")[:10]
    c = float(vals[0].get("close"))
    return d, c
