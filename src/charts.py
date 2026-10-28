"""Dashboard figure + table builders.

Every chart is a plain Plotly JSON spec ({"data": [...], "layout": {...}}) built from `src.analytics` results, so the
Flask API can return it as-is and Plotly.js renders it in the browser (no plotly Python package needed).
All builders share the same filters, theme and empty-state handling.
"""
import math
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

import config
from src import analytics as A
from src import forecasting

# ---------------------------------------------------------------- theme (colour-blind-safe Okabe-Ito based)
FUEL_COLORS = {"Petrol": "#0072B2", "Diesel": "#E69F00", "LPG": "#009E73"}
REGION_COLORS = {"East Asia & Pacific": "#0072B2", "Europe & Central Asia": "#E69F00",
                 "Latin America & Caribbean": "#009E73", "Middle East & North Africa": "#D55E00",
                 "North America": "#CC79A7", "South Asia": "#56B4E9", "Sub-Saharan Africa": "#8A8300"}
INCOME_COLORS = {"Low": "#6BAED6", "Lower-middle": "#3182BD", "Upper-middle": "#08519C", "High": "#08306B"}
FALLBACK = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#8A8300"]
GRID = "#e5e7eb"
BY_OPTIONS = {"fuel_type": FUEL_COLORS, "region": REGION_COLORS, "income_group": INCOME_COLORS}
GEO_NOTE = "Partial years are marked with *."


class NoData(Exception):
    """Raised by a builder when the current filters leave nothing to draw (UI shows an empty state)."""


@dataclass(frozen=True)
class ChartSpec:
    name: str
    title: str
    page: str
    fn: Callable


REGISTRY: dict[str, ChartSpec] = {}


def register(name: str, title: str, page: str):
    def deco(fn):
        REGISTRY[name] = ChartSpec(name, title, page, fn)
        return fn
    return deco


# ---------------------------------------------------------------- shared helpers
def jsonable(x):
    """Recursively convert numpy/pandas values to JSON-safe python (NaN/inf -> None)."""
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return jsonable(x.tolist())
    if isinstance(x, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(x).date())
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if (math.isnan(x) or math.isinf(x)) else float(x)
    if x is pd.NA or x is pd.NaT:
        return None
    return x


def is_synthetic() -> bool:
    df = A.query("SELECT data_origin FROM etl_run ORDER BY run_id DESC LIMIT 1")
    return bool(len(df)) and str(df.iloc[0, 0]).upper().startswith("SYNTHETIC")


def describe(f: A.Filters) -> str:
    """Human-readable summary of the active filters."""
    parts = []
    if f.fuels:
        parts.append("/".join(f.fuels))
    if f.regions:
        parts.append(", ".join(f.regions))
    if f.income_groups:
        parts.append(", ".join(f.income_groups) + " income")
    if f.countries:
        parts.append(f"{len(f.countries)} selected countr{'y' if len(f.countries) == 1 else 'ies'}")
    if f.date_from or f.date_to:
        parts.append(f"{(f.date_from or '')[:7] or 'start'} to {(f.date_to or '')[:7] or 'end'}")
    return "; ".join(parts) if parts else "all countries, fuels and months"


def _need(df: pd.DataFrame, msg: str = "No data matches the current filters. Widen or reset the filters."):
    if df is None or df.empty:
        raise NoData(msg)
    return df


def _layout(xtitle: str | None = None, ytitle: str | None = None, **extra) -> dict:
    lay = {
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif", "size": 12, "color": "#1f2937"},
        "margin": {"l": 56, "r": 16, "t": 12, "b": 48},
        "hovermode": "closest",
        "hoverlabel": {"font": {"size": 12}},
        "legend": {"orientation": "h", "y": -0.2, "x": 0, "title": {"text": ""}},
        "xaxis": {"title": {"text": xtitle or ""}, "gridcolor": GRID, "zeroline": False, "automargin": True},
        "yaxis": {"title": {"text": ytitle or ""}, "gridcolor": GRID, "zeroline": False, "automargin": True},
    }
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(lay.get(k), dict):
            lay[k] = {**lay[k], **v}
        else:
            lay[k] = v
    return lay


