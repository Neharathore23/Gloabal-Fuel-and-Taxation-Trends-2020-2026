"""Reproducible SYNTHETIC data generator.

Everything produced here is simulated. Magnitudes are stylised and must NOT be presented as real
observations. Grain: one row per country x month x fuel type. Prices are nominal USD per litre
(LPG expressed per litre of liquid equivalent). No inflation adjustment is applied.

`build_clean()` returns the defect-free "ground truth"; `inject_defects()` then adds a small,
documented number of realistic data problems so the validation/preprocessing stages have real work.
"""
import json

import numpy as np
import pandas as pd

import config

# iso3|country|region key|GDP per capita 2020 (illustrative USD)|local currency|subsidy level (0-1)
_COUNTRIES = """
CHN|China|EAP|10500|CNY|0
JPN|Japan|EAP|40000|JPY|0
KOR|South Korea|EAP|31700|KRW|0
AUS|Australia|EAP|51800|AUD|0
NZL|New Zealand|EAP|41100|NZD|0
THA|Thailand|EAP|7200|THB|0.05
VNM|Vietnam|EAP|3500|VND|0
IDN|Indonesia|EAP|3900|IDR|0.25
MYS|Malaysia|EAP|10400|MYR|0.3
PHL|Philippines|EAP|3300|PHP|0
SGP|Singapore|EAP|59800|SGD|0
MNG|Mongolia|EAP|4000|MNT|0
KHM|Cambodia|EAP|1600|KHR|0
LAO|Laos|EAP|2600|LAK|0
DEU|Germany|ECA|46200|EUR|0
FRA|France|ECA|39000|EUR|0
GBR|United Kingdom|ECA|40300|GBP|0
ITA|Italy|ECA|31700|EUR|0
ESP|Spain|ECA|27100|EUR|0
NLD|Netherlands|ECA|52400|EUR|0
BEL|Belgium|ECA|46100|EUR|0
SWE|Sweden|ECA|52900|SEK|0
NOR|Norway|ECA|67300|NOK|0
POL|Poland|ECA|15700|PLN|0
CZE|Czechia|ECA|22900|CZK|0
HUN|Hungary|ECA|15900|HUF|0
ROU|Romania|ECA|12900|RON|0
GRC|Greece|ECA|17700|EUR|0
PRT|Portugal|ECA|22400|EUR|0
TUR|Turkiye|ECA|8500|TRY|0
RUS|Russia|ECA|10100|RUB|0.1
UKR|Ukraine|ECA|3700|UAH|0
KAZ|Kazakhstan|ECA|9100|KZT|0.2
UZB|Uzbekistan|ECA|1700|UZS|0.2
CHE|Switzerland|ECA|86600|CHF|0
AUT|Austria|ECA|48800|EUR|0
BRA|Brazil|LAC|6800|BRL|0
MEX|Mexico|LAC|8400|MXN|0.08
ARG|Argentina|LAC|8600|ARS|0.15
COL|Colombia|LAC|5300|COP|0
CHL|Chile|LAC|13100|CLP|0
PER|Peru|LAC|6100|PEN|0
ECU|Ecuador|LAC|5600|USD|0.2
VEN|Venezuela|LAC|1700|VES|0.75
BOL|Bolivia|LAC|3100|BOB|0.45
PRY|Paraguay|LAC|5400|PYG|0
URY|Uruguay|LAC|15700|UYU|0
DOM|Dominican Republic|LAC|7200|DOP|0
GTM|Guatemala|LAC|4600|GTQ|0
CRI|Costa Rica|LAC|12100|CRC|0
SAU|Saudi Arabia|MENA|20400|SAR|0.4
ARE|United Arab Emirates|MENA|36300|AED|0.15
IRN|Iran|MENA|2800|IRR|0.7
IRQ|Iraq|MENA|4100|IQD|0.45
EGY|Egypt|MENA|3500|EGP|0.3
DZA|Algeria|MENA|3300|DZD|0.5
MAR|Morocco|MENA|3200|MAD|0
TUN|Tunisia|MENA|3300|TND|0.25
JOR|Jordan|MENA|4100|JOD|0.1
KWT|Kuwait|MENA|22400|KWD|0.35
QAT|Qatar|MENA|50000|QAR|0.3
OMN|Oman|MENA|14700|OMR|0.3
USA|United States|NAM|63500|USD|0
CAN|Canada|NAM|43300|CAD|0
IND|India|SAS|1900|INR|0.05
PAK|Pakistan|SAS|1300|PKR|0.1
BGD|Bangladesh|SAS|2000|BDT|0.15
LKA|Sri Lanka|SAS|3700|LKR|0
NPL|Nepal|SAS|1200|NPR|0
BTN|Bhutan|SAS|3000|BTN|0
MDV|Maldives|SAS|10300|MVR|0
AFG|Afghanistan|SAS|500|AFN|0
NGA|Nigeria|SSA|2100|NGN|0.35
ZAF|South Africa|SSA|5100|ZAR|0
KEN|Kenya|SSA|1900|KES|0
ETH|Ethiopia|SSA|900|ETB|0.25
GHA|Ghana|SSA|2300|GHS|0
TZA|Tanzania|SSA|1100|TZS|0
UGA|Uganda|SSA|800|UGX|0
AGO|Angola|SSA|1500|AOA|0.3
SEN|Senegal|SSA|1600|XOF|0
CIV|Cote d'Ivoire|SSA|2300|XOF|0
ZMB|Zambia|SSA|1000|ZMW|0.1
MOZ|Mozambique|SSA|500|MZN|0
"""

