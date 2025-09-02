# app/markets.py

from typing import Dict, Any, List, Tuple, Optional
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import current_app

EIA_BASE = "https://api.eia.gov/v2/petroleum/pri/spt/data/"

# ---------- Session con reintentos ----------
def _make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
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
    # (connect, read) – dejamos buen margen al read por lentitud del endpoint
    return (5, 45)

# ---------- Utils ----------
def _eia_key() -> str:
    return (current_app.config.get("EIA_API_KEY") or "").strip()

def _norm_series_id(sym: str) -> str:
    if not sym:
        return ""
    s = sym.strip().upper()
    # Permitimos "EIA.RBRTE" -> "RBRTE"
    if "." in s:
        parts = s.split(".")
        if len(parts) >= 2:
            return parts[1]
    return s

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
        current_app.logger.exception("EIA X-Params request error %s len=%s off=%s: %s",
                                     series_key, length, offset, e)
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
        current_app.logger.exception("EIA querystring request error %s len=%s off=%s: %s",
                                     series_key, length, offset, e)
        return None

def _extract_rows(js: Optional[dict]) -> List[dict]:
    if not js:
        return []
    return (js.get("response", {}) or {}).get("data", []) or []

# ---------- Lecturas de dato único / series ----------
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
            current_app.logger.warning("EIA empty latest for %s (after fallback): %s", series_key, js)
            return None
    try:
        return float(rows[0]["value"])
    except Exception:
        return None

def _eia_get_last_n(series_key: str, n: int) -> List[Tuple[str, float]]:
    """
    Descarga hasta n puntos recientes (desc) en bloques con paginación (offset).
    Esto evita timeouts y repetición del mismo bloque.
    """
    n = max(1, int(n))
    out: List[Tuple[str, float]] = []
    offset = 0

    while len(out) < n:
        # Pedimos en bloques de 10 para ser conservadores con el endpoint
        take = min(10, n - len(out))

        js = _req_xparams(series_key, length=take, offset=offset)
        rows = _extract_rows(js)
        if not rows:
            js = _req_querystring(series_key, length=take, offset=offset)
            rows = _extract_rows(js)

        if not rows:
            current_app.logger.warning("EIA empty chunk for %s len=%s off=%s", series_key, take, offset)
            break

        # Agregamos este bloque
        for r in rows:
            try:
                out.append((str(r["period"]), float(r["value"])))
            except Exception:
                continue

        # Si nos devolvieron menos que 'take', ya no hay más páginas
        if len(rows) < take:
            break

        # Avanza el offset para la siguiente página (como estamos en orden desc)
        offset += len(rows)

    # Asegura tamaño n
    return out[:n]

# ---------- Interfaz compatible con tu app ----------
def td_price_batch(symbols_csv: str) -> Dict[str, Any]:
    """
    'RBRTE,RWTC' -> {"RBRTE":{"price":"xx.x"},"RWTC":{"price":"yy.y"}}
    """
    out: Dict[str, Any] = {}
    if not symbols_csv:
        return out
    for raw in [s.strip() for s in symbols_csv.split(",") if s.strip()]:
        skey = _norm_series_id(raw)
        val = _eia_get_latest_value(skey)
        out[raw] = {"price": (str(val) if val is not None else None)}
    return out

def td_timeseries_daily(symbol: str, outputsize: int = 2) -> Dict[str, Any]:
    """
    'RBRTE' -> {"values":[{"datetime":"YYYY-MM-DD","close":85.1}, ...]} (orden desc).
    """
    skey = _norm_series_id(symbol)
    pairs = _eia_get_last_n(skey, outputsize) if skey else []
    values = [{"datetime": d, "close": v} for (d, v) in pairs]
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