def _colors(group_by: str) -> dict:
    return BY_OPTIONS.get(group_by, {})


def _color(mapping: dict, key: str, i: int) -> str:
    return mapping.get(key, FALLBACK[i % len(FALLBACK)])


def _year_labels(years, f: A.Filters) -> dict:
    """Map year -> label; the first/last year gets '*' when the selected window does not cover it fully."""
    opt = A.options()
    start = pd.Timestamp((f.date_from or opt["date_min"] + "-01")[:7] + "-01")
    end = pd.Timestamp((f.date_to or opt["date_max"] + "-01")[:7] + "-01")
    lab = {int(y): str(int(y)) for y in years}
    if int(start.year) in lab and start.month != 1:
        lab[int(start.year)] += "*"
    if int(end.year) in lab and end.month != 12:
        lab[int(end.year)] += "*"
    return lab


def _scatter(df, x, y, group, colors, xtitle, ytitle, order=None, fit=True, logx=False, logy=False,
             hover_x="%{x:.2f}", hover_y="%{y:.2f}"):
    traces = []
    groups = [g for g in (order or df[group].unique().tolist()) if g in set(df[group])]
    for i, g in enumerate(groups):
        s = df[df[group] == g]
        traces.append({"type": "scatter", "mode": "markers", "name": g, "x": s[x].tolist(), "y": s[y].tolist(),
                       "customdata": s[["country", "region", "income_group"]].values.tolist(),
                       "marker": {"size": 9, "opacity": 0.85, "color": _color(colors, g, i),
                                  "line": {"width": 0.8, "color": "#ffffff"}},
                       "hovertemplate": ("<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]} income<br>"
                                         f"{xtitle}: {hover_x}<br>{ytitle}: {hover_y}<extra></extra>")})
    r = None
    sub = df[[x, y]].dropna()
    if fit and len(sub) >= 5 and sub[x].std() > 0:
        xs, ys = sub[x].to_numpy(float), sub[y].to_numpy(float)
        if logx:
            xs = np.log10(xs)
        if logy:
            ys = np.log10(ys)
        ok = np.isfinite(xs) & np.isfinite(ys)
        if ok.sum() >= 5 and np.std(xs[ok]) > 0:
            slope, icpt = np.polyfit(xs[ok], ys[ok], 1)
            r = float(np.corrcoef(xs[ok], ys[ok])[0, 1])
            gx = np.linspace(xs[ok].min(), xs[ok].max(), 30)
            gy = slope * gx + icpt
            traces.append({"type": "scatter", "mode": "lines", "name": "Linear fit (association only)",
                           "x": (10 ** gx if logx else gx).tolist(), "y": (10 ** gy if logy else gy).tolist(),
                           "line": {"color": "#6b7280", "dash": "dash", "width": 1.5}, "hoverinfo": "skip"})
    lay = _layout(xtitle, ytitle)
    if logx:
        lay["xaxis"]["type"] = "log"
    if logy:
        lay["yaxis"]["type"] = "log"
    return traces, lay, r


def _r_note(r, n, what) -> str:
    if r is None:
        return f"{n} countries. Association only; not evidence of causation."
    return (f"Each point is one country (mean over the selected months). Pearson r = {r:.2f} across {n} countries"
            f"{what}. Association only; correlation does not show that one variable causes the other.")


