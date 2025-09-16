# app/markets.py

from typing import Dict, Any, List, Tuple, Optional
import json
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import current_app

EIA_BASE = "https://api.eia.gov/v2/petroleum/pri/spt/data/"

# ---- Alias comunes -> series EIA oficiales ----
# RBRTE = Brent (Europe Brent Spot)
# RWTC  = WTI (Cushing, OK WTI Spot)
_SERIES_ALIASES = {
    "BRENT": "RBRTE",
    "BRET": "RBRTE",
    "BREN": "RBRTE",
    "RBRTE": "RBRTE",
    "WTI": "RWTC",
    "WTIC": "RWTC",
    "WTICUSH": "RWTC",
    "RWTC": "RWTC",
}

# ---------- Session con reintentos ----------
def _make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

_session = _make_session()

def _timeout():
    # (connect, read) – margen generoso por lentitud eventual del endpoint
    return (5, 60)

# ---------- Utils ----------
def _eia_key() -> str:
    # lee de config o de entorno, prioridad config
    return (
        current_app.config.get("EIA_API_KEY")
        or os.getenv("EIA_API_KEY", "")
    ).strip()

def _norm_series_id(sym: str) -> str:
    """
    Normaliza entradas variadas:
      'bret', 'brent', 'BRENT', 'RBRTE' -> 'RBRTE'
      'wti',  'WTI',   'RWTC'           -> 'RWTC'
      además acepta 'EIA.RBRTE' y devuelve 'RBRTE'
    """
    if not sym:
        return ""
    s = sym.strip().upper()

    # Permite "EIA.RBRTE" -> "RBRTE"
    if "." in s:
        parts = s.split(".")
        if len(parts) >= 2:
            s = parts[-1].strip().upper()

    # Aplica alias
    return _SERIES_ALIASES.get(s, s)

def _req_xparams(series_key: str, length: int, offset: int = 0) -> Optional[dict]:
    """
    Petición con header X-Params (recomendado por EIA) + paginación via offset.
    """
    api_key = _eia_key()
    if not api_key or not series_key:
        return None

    xparams = {
        "frequency": "daily",
        "data": ["value"],
        "facets": {"series": [series_key]},
        "sort": [{"column": "period", "direction": "desc"}],
        "offset": max(0, int(offset)),
        "length": max(1, int(length)),
    }
    headers = {"X-Params": json.dumps(xparams)}
    try:
        resp = _session.get(EIA_BASE, params={"api_key": api_key}, headers=headers, timeout=_timeout())
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        current_app.logger.exception(
            "EIA X-Params request error series=%s len=%s off=%s: %s",
            series_key, length, offset, e
        )
        return None

def _req_querystring(series_key: str, length: int, offset: int = 0) -> Optional[dict]:
    """
    Plan B: mismos filtros en querystring (por si X-Params es filtrado o ignorado).
    Incluye offset para paginación.
    """
    api_key = _eia_key()
    if not api_key or not series_key:
        return None
    try:
        params = {
            "api_key": api_key,
            "frequency": "daily",
            "data": "value",
            "length": max(1, int(length)),
            "offset": max(0, int(offset)),
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "facets[series][]": series_key,
        }
        resp = _session.get(EIA_BASE, params=params, timeout=_timeout())
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        current_app.logger.exception(
            "EIA querystring request error series=%s len=%s off=%s: %s",
            series_key, length, offset, e
        )
        return None

def _extract_rows(js: Optional[dict]) -> List[dict]:
    if not js:
        return []
    return (js.get("response", {}) or {}).get("data", []) or []

# ---------- Lecturas de dato único / series ----------
def _to_float_or_none(v) -> Optional[float]:
    try:
        return float(v) if v is not None and str(v).strip() != "" else None
    except Exception:
        return None

def _eia_get_latest_value(series_key: str) -> Optional[float]:
    """
    Último valor (float) o None. Intenta X-Params y cae a querystring si falla/queda vacío.
    """
    js = _req_xparams(series_key, length=1, offset=0)
    rows = _extract_rows(js)
    if not rows:
        js = _req_querystring(series_key, length=1, offset=0)
        rows = _extract_rows(js)
        if not rows:
            current_app.logger.warning(
                "EIA empty latest for series=%s (after fallback). Raw=%s", series_key, js
            )
            return None
    return _to_float_or_none(rows[0].get("value"))

def _eia_get_last_n(series_key: str, n: int) -> List[Tuple[str, float]]:
    """
    Descarga hasta n puntos recientes (desc) en bloques con paginación (offset).
    """
    n = max(1, int(n))
    out: List[Tuple[str, float]] = []
    offset = 0

    while len(out) < n:
        take = min(10, n - len(out))

        js = _req_xparams(series_key, length=take, offset=offset)
        rows = _extract_rows(js)
        if not rows:
            js = _req_querystring(series_key, length=take, offset=offset)
            rows = _extract_rows(js)

        if not rows:
            current_app.logger.warning(
                "EIA empty chunk series=%s len=%s off=%s", series_key, take, offset
            )
            break

        # Agregamos este bloque
        for r in rows:
            d = str(r.get("period", ""))[:10]
            v = _to_float_or_none(r.get("value"))
            if d and v is not None:
                out.append((d, v))

        if len(rows) < take:
            break
        offset += len(rows)

    return out[:n]

# ---------- Interfaz compatible con tu app ----------
def td_price_batch(symbols_csv: str) -> Dict[str, Any]:
    """
    'RBRTE,RWTC' o 'BRENT,WTI' -> {"RBRTE":{"price":"xx.x"},"RWTC":{"price":"yy.y"}}
    Mantiene las claves originales de entrada para no romper llamadas existentes.
    """
    out: Dict[str, Any] = {}
    if not symbols_csv:
        return out

    for raw in [s.strip() for s in symbols_csv.split(",") if s.strip()]:
        skey = _norm_series_id(raw)
        if not skey:
            out[raw] = {"price": None}
            continue
        val = _eia_get_latest_value(skey)
        out[raw] = {"price": (str(val) if val is not None else None)}
        if val is None:
            current_app.logger.warning("No latest value for input=%s mapped_series=%s", raw, skey)
    return out

def td_timeseries_daily(symbol: str, outputsize: int = 2) -> Dict[str, Any]:
    """
    'RBRTE' o 'BRENT' -> {"values":[{"datetime":"YYYY-MM-DD","close":85.1}, ...]} (orden desc).
    """
    skey = _norm_series_id(symbol)
    pairs = _eia_get_last_n(skey, outputsize) if skey else []
    values = [{"datetime": d, "close": v} for (d, v) in pairs]
    if not values:
        current_app.logger.warning("Empty timeseries for input=%s mapped_series=%s", symbol, skey)
    return {"values": values}

def parse_last_ts(ts_json: Dict[str, Any]):
    vals = ts_json.get("values") or []
    if not vals:
        return None, None
    d = str(vals[0].get("datetime", ""))[:10]
    c = vals[0].get("close")
    try:
        c = float(c) if c is not None else None
    except Exception:
        c = None
    return d, c