# Fuel parameters: base pre-tax price (USD/l), tax multiplier, subsidy multiplier
_FUEL = {
    "Petrol": dict(base=0.62, tax=1.0, sub=0.9),
    "Diesel": dict(base=0.64, tax=0.9, sub=1.1),
    "LPG": dict(base=0.50, tax=0.35, sub=1.2),
}
_REGION_TAX = {"ECA": 105, "NAM": 25, "EAP": 45, "LAC": 38, "MENA": 12, "SAS": 55, "SSA": 30}  # % of net pre-tax
_REGION_COST = {"SSA": 1.15, "SAS": 1.0, "EAP": 1.0, "LAC": 1.05, "ECA": 1.0, "MENA": 0.9, "NAM": 0.9}
_LOW_TAX = {"RUS", "KAZ", "UKR", "UZB"}
# Stylised global crude-cost index (1.0 = Jan 2020). Loosely mimics a 2020 slump, 2022 spike, gradual easing.
_OIL = {"2020-01": 1.00, "2020-04": 0.55, "2020-12": 0.78, "2021-12": 1.22, "2022-06": 1.68,
        "2022-12": 1.32, "2023-12": 1.10, "2024-12": 1.08, "2025-12": 1.00, "2026-10": 1.06}

RAW_COLUMNS = ["country_code", "country", "region", "income_group", "date", "fuel_type", "currency_local",
               "price_usd_per_litre", "tax_usd_per_litre", "tax_rate_pct", "subsidy_usd_per_litre",
               "gdp_per_capita_usd", "data_source"]

ASSUMPTIONS = [
    "All values are simulated; no real-world observation is represented.",
    "Grain: one row per country x month x fuel type; prices are nominal USD per litre (LPG per litre-equivalent).",
    "Prices are generated directly in USD, so no currency conversion is involved; currency_local is metadata only.",
    "retail price = (market pre-tax price - subsidy) + tax; tax_rate_pct = tax / (retail - tax) * 100.",
    "A stylised global cost index drives prices; subsidised countries pass through only ~50% of changes.",
    "Subsidy levels, tax levels and GDP per capita are illustrative country settings, not official statistics.",
    "Income group is fixed per country from 2020 GDP per capita using illustrative thresholds.",
]