# ---------------------------------------------------------------- charts
@register("choropleth", "Global average retail price by country", "dashboard")
def choropleth(f, o):
    df = _need(A.country_averages(f))
    data = [{"type": "choropleth", "locationmode": "ISO-3", "locations": df["country_code"].tolist(),
             "z": df["avg_price"].round(4).tolist(), "text": df["country"].tolist(),
             "customdata": df[["region", "effective_tax_burden_pct", "avg_affordability_pct"]].values.tolist(),
             "colorscale": "Viridis", "reversescale": True,
             "marker": {"line": {"color": "#ffffff", "width": 0.4}},
             "colorbar": {"title": {"text": "USD / litre"}, "thickness": 12, "len": 0.75},
             "hovertemplate": ("<b>%{text}</b><br>%{customdata[0]}<br>Avg price: $%{z:.2f}/L<br>"
                               "Tax burden: %{customdata[1]:.1f}% of price<br>"
                               "Affordability: %{customdata[2]:.1f}% of daily income per L<extra></extra>")}]
    lay = _layout(margin={"l": 0, "r": 0, "t": 0, "b": 0},
                  geo={"projection": {"type": "natural earth"}, "showframe": False, "showcoastlines": False,
                       "showland": True, "landcolor": "#eef0f3", "showcountries": True, "countrycolor": "#d1d5db",
                       "bgcolor": "rgba(0,0,0,0)"})
    return data, lay, (f"Mean nominal retail price (USD per litre) over the selected months for {describe(f)}. "
                       f"{len(df)} countries shown; unshaded countries are outside the dataset or the selection. "
                       "The map tiles load from Plotly's CDN unless assets are vendored (scripts/vendor_assets.py); "
                       "the ranking chart is the offline fallback.")


@register("region_bar", "Regional average price by fuel", "regional")
def region_bar(f, o):
    df = _need(A.region_averages(f))
    order = df.groupby("region")["avg_price"].mean().sort_values().index.tolist()
    data = []
    for i, fuel in enumerate([x for x in config.FUEL_TYPES if x in set(df["fuel_type"])]):
        s = df[df["fuel_type"] == fuel].set_index("region").reindex(order)
        data.append({"type": "bar", "orientation": "h", "name": fuel, "y": order, "x": s["avg_price"].round(4).tolist(),
                     "customdata": s[["n_countries"]].values.tolist(), "marker": {"color": FUEL_COLORS.get(fuel)},
                     "hovertemplate": "%{y}<br>" + fuel + ": $%{x:.2f}/L (%{customdata[0]} countries)<extra></extra>"})
    lay = _layout("Average retail price (USD/L, nominal)", None, barmode="group", margin={"l": 8})
    return data, lay, f"Average over all monthly observations in each region for {describe(f)}."


def _trend(f, o, by):
    df = _need(A.monthly_trend(f, by))
    cmap = _colors(by)
    data = []
    for i, (g, s) in enumerate(df.groupby(by, sort=True)):
        data.append({"type": "scatter", "mode": "lines", "name": g, "x": s["date"].astype(str).tolist(),
                     "y": s["avg_price"].round(4).tolist(), "line": {"color": _color(cmap, g, i), "width": 2},
                     "hovertemplate": "%{x|%b %Y}<br>" + str(g) + ": $%{y:.3f}/L<extra></extra>"})
    note = f"Monthly mean nominal retail price (USD/L) for {describe(f)}, split by {by.replace('_', ' ')}."
    if by != "fuel_type" and len(f.fuels) != 1:
        note += " Averages mix the selected fuels; filter to one fuel for a like-for-like comparison."
    return data, _layout(None, "USD per litre (nominal)", hovermode="x unified"), note


@register("trend_lines", "Monthly price trend, 2020-2026", "dashboard")
def trend_lines(f, o):
    return _trend(f, o, o.get("by", "fuel_type"))


@register("trend_region", "Monthly price trend by region", "regional")
def trend_region(f, o):
    return _trend(f, o, "region")


@register("fuel_comparison", "Petrol vs diesel vs LPG by year", "dashboard")
def fuel_comparison(f, o):
    df = _need(A.fuel_by_year(f))
    lab = _year_labels(sorted(df["year"].unique()), f)
    data = []
    for fuel in [x for x in config.FUEL_TYPES if x in set(df["fuel_type"])]:
        s = df[df["fuel_type"] == fuel].sort_values("year")
        data.append({"type": "bar", "name": fuel, "x": [lab[int(y)] for y in s["year"]],
                     "y": s["avg_price"].round(4).tolist(), "marker": {"color": FUEL_COLORS.get(fuel)},
                     "customdata": s[["effective_tax_burden_pct"]].values.tolist(),
                     "hovertemplate": "%{x}<br>" + fuel + ": $%{y:.3f}/L<br>Tax burden %{customdata[0]:.1f}%"
                                      "<extra></extra>"})
    return (data, _layout("Year", "USD per litre (nominal)", barmode="group", xaxis={"type": "category"}),
            f"Annual mean price by fuel for {describe(f)}. {GEO_NOTE}")


