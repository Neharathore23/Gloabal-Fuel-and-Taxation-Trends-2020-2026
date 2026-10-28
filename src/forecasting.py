"""Lightweight forecasting: naive baseline vs damped-trend Holt exponential smoothing (numpy only).

Prediction intervals are approximate (normal errors, residual std of one-step forecasts scaled by sqrt(h)).
When the underlying data are synthetic, forecasts are demonstrations only.
"""
import numpy as np
import pandas as pd

MIN_POINTS = 24


def _run(y: np.ndarray, alpha: float, beta: float, phi: float):
    level, trend = y[0], float(np.mean(np.diff(y[:4]))) if len(y) > 3 else 0.0
    fitted = np.empty(len(y))
    fitted[0] = y[0]
    for t in range(1, len(y)):
        fitted[t] = level + phi * trend
        new_level = alpha * y[t] + (1 - alpha) * (level + phi * trend)
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    return level, trend, fitted


def _fit(y: np.ndarray) -> dict:
    best = None
    for alpha in (0.1, 0.2, 0.3, 0.5, 0.7, 0.9):
        for beta in (0.05, 0.1, 0.2, 0.4):
            for phi in (0.8, 0.9, 0.98):
                level, trend, fitted = _run(y, alpha, beta, phi)
                sse = float(np.sum((y[1:] - fitted[1:]) ** 2))
                if best is None or sse < best["sse"]:
                    best = {"alpha": alpha, "beta": beta, "phi": phi, "sse": sse, "level": level, "trend": trend,
                            "fitted": fitted}
    return best


def _project(level: float, trend: float, phi: float, h: int) -> np.ndarray:
    steps = np.arange(1, h + 1)
    return level + np.cumsum(phi ** steps) * trend


def _errors(actual: np.ndarray, pred: np.ndarray) -> dict:
    return {"mae": float(np.mean(np.abs(actual - pred))), "mape_pct": float(np.mean(np.abs((actual - pred) / actual)) * 100)}


def forecast_series(s: pd.Series, horizon: int = 12, holdout: int = 6) -> dict:
    """Forecast a monthly series. Returns history, forecast (with 95% band), baseline and backtest metrics."""
    s = s.dropna()
    if len(s) < MIN_POINTS:
        raise ValueError(f"Need at least {MIN_POINTS} monthly points to forecast; got {len(s)}.")
    if not 1 <= horizon <= 36:
        raise ValueError("horizon must be between 1 and 36 months")
    y = s.to_numpy(float)

    train, test = y[:-holdout], y[-holdout:]
    m = _fit(train)
    holt_pred = _project(m["level"], m["trend"], m["phi"], holdout)
    naive_pred = np.full(holdout, train[-1])
    metrics = {"holdout_months": holdout, "holt": _errors(test, holt_pred), "naive": _errors(test, naive_pred)}

    m = _fit(y)
    fc = _project(m["level"], m["trend"], m["phi"], horizon)
    sigma = float(np.std(y[1:] - m["fitted"][1:], ddof=1))
    band = 1.96 * sigma * np.sqrt(np.arange(1, horizon + 1))
    idx = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    return {
        "history": pd.DataFrame({"date": s.index, "actual": y, "fitted": m["fitted"]}),
        "forecast": pd.DataFrame({"date": idx, "forecast": fc, "lower": np.maximum(fc - band, 0), "upper": fc + band,
                                  "naive": y[-1]}),
        "metrics": metrics,
        "params": {k: m[k] for k in ("alpha", "beta", "phi")},
        "method": "Damped-trend Holt exponential smoothing; baseline = last observed value",
        "interval": "approx. 95% (normal, residual std x sqrt(h))",
    }