def country_table() -> pd.DataFrame:
    rows = [line.split("|") for line in _COUNTRIES.strip().splitlines()]
    c = pd.DataFrame(rows, columns=["country_code", "country", "region_key", "gdp_pc_2020",
                                    "currency_local", "subsidy_level"])
    c["gdp_pc_2020"] = c["gdp_pc_2020"].astype(float)
    c["subsidy_level"] = c["subsidy_level"].astype(float)
    c["region"] = c["region_key"].map(config.REGIONS)
    return c


def oil_index(dates: pd.DatetimeIndex) -> np.ndarray:
    origin = pd.Timestamp("2020-01-01")
    xs = [(pd.Timestamp(k + "-01") - origin).days for k in _OIL]
    return np.interp((dates - origin).days, xs, list(_OIL.values()))


def build_clean(seed: int | None = None) -> pd.DataFrame:
    """Defect-free synthetic panel (the ground truth)."""
    seed = config.SEED if seed is None else seed
    rng = np.random.default_rng(seed)
    c = country_table()
    n = len(c)
    c["cost"] = c["region_key"].map(_REGION_COST) * rng.lognormal(0, 0.08, n)
    income_factor = np.clip(0.6 + 0.4 * c["gdp_pc_2020"] / 40_000, 0.6, 1.3)
    tax_mult = np.where(c["subsidy_level"] >= 0.3, 0.25, np.where(c["country_code"].isin(_LOW_TAX), 0.5, 1.0))
    c["tax_base"] = c["region_key"].map(_REGION_TAX) * income_factor * tax_mult * rng.lognormal(0, 0.25, n)
    c["gdp_growth"] = rng.normal(0.025, 0.01, n)
    c["beta"] = np.where(c["subsidy_level"] > 0, 0.5, 1.0)
    c["income_group"] = config.income_group(c["gdp_pc_2020"])

    dates = pd.date_range(config.START_DATE, config.END_DATE, freq="MS")
    t = pd.DataFrame({"date": dates, "oil": oil_index(dates)})
    f = pd.DataFrame({"fuel_type": list(_FUEL)})
    df = c.merge(t, how="cross").merge(f, how="cross")

    for key, col in (("base", "f_base"), ("tax", "f_tax"), ("sub", "f_sub")):
        df[col] = df["fuel_type"].map({k: v[key] for k, v in _FUEL.items()})
    m = len(df)
    market = df["f_base"] * df["cost"] * (1 + df["beta"] * (df["oil"] - 1)) * rng.lognormal(0, 0.012, m)
    rate = np.clip(df["subsidy_level"] * df["f_sub"] * (0.75 + 0.25 * df["oil"]) * rng.lognormal(0, 0.05, m), 0, 0.8)
    subsidy = market * rate
    net = market - subsidy
    tax_rate = df["tax_base"] * df["f_tax"] * rng.lognormal(0, 0.02, m)
    tax = net * tax_rate / 100
    df["price_usd_per_litre"] = (net + tax).round(4)
    df["tax_usd_per_litre"] = tax.round(4)
    df["tax_rate_pct"] = tax_rate.round(2)
    df["subsidy_usd_per_litre"] = subsidy.round(4)

    years = pd.DataFrame({"year": range(2020, 2027)})
    g = c[["country_code", "gdp_pc_2020", "gdp_growth"]].merge(years, how="cross")
    g["gdp_per_capita_usd"] = (g["gdp_pc_2020"] * (1 + g["gdp_growth"]) ** (g["year"] - 2020)
                               * (1 + rng.normal(0, 0.01, len(g)))).round(0)
    df["year"] = df["date"].dt.year
    df = df.merge(g[["country_code", "year", "gdp_per_capita_usd"]], on=["country_code", "year"])
    df["data_source"] = f"SYNTHETIC (simulated, seed={seed}) - not real-world data"
    return df.sort_values(["country_code", "fuel_type", "date"]).reset_index(drop=True)[RAW_COLUMNS]


_FUEL_VARIANTS = {"Petrol": ["gasoline", "PETROL ", "petrol"], "Diesel": [" diesel", "DIESEL", "Gasoil"],
                  "LPG": ["lpg", "Autogas", "LPG "]}