@register("country_ranking", "Country price ranking", "regional")
def country_ranking(f, o):
    n = int(o.get("n", 12))
    df = _need(A.country_averages(f)).sort_values("avg_price", ascending=False)
    hover = "%{y}<br>$%{x:.2f}/L<extra></extra>"
    if len(df) <= 2 * n:
        parts = [("All countries", df, "#0072B2")]
    else:
        parts = [(f"Highest {n}", df.head(n), "#D55E00"), (f"Lowest {n}", df.tail(n), "#009E73")]
    data = [{"type": "bar", "orientation": "h", "name": name, "y": s["country"].tolist(),
             "x": s["avg_price"].round(4).tolist(), "marker": {"color": c}, "hovertemplate": hover}
            for name, s, c in parts]
    ylab = {"autorange": "reversed", "type": "category", "automargin": True}
    return (data, _layout("Average retail price (USD/L, nominal)", None, yaxis=ylab, margin={"l": 8}),
            f"Countries ranked by mean price for {describe(f)} (1 = most expensive).")


@register("tax_rate_box", "Fuel tax rate comparison by region", "taxation")
def tax_rate_box(f, o):
    df = _need(A.country_averages(f))
    order = df.groupby("region")["avg_tax_rate_pct"].median().sort_values().index.tolist()
    data = [{"type": "box", "orientation": "h", "name": reg, "y": [reg] * len(s), "x": s["avg_tax_rate_pct"].round(2).tolist(),
             "boxpoints": "all", "jitter": 0.5, "pointpos": 0, "text": s["country"].tolist(), "showlegend": False,
             "marker": {"color": REGION_COLORS.get(reg, FALLBACK[0]), "size": 5},
             "line": {"color": REGION_COLORS.get(reg, FALLBACK[0])},
             "hovertemplate": "%{text}<br>%{x:.1f}% of pre-tax price<extra>" + reg + "</extra>"}
            for reg in order for s in [df[df["region"] == reg]]]
    return (data, _layout("Average tax rate (% of pre-tax price)", None, margin={"l": 8}, yaxis={"type": "category"}),
            f"Distribution of country mean tax rates within each region for {describe(f)}. "
            "Tax rate = tax / (retail price - tax). Box = interquartile range; dots = countries.")


@register("price_vs_tax", "Retail price vs tax burden", "taxation")
def price_vs_tax(f, o):
    df = _need(A.country_averages(f))
    traces, lay, r = _scatter(df, "effective_tax_burden_pct", "avg_price", "region", REGION_COLORS,
                              "Tax burden (% of retail price)", "Avg price (USD/L)",
                              hover_x="%{x:.1f}%", hover_y="$%{y:.2f}")
    return traces, lay, _r_note(r, len(df), "")


@register("subsidy_vs_price", "Subsidy vs retail price", "taxation")
def subsidy_vs_price(f, o):
    df = _need(A.country_averages(f))
    traces, lay, r = _scatter(df, "subsidy_to_price_pct", "avg_price", "income_group", INCOME_COLORS,
                              "Subsidy (% of retail price)", "Avg price (USD/L)", order=config.INCOME_ORDER,
                              hover_x="%{x:.1f}%", hover_y="$%{y:.2f}")
    return traces, lay, _r_note(r, len(df), "") + " Colour = income group."


