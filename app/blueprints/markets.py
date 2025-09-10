# app/blueprints/markets.py
from flask import Blueprint, render_template, jsonify, current_app, request
from datetime import datetime
from ..extensions import db
from ..models import MercadoUltimo, MercadoDaily
from ..utils import pct_change_n, rolling_insert_30  # si están en utils
from ..markets import td_price_batch, td_timeseries_daily

bp = Blueprint("markets", __name__)

@bp.get("/mercados")
def mercados_home():
    return render_template("mercados.html")

@bp.get("/mercados/dashboard.json")
def mercados_json():
    items = []
    unidades = {"brent": "USD/bbl", "wti": "USD/bbl"}
    nombres = {"brent": "Brent", "wti": "WTI"}
    for symbol in ("brent", "wti"):
        last = MercadoUltimo.query.filter_by(symbol=symbol).first()
        hist = (MercadoDaily.query
                .filter_by(symbol=symbol)
                .order_by(MercadoDaily.date.asc())
                .all())
        series = [h.close for h in hist]
        dates = [h.date.isoformat() if hasattr(h.date, "isoformat") else str(h.date) for h in hist]
        last_date = dates[-1] if dates else None
        items.append({
            "id": symbol, "name": nombres[symbol], "unit": unidades[symbol],
            "value": last.value if last else None, "asof": last.asof if last else None,
            "stale": bool(last.stale) if last else True,
            "chg_10d_pct": pct_change_n(series, 10),
            "chg_30d_pct": pct_change_n(series, 30),
            "spark": series[-30:], "spark_dates": dates[-30:], "last_date": last_date,
        })
    return jsonify({"updated_at": datetime.utcnow().isoformat()+"Z", "markets": items})

@bp.post("/tasks/refresh-mercados")
def refresh_mercados():
    token = request.headers.get("X-Refresh-Token", "")
    if token != current_app.config.get("CANAL_KEY", ""):
        return {"error": "unauthorized"}, 401

    symmap   = current_app.config.get("TWELVEDATA_SYMBOLS", {})
    brent_sym = symmap.get("brent")
    wti_sym   = symmap.get("wti")
    symbols_csv = ",".join([brent_sym, wti_sym])
    now_iso = datetime.utcnow().isoformat() + "Z"

    try:
        prices = td_price_batch(symbols_csv)
    except Exception as e:
        current_app.logger.exception("Error td_price_batch: %s", e)
        prices = {}

    for real_sym, logical in [(brent_sym, "brent"), (wti_sym, "wti")]:
        obj = prices.get(real_sym) or {}
        val = None
        try:
            if obj.get("price") is not None:
                val = float(obj.get("price"))
        except Exception:
            pass

        row = (MercadoUltimo.query.filter_by(symbol=logical).first()
               or MercadoUltimo(symbol=logical, unit="USD/bbl", value=0.0, asof=now_iso, stale=True))
        if val is not None:
            row.value, row.asof, row.stale = val, now_iso, False
        else:
            row.stale = True
            if not row.asof:
                row.asof = now_iso
        db.session.add(row)

    for logical, real_sym in [("brent", brent_sym), ("wti", wti_sym)]:
        try:
            ts = td_timeseries_daily(real_sym, outputsize=31)
            values = ts.get("values") or []
            for v in reversed(values[:30]):
                d = v.get("datetime", "")[:10]
                c = v.get("close")
                if d and (c is not None):
                    rolling_insert_30(db.session, logical, d, float(c), MercadoDaily)
        except Exception as e:
            current_app.logger.exception("Error time_series %s: %s", real_sym, e)

    db.session.commit()
    return {"ok": True}
