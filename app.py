"""On-Peak DA LMP Dashboard -- condensed live view companion to the
ISONE/PJM/NYISO/ERCOT email alerts (vijeet88-hub/isone-lmp-alert).

Shows one row per ISO: on-peak avg LMP, on-peak avg congestion (blank for
ERCOT, which has no component breakdown), and posting status. Auto-polls
every 60s until all four ISOs have posted their full on-peak hour set,
mirroring the email scripts' retry-until-complete behavior.
"""

from datetime import datetime, timedelta

import pandas as pd
import pytz
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from fetchers import fetch_ercot, fetch_isone, fetch_nyiso, fetch_pjm

st.set_page_config(page_title="DA LMP On-Peak Dashboard", layout="centered")

EASTERN = pytz.timezone("US/Eastern")
POLL_INTERVAL_MS = 60_000
CACHE_TTL_SECONDS = 50   # < poll interval so each auto-rerun fetches fresh data


def next_operating_day():
    tomorrow = datetime.now(EASTERN) + timedelta(days=1)
    return tomorrow


def summarize(result):
    rows = result["rows"]
    posted = len(rows) == result["expected_hours"]
    avg_lmp = round(sum(r["lmp"] for r in rows) / len(rows), 2) if rows else None
    congestions = [r["congestion"] for r in rows if r["congestion"] is not None]
    avg_cong = round(sum(congestions) / len(congestions), 2) if congestions else None
    return {
        "posted": posted,
        "hours": len(rows),
        "expected": result["expected_hours"],
        "avg_lmp": avg_lmp,
        "avg_cong": avg_cong,
        "has_cong": bool(congestions),
    }


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_isone(date_key, user, pw):
    return fetch_isone(date_key, user, pw)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_pjm(date_key, api_key):
    return fetch_pjm(date_key, api_key)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_nyiso(date_key):
    return fetch_nyiso(date_key)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_ercot(date_key, ye_user, ye_pass):
    return fetch_ercot(date_key, ye_user, ye_pass)


def safe_fetch(fn, label, *args):
    try:
        return summarize(fn(*args)), None
    except Exception as exc:  # noqa: BLE001 -- surface any error to the dashboard, not just a crash
        return None, f"{type(exc).__name__}: {exc}"


def fmt_money(val):
    return f"${val:.2f}" if val is not None else "—"


def main():
    st.title("DA LMP On-Peak Dashboard")

    tomorrow = next_operating_day()
    st.caption(f"Operating Day: {tomorrow.strftime('%B %d, %Y')}  ·  "
               f"Refreshed {datetime.now(EASTERN).strftime('%I:%M:%S %p ET')}")

    isone_user = st.secrets["ISONE_USERNAME"]
    isone_pw = st.secrets["ISONE_PASSWORD"]
    pjm_key = st.secrets["PJM_API_KEY"]
    ye_user = st.secrets["YE_USER"]
    ye_pass = st.secrets["YE_PASS"]

    isone_summary, isone_err = safe_fetch(
        get_isone, "ISONE", tomorrow.strftime("%Y%m%d"), isone_user, isone_pw)
    pjm_summary, pjm_err = safe_fetch(
        get_pjm, "PJM", tomorrow.strftime("%Y-%m-%d"), pjm_key)
    nyiso_summary, nyiso_err = safe_fetch(
        get_nyiso, "NYISO", tomorrow.strftime("%Y%m%d"))
    ercot_summary, ercot_err = safe_fetch(
        get_ercot, "ERCOT", tomorrow.strftime("%m/%d/%Y"), ye_user, ye_pass)

    entries = [
        ("ISONE", "Internal Hub", isone_summary, isone_err),
        ("PJM", "Western Hub", pjm_summary, pjm_err),
        ("NYISO", "Zone G", nyiso_summary, nyiso_err),
        ("ERCOT", "Hub North", ercot_summary, ercot_err),
    ]

    table_rows = []
    all_posted = True
    for iso, loc, summary, err in entries:
        if err is not None:
            all_posted = False
            table_rows.append({
                "ISO": iso, "Location": loc,
                "On-Peak Avg LMP": "error", "On-Peak Avg Cong": "error",
                "Status": err,
            })
            continue

        if not summary["posted"]:
            all_posted = False
        status = (f"Posted ({summary['hours']}/{summary['expected']})"
                   if summary["posted"]
                   else f"Pending ({summary['hours']}/{summary['expected']})")
        table_rows.append({
            "ISO": iso,
            "Location": loc,
            "On-Peak Avg LMP": fmt_money(summary["avg_lmp"]),
            "On-Peak Avg Cong": fmt_money(summary["avg_cong"]) if summary["has_cong"] else "n/a",
            "Status": status,
        })

    df = pd.DataFrame(table_rows).set_index("ISO")
    st.dataframe(df, use_container_width=True)

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Refresh now"):
            st.cache_data.clear()
            st.rerun()
    with col2:
        if all_posted:
            st.success("All 4 ISOs posted -- auto-refresh stopped.")
        else:
            st.info(f"Auto-refreshing every {POLL_INTERVAL_MS // 1000}s until all 4 ISOs post...")

    if not all_posted:
        st_autorefresh(interval=POLL_INTERVAL_MS, key="poller")


if __name__ == "__main__":
    main()