@register("region_tax_subsidy", "Tax burden and subsidy ratio by region", "taxation")
def region_tax_subsidy(f, o):
    df = _need(A.aggregate(f, ["region"], ["effective_tax_burden_pct", "subsidy_to_price_pct"]))
    df = df.sort_values("effective_tax_burden_pct")
    data = [{"type": "bar", "orientation": "h", "name": "Tax burden (% of price)", "y": df["region"].tolist(),
             "x": df["effective_tax_burden_pct"].round(2).tolist(), "marker": {"color": "#0072B2"},
             "hovertemplate": "%{y}<br>Tax burden %{x:.1f}% of price<extra></extra>"},
            {"type": "bar", "orientation": "h", "name": "Subsidy (% of price)", "y": df["region"].tolist(),
             "x": df["subsidy_to_price_pct"].round(2).tolist(), "marker": {"color": "#D55E00"},
             "hovertemplate": "%{y}<br>Subsidy %{x:.1f}% of price<extra></extra>"}]
    return (data, _layout("% of retail price", None, barmode="group", margin={"l": 8}),
            f"Price-weighted ratios (sum of tax or subsidy / sum of price) for {describe(f)}.")


@register("income_affordability", "Affordability by income group", "affordability")
def income_affordability(f, o):
    df = _need(A.income_affordability(f))
    data = []
    for fuel in [x for x in config.FUEL_TYPES if x in set(df["fuel_type"])]:
        s = df[df["fuel_type"] == fuel]
        data.append({"type": "bar", "name": fuel, "x": s["income_group"].tolist(),
                     "y": s["avg_affordability_pct"].round(3).tolist(), "marker": {"color": FUEL_COLORS.get(fuel)},
                     "customdata": s[["n_countries", "avg_gdp_per_capita"]].values.tolist(),
                     "hovertemplate": ("%{x}<br>" + fuel + ": %{y:.1f}% of daily income per litre<br>"
                                       "%{customdata[0]} countries, GDP pc $%{customdata[1]:,.0f}<extra></extra>")})
    lay = _layout("Income group (illustrative GDP-per-capita bands)", "Price per litre as % of daily GDP per capita",
                  barmode="group", xaxis={"type": "category", "categoryorder": "array",
                                          "categoryarray": config.INCOME_ORDER})
    return data, lay, ("Affordability = price per litre / (GDP per capita / 365) x 100. Lower = more affordable. "
                       f"Income groups use illustrative thresholds, not official World Bank cut-offs. {describe(f)}.")


@register("affordability_gdp", "Income level vs affordability", "affordability")
def affordability_gdp(f, o):
    df = _need(A.country_averages(f))
    traces, lay, r = _scatter(df, "avg_gdp_per_capita", "avg_affordability_pct", "region", REGION_COLORS,
                              "GDP per capita (USD, log scale)", "Affordability (% daily income per L, log scale)",
                              logx=True, logy=True, hover_x="$%{x:,.0f}", hover_y="%{y:.1f}%")
    return traces, lay, _r_note(r, len(df), " (on log-log axes)") + " Lower = more affordable."


@register("correlation", "Correlation matrix (country level)", "affordability")
def correlation(f, o):
    c = A.correlations(f)
    if not c["labels"]:
        raise NoData(f"Need at least 3 countries for a correlation matrix (selection has {c['n_countries']}).")
    z = c["matrix"]
    data = [{"type": "heatmap", "x": c["labels"], "y": c["labels"], "z": z, "zmin": -1, "zmax": 1,
             "colorscale": "RdBu", "text": [[f"{v:.2f}" for v in row] for row in z], "texttemplate": "%{text}",
             "colorbar": {"title": {"text": "Pearson r"}, "thickness": 12},
             "hovertemplate": "%{y} vs %{x}<br>r = %{z:.2f}<extra></extra>"}]
    lay = _layout(None, None, margin={"l": 150, "b": 110}, xaxis={"tickangle": -35, "automargin": True},
                  yaxis={"autorange": "reversed", "automargin": True})
    return data, lay, (f"Pearson correlation across {c['n_countries']} countries (country-level means) for "
                       f"{describe(f)}. Association, not causation; the country-level view ignores time effects.")


