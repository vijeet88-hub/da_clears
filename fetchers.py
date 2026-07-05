"""Per-ISO DA LMP fetch + on-peak parsing.

Mirrors the parsing logic in vijeet88-hub/isone-lmp-alert's four alert
scripts (isone_da_lmp.py, pjm_da_lmp.py, nyiso_da_lmp.py, ercot_da_lmp.py),
trimmed down to just fetch + parse (no email sending). Each fetch_* function
returns a dict:

  {
    "rows": [{"he": int, "lmp": float, "congestion": float|None}, ...],
    "expected_hours": int,
    "he_start": int,
    "he_end": int,
  }

congestion is None for ERCOT (its DAM hub SPP has no component breakdown).
"""

import csv
import io
from datetime import datetime

import requests

# ── on-peak hour-ending ranges ───────────────────────────────────────────────
# ISONE/PJM/NYISO: HE 8-23 Eastern Prevailing Time (ICE Eastern-ISO convention).
# ERCOT: HE 7-22 Central Prevailing Time (ICE/CME ERCOT Hub convention) --
# a genuinely different 16-hour block, not just a timezone shift.
EASTERN_HE_START, EASTERN_HE_END = 8, 23
ERCOT_HE_START, ERCOT_HE_END = 7, 22


def _expected(he_start, he_end):
    return he_end - he_start + 1


# ── ISONE ────────────────────────────────────────────────────────────────────
ISONE_LOCATION_ID = 4000
ISONE_BASE_URL = "https://webservices.iso-ne.com/api/v1.1"


def fetch_isone(date_str, user, pw):
    """date_str: YYYYMMDD"""
    url = f"{ISONE_BASE_URL}/hourlylmp/da/final/day/{date_str}/location/{ISONE_LOCATION_ID}.json"
    resp = requests.get(url, auth=(user, pw), headers={"Accept": "application/json"}, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    raw = payload.get("HourlyLmps", {}).get("HourlyLmp", [])
    rows = []
    for entry in raw:
        try:
            begin_dt = datetime.fromisoformat(entry["BeginDate"])
            he = begin_dt.hour + 1
            if EASTERN_HE_START <= he <= EASTERN_HE_END:
                rows.append({
                    "he": he,
                    "lmp": round(float(entry["LmpTotal"]), 2),
                    "congestion": round(float(entry.get("CongestionComponent", 0)), 2),
                })
        except (KeyError, ValueError):
            continue

    return {
        "rows": sorted(rows, key=lambda r: r["he"]),
        "expected_hours": _expected(EASTERN_HE_START, EASTERN_HE_END),
        "he_start": EASTERN_HE_START,
        "he_end": EASTERN_HE_END,
    }


# ── PJM ──────────────────────────────────────────────────────────────────────
PJM_PNODE_ID = 51288
PJM_BASE_URL = "https://api.pjm.com/api/v1/da_hrl_lmps"


def fetch_pjm(date_str, api_key):
    """date_str: YYYY-MM-DD"""
    params = {
        "pnode_id": PJM_PNODE_ID,
        "datetime_beginning_ept": f"{date_str} 00:00to{date_str} 23:00",
        "rowCount": 100,
        "startRow": 1,
    }
    resp = requests.get(
        PJM_BASE_URL,
        headers={"Ocp-Apim-Subscription-Key": api_key, "Cache-Control": "no-cache"},
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()

    items = payload.get("items", [])
    rows = []
    for entry in items:
        try:
            begin_str = entry["datetime_beginning_ept"]
            hour_beginning = datetime.fromisoformat(begin_str).hour
            he = hour_beginning + 1
            if EASTERN_HE_START <= he <= EASTERN_HE_END:
                rows.append({
                    "he": he,
                    "lmp": round(float(entry["total_lmp_da"]), 2),
                    "congestion": round(float(entry.get("congestion_price_da", 0)), 2),
                })
        except (KeyError, ValueError):
            continue

    return {
        "rows": sorted(rows, key=lambda r: r["he"]),
        "expected_hours": _expected(EASTERN_HE_START, EASTERN_HE_END),
        "he_start": EASTERN_HE_START,
        "he_end": EASTERN_HE_END,
    }


# ── NYISO ────────────────────────────────────────────────────────────────────
NYISO_ZONE_NAME = "HUD VL"   # Zone G, PTID 61758 -- exact "Name" field value (note the space)
NYISO_BASE_URL = "https://mis.nyiso.com/public/csv/damlbmp"


def fetch_nyiso(date_str):
    """date_str: YYYYMMDD. No auth required -- public MIS CSV."""
    url = f"{NYISO_BASE_URL}/{date_str}damlbmp_zone.csv"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    rows = []
    reader = csv.DictReader(io.StringIO(resp.text))
    for entry in reader:
        if entry.get("Name") != NYISO_ZONE_NAME:
            continue
        try:
            begin_dt = datetime.strptime(entry["Time Stamp"], "%m/%d/%Y %H:%M")
            he = begin_dt.hour + 1
            if EASTERN_HE_START <= he <= EASTERN_HE_END:
                lmp = float(entry["LBMP ($/MWHr)"])
                cong = float(entry["Marginal Cost Congestion ($/MWHr)"])
                rows.append({"he": he, "lmp": round(lmp, 2), "congestion": round(cong, 2)})
        except (KeyError, ValueError):
            continue

    return {
        "rows": sorted(rows, key=lambda r: r["he"]),
        "expected_hours": _expected(EASTERN_HE_START, EASTERN_HE_END),
        "he_start": EASTERN_HE_START,
        "he_end": EASTERN_HE_END,
    }


# ── ERCOT (via Yes Energy DataSignals) ──────────────────────────────────────
ERCOT_OBJECT_NAME = "HB_NORTH"
YE_BASE_URL = "https://services.yesenergy.com/PS/rest/timeseries/multiple.csv"


def fetch_ercot(date_str_mmddyyyy, ye_user, ye_pass):
    """date_str_mmddyyyy: MM/DD/YYYY. ERCOT hub SPPs have no energy/congestion/loss
    breakdown -- congestion is always None."""
    params = {
        "agglevel": "HOUR",
        "startdate": date_str_mmddyyyy,
        "enddate": date_str_mmddyyyy,
        "items": f"DALMP:{ERCOT_OBJECT_NAME}",
    }
    resp = requests.get(YE_BASE_URL, params=params, auth=(ye_user, ye_pass), timeout=30)
    resp.raise_for_status()

    rows = []
    reader = csv.DictReader(io.StringIO(resp.text))
    lmp_col = f"{ERCOT_OBJECT_NAME} (DALMP)"
    for entry in reader:
        if "error" in entry:
            continue
        try:
            if entry.get("MARKETDAY") != date_str_mmddyyyy:
                continue
            he = int(entry["HOURENDING"])
            if ERCOT_HE_START <= he <= ERCOT_HE_END:
                rows.append({"he": he, "lmp": round(float(entry[lmp_col]), 2), "congestion": None})
        except (KeyError, ValueError):
            continue

    return {
        "rows": sorted(rows, key=lambda r: r["he"]),
        "expected_hours": _expected(ERCOT_HE_START, ERCOT_HE_END),
        "he_start": ERCOT_HE_START,
        "he_end": ERCOT_HE_END,
    }