_DEFECT_COUNTS = {"missing_price": 15, "missing_tax": 30, "missing_subsidy": 40, "missing_gdp": 20,
                  "negative_price": 6, "invalid_tax_rate": 6, "extreme_price": 6}


def inject_defects(clean: pd.DataFrame, seed: int | None = None) -> tuple[pd.DataFrame, dict]:
    """Return a raw-looking frame with documented defects, plus a log of what was injected."""
    seed = config.SEED if seed is None else seed
    rng = np.random.default_rng(seed + 1)
    raw = clean.copy()
    raw["date"] = raw["date"].dt.strftime("%Y-%m-%d")
    n = len(raw)
    order = rng.permutation(n)
    pos, log = 0, {}
    for name, k in _DEFECT_COUNTS.items():
        idx = order[pos:pos + k]
        pos += k
        col = {"missing_price": "price_usd_per_litre", "missing_tax": "tax_usd_per_litre",
               "missing_subsidy": "subsidy_usd_per_litre", "missing_gdp": "gdp_per_capita_usd",
               "negative_price": "price_usd_per_litre", "invalid_tax_rate": "tax_rate_pct",
               "extreme_price": "price_usd_per_litre"}[name]
        j = raw.columns.get_loc(col)
        if name.startswith("missing"):
            raw.iloc[idx, j] = np.nan
        elif name == "negative_price":
            raw.iloc[idx, j] = -raw.iloc[idx, j].abs()
        elif name == "invalid_tax_rate":
            raw.iloc[idx, j] = rng.choice([900.0, -5.0], size=k)
        else:
            raw.iloc[idx, j] = raw.iloc[idx, j] * 12
        log[name] = int(k)

    m = rng.random(n) < 0.01
    raw.loc[m, "country"] = raw.loc[m, "country"].str.upper()
    log["country_name_case_variants"] = int(m.sum())
    m = rng.random(n) < 0.01
    raw.loc[m, "country"] = " " + raw.loc[m, "country"] + " "
    log["country_name_whitespace_variants"] = int(m.sum())
    m = rng.random(n) < 0.03
    raw.loc[m, "fuel_type"] = [rng.choice(_FUEL_VARIANTS[f]) for f in raw.loc[m, "fuel_type"]]
    log["fuel_type_label_variants"] = int(m.sum())
    m = rng.random(n) < 0.01
    raw.loc[m, "region"] = raw.loc[m, "region"].str.replace("&", "and", regex=False).str.upper()
    log["region_label_variants"] = int(m.sum())
    m = rng.random(n) < 0.005
    raw.loc[m, "date"] = raw.loc[m, "date"].str.replace("-", "/", regex=False)
    log["date_format_variants"] = int(m.sum())

    dup_idx = rng.choice(n, size=60, replace=False)
    raw = pd.concat([raw, raw.iloc[dup_idx]]).sort_index(kind="stable").reset_index(drop=True)
    log["exact_duplicate_rows_added"] = 60
    log["rows_before_duplicates"] = int(n)
    log["rows_written"] = int(len(raw))
    return raw, log


def generate_raw(path=None, seed: int | None = None) -> dict:
    """Write the synthetic raw CSV and its provenance file; return the provenance dict."""
    seed = config.SEED if seed is None else seed
    path = path or config.RAW_FILE
    clean = build_clean(seed)
    raw, log = inject_defects(clean, seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw.to_csv(path, index=False)
    prov = {"synthetic": True, "seed": seed, "file": path.name, "countries": int(clean["country_code"].nunique()),
            "regions": int(clean["region"].nunique()), "fuel_types": int(clean["fuel_type"].nunique()),
            "periods": int(clean["date"].nunique()), "defect_free_rows": int(len(clean)),
            "injected_defects": log, "assumptions": ASSUMPTIONS}
    config.PROVENANCE_FILE.write_text(json.dumps(prov, indent=2), encoding="utf-8")
    return prov


if __name__ == "__main__":
    print(json.dumps(generate_raw(), indent=2))