@register("volatility", "Most volatile prices", "trends")
def volatility(f, o):
    n = int(o.get("n", 15))
    df = _need(A.volatility(f), "Not enough monthly observations to measure volatility.")
    df = df.sort_values("cv_pct", ascending=False).head(n)
    labels = (df["country"] + " (" + df["fuel_type"] + ")").tolist()
    data = [{"type": "bar", "orientation": "h", "y": labels, "x": df["cv_pct"].round(2).tolist(),
             "marker": {"color": [FUEL_COLORS.get(x, FALLBACK[0]) for x in df["fuel_type"]]},
             "customdata": df[["mom_vol_pct", "avg_price"]].values.tolist(), "showlegend": False,
             "hovertemplate": ("%{y}<br>CV %{x:.1f}%<br>Month-over-month std %{customdata[0]:.1f}%<br>"
                               "Mean price $%{customdata[1]:.2f}/L<extra></extra>")}]
    lay = _layout("Coefficient of variation of monthly price (%)", None, margin={"l": 8},
                  yaxis={"autorange": "reversed", "type": "category"})
    return data, lay, (f"Top {len(df)} country-fuel series by CV (std / mean of the monthly price level) for "
                       f"{describe(f)}. Bar colour = fuel (blue petrol, orange diesel, green LPG).")


@register("yoy_change", "Year-over-year price change", "trends")
def yoy_change(f, o):
    df = A.yoy(f, "fuel_type")
    df = _need(df.dropna(subset=["yoy_change_pct"]), "Year-over-year change needs at least two calendar years.")
    lab = _year_labels(sorted(df["year"].unique()), f)
    data = []
    for fuel in [x for x in config.FUEL_TYPES if x in set(df["fuel_type"])]:
        s = df[df["fuel_type"] == fuel].sort_values("year")
        data.append({"type": "bar", "name": fuel, "x": [lab[int(y)] for y in s["year"]],
                     "y": s["yoy_change_pct"].round(2).tolist(), "marker": {"color": FUEL_COLORS.get(fuel)},
                     "customdata": s[["yoy_change_usd"]].values.tolist(),
                     "hovertemplate": "%{x}<br>" + fuel + ": %{y:+.1f}% (%{customdata[0]:+.3f} USD/L)<extra></extra>"})
    return (data, _layout("Year", "Change in annual mean price (%)", barmode="group", xaxis={"type": "category"}),
            f"Change of the annual mean price versus the previous year for {describe(f)}. {GEO_NOTE}")


@register("forecast", "12-month price forecast (demonstration)", "trends")
def forecast(f, o):
    horizon = int(o.get("horizon", 12))
    s = A.monthly_series(f)
    if len(s) < forecasting.MIN_POINTS:
        raise NoData(f"Forecasting needs at least {forecasting.MIN_POINTS} monthly points; the selection has {len(s)}. "
                     "Widen the date range.")
    r = forecasting.forecast_series(s, horizon=horizon)
    h, fc = r["history"], r["forecast"]
    dstr = lambda ser: pd.to_datetime(ser).dt.strftime("%Y-%m-%d").tolist()  # noqa: E731
    data = [
        {"type": "scatter", "mode": "lines", "name": "Actual", "x": dstr(h["date"]), "y": h["actual"].round(4).tolist(),
         "line": {"color": "#0072B2", "width": 2}, "hovertemplate": "%{x|%b %Y}<br>Actual $%{y:.3f}/L<extra></extra>"},
        {"type": "scatter", "mode": "lines", "name": "95% upper", "x": dstr(fc["date"]), "y": fc["upper"].round(4).tolist(),
         "line": {"width": 0}, "showlegend": False, "hoverinfo": "skip"},
        {"type": "scatter", "mode": "lines", "name": "Approx. 95% interval", "x": dstr(fc["date"]),
         "y": fc["lower"].round(4).tolist(), "line": {"width": 0}, "fill": "tonexty",
         "fillcolor": "rgba(213,94,0,0.18)", "hoverinfo": "skip"},
        {"type": "scatter", "mode": "lines", "name": "Naive baseline", "x": dstr(fc["date"]),
         "y": fc["naive"].round(4).tolist(), "line": {"color": "#6b7280", "dash": "dot", "width": 1.5},
         "hovertemplate": "%{x|%b %Y}<br>Naive $%{y:.3f}/L<extra></extra>"},
        {"type": "scatter", "mode": "lines", "name": "Forecast (damped Holt)", "x": dstr(fc["date"]),
         "y": fc["forecast"].round(4).tolist(), "line": {"color": "#D55E00", "dash": "dash", "width": 2.2},
         "hovertemplate": "%{x|%b %Y}<br>Forecast $%{y:.3f}/L<extra></extra>"},
    ]
    m = r["metrics"]
    note = (f"{r['method']}. Selection: {describe(f)}. Last {m['holdout_months']}-month holdout backtest: "
            f"Holt MAPE {m['holt']['mape_pct']:.2f}% vs naive {m['naive']['mape_pct']:.2f}%. Interval: {r['interval']}.")
    if len(f.fuels) != 1:
        note += " The series averages several fuels; select one fuel for a cleaner forecast."
    if is_synthetic():
        note += " Based on SYNTHETIC data: a method demonstration, not a market prediction."
    return data, _layout(None, "USD per litre (nominal)", hovermode="x unified"), note


# ---------------------------------------------------------------- public API
def parse_opts(args) -> dict:
    """Validate chart options (separate from data filters)."""
    out = {}
    for key, lo, hi in (("n", 3, 30), ("horizon", 1, 36)):
        if args.get(key):
            try:
                v = int(args.get(key))
            except ValueError:
                raise A.FilterError(f"{key} must be an integer") from None
            if not lo <= v <= hi:
                raise A.FilterError(f"{key} must be between {lo} and {hi}")
            out[key] = v
    if args.get("by"):
        if args["by"] not in BY_OPTIONS:
            raise A.FilterError(f"by must be one of {sorted(BY_OPTIONS)}")
        out["by"] = args["by"]
    return out


def build(name: str, f: A.Filters, opts: dict | None = None) -> dict:
    spec = REGISTRY[name]  # KeyError -> 404 in the API
    base = {"name": name, "title": spec.title, "page": spec.page, "synthetic": is_synthetic()}
    try:
        data, layout, note = spec.fn(f, opts or {})
    except NoData as e:
        return jsonable({**base, "empty": True, "message": str(e), "figure": None, "note": ""})
    return jsonable({**base, "empty": False, "message": "", "figure": {"data": data, "layout": layout}, "note": note})


# ---------------------------------------------------------------- tables
TABLE_BY = {"region", "fuel_type", "income_group"}


def table(name: str, f: A.Filters, args) -> dict:
    if name == "price_stats":
        by = args.get("by", "region")
        if by not in TABLE_BY:
            raise A.FilterError(f"by must be one of {sorted(TABLE_BY)}")
        df = A.price_statistics(f, by)
        cols = [(by, by.replace("_", " ").title(), "text"), ("mean", "Mean", "usd"), ("median", "Median", "usd"),
                ("max", "Max", "usd"), ("std", "Std dev", "usd"), ("n", "Observations", "int")]
        df = df.sort_values("mean", ascending=False)
    elif name == "country_table":
        df = A.country_averages(f)
        cols = [("country", "Country", "text"), ("region", "Region", "text"), ("income_group", "Income", "text"),
                ("avg_price", "Avg price (USD/L)", "usd"), ("effective_tax_burden_pct", "Tax burden %", "pct"),
                ("subsidy_to_price_pct", "Subsidy %", "pct"), ("avg_affordability_pct", "Affordability %", "pct"),
                ("avg_gdp_per_capita", "GDP pc (USD)", "int")]
    else:
        raise KeyError(name)
    keys = [c[0] for c in cols]
    return jsonable({"name": name, "empty": df.empty, "columns": [{"key": k, "label": l, "fmt": t} for k, l, t in cols],
                     "rows": df[keys].to_dict("records") if not df.empty else []})


TABLES = ("price_stats", "country_table")
