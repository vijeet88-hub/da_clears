"""On-Peak DA LMP Dashboard -- condensed live view companion to the
ISONE/PJM/NYISO/ERCOT email alerts (vijeet88-hub/isone-lmp-alert).

Shows one card per ISO: on-peak avg LMP, on-peak avg congestion (blank for
ERCOT, which has no component breakdown), posting status, and a small
sparkline of the on-peak hourly shape. Auto-polls every 60s until all four
ISOs have posted their full on-peak hour set, mirroring the email scripts'
retry-until-complete behavior. Entirely cloud-side -- every card is a live
HTTP fetch at render time, no local database or laptop dependency.
"""

from datetime import datetime, timedelta

import pytz
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from fetchers import fetch_ercot, fetch_isone, fetch_nyiso, fetch_pjm
from icons import liberty_bell, pine_tree, skyline, texas_star

st.set_page_config(page_title="DA LMP On-Peak Dashboard", layout="wide")

EASTERN = pytz.timezone("US/Eastern")
POLL_INTERVAL_MS = 60_000
CACHE_TTL_SECONDS = 50   # < poll interval so each auto-rerun fetches fresh data

ISOS = [
    {
        "key": "isone", "name": "ISO-NE", "location": "Internal Hub",
        "brand": "#465C67", "accent": "#62C3EE", "icon": pine_tree, "has_congestion": True,
    },
    {
        "key": "pjm", "name": "PJM", "location": "Western Hub",
        "brand": "#003087", "accent": "#3D8EC7", "icon": liberty_bell, "has_congestion": True,
    },
    {
        "key": "nyiso", "name": "NYISO", "location": "Zone G · Hudson Valley",
        "brand": "#0B5FFF", "accent": "#FF9900", "icon": skyline, "has_congestion": True,
    },
    {
        "key": "ercot", "name": "ERCOT", "location": "Hub North",
        "brand": "#1F8B9D", "accent": "#00AEC7", "icon": texas_star, "has_congestion": False,
    },
]

CSS = """
<style>
.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 28px;
    margin-top: 8px;
}
@media (max-width: 900px) {
    .dashboard-grid { grid-template-columns: 1fr; }
}
.iso-card {
    border-radius: 18px;
    padding: 26px 28px 22px 28px;
    background: linear-gradient(160deg, var(--tint) 0%, #ffffff 55%);
    border-top: 7px solid var(--brand);
    box-shadow: 0 4px 18px rgba(0,0,0,0.10);
    color-scheme: light;
}
.card-header { display: flex; align-items: center; gap: 14px; }
.card-header .icon-wrap { flex-shrink: 0; }
.title-block { flex-grow: 1; }
.iso-name {
    font-size: 26px; font-weight: 800; letter-spacing: 0.5px;
    color: var(--brand); line-height: 1.1;
}
.iso-loc { font-size: 14px; color: #666; font-weight: 500; }
.status-pill {
    font-size: 12px; font-weight: 700; padding: 5px 12px; border-radius: 20px;
    white-space: nowrap; text-transform: uppercase; letter-spacing: 0.5px;
}
.status-posted  { background: #DFF5E1; color: #1A7A3E; }
.status-pending { background: #FDF1D6; color: #A66A00; }
.status-error   { background: #FBE1E1; color: #A62B2B; }
.metric-row { display: flex; align-items: baseline; gap: 10px; margin-top: 18px; }
.metric-value { font-size: 52px; font-weight: 800; line-height: 1; color: var(--brand); }
.metric-label { font-size: 13px; color: #777; font-weight: 600; letter-spacing: 0.3px; }
.metric-row-sub { display: flex; align-items: baseline; gap: 10px; margin-top: 10px; }
.metric-value-sub { font-size: 26px; font-weight: 700; line-height: 1; }
.metric-label-sub { font-size: 12px; color: #888; font-weight: 500; }
.progress-track {
    height: 6px; border-radius: 3px; background: #EDEDED; margin-top: 16px; overflow: hidden;
}
.progress-fill { height: 100%; border-radius: 3px; background: var(--brand); }
.sparkline-wrap { margin-top: 14px; }
.error-text { font-size: 13px; color: #A62B2B; margin-top: 14px; font-family: monospace; }
</style>
"""


def next_operating_day():
    return datetime.now(EASTERN) + timedelta(days=1)


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
        "he_start": result["he_start"],
        "he_end": result["he_end"],
        "avg_lmp": avg_lmp,
        "avg_cong": avg_cong,
        "lmp_series": [r["lmp"] for r in rows],
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


def safe_fetch(fn, *args):
    try:
        return summarize(fn(*args)), None
    except Exception as exc:  # noqa: BLE001 -- surface to the card, not a hard crash
        return None, f"{type(exc).__name__}: {exc}"


def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def hex_mix(hex_color, base_hex, ratio):
    """Blend hex_color into base_hex as a fully OPAQUE hex color (not rgba
    alpha) so the card background never shows the underlying Streamlit theme
    (light or dark) bleeding through -- cards are always a light surface."""
    hex_color, base_hex = hex_color.lstrip("#"), base_hex.lstrip("#")
    r1, g1, b1 = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r2, g2, b2 = (int(base_hex[i:i + 2], 16) for i in (0, 2, 4))
    r = round(r1 * ratio + r2 * (1 - ratio))
    g = round(g1 * ratio + g2 * (1 - ratio))
    b = round(b1 * ratio + b2 * (1 - ratio))
    return f"#{r:02x}{g:02x}{b:02x}"


def sparkline_svg(values, color):
    if not values:
        return ""
    width, height, pad = 260, 46, 4
    lo, hi = min(values), max(values)
    span = hi - lo or 1
    n = len(values)
    step = (width - 2 * pad) / max(n - 1, 1)
    points = []
    for i, v in enumerate(values):
        x = pad + i * step
        y = height - pad - ((v - lo) / span) * (height - 2 * pad)
        points.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(points)
    fill_poly = f"{pad:.1f},{height - pad:.1f} " + poly + f" {width - pad:.1f},{height - pad:.1f}"
    return f"""
    <svg viewBox="0 0 {width} {height}" width="100%" height="{height}" preserveAspectRatio="none">
      <polygon points="{fill_poly}" fill="{hex_to_rgba(color, 0.12)}"/>
      <polyline points="{poly}" fill="none" stroke="{color}" stroke-width="2.5"
                stroke-linejoin="round" stroke-linecap="round"/>
    </svg>"""


def build_card_html(iso, summary, err):
    brand = iso["brand"]
    tint = hex_mix(brand, "#ffffff", 0.08)
    icon_svg = iso["icon"](brand)

    if err is not None:
        return f"""
        <div class="iso-card" style="--brand:{brand}; --tint:{tint};">
          <div class="card-header">
            <div class="icon-wrap">{icon_svg}</div>
            <div class="title-block">
              <div class="iso-name">{iso['name']}</div>
              <div class="iso-loc">{iso['location']}</div>
            </div>
            <div class="status-pill status-error">Error</div>
          </div>
          <div class="error-text">{err}</div>
        </div>"""

    accent = iso["accent"]
    status_class = "status-posted" if summary["posted"] else "status-pending"
    status_text = "Posted" if summary["posted"] else "Pending"
    pct = round(100 * summary["hours"] / summary["expected"]) if summary["expected"] else 0

    lmp_display = f"${summary['avg_lmp']:.2f}" if summary["avg_lmp"] is not None else "—"

    if not iso["has_congestion"]:
        # Structural: this ISO's DA report has no congestion component at all
        # (ERCOT hub SPPs), regardless of whether today's data has posted yet.
        cong_display, cong_color, cong_label = "n/a", "#999", "NO CONGESTION COMPONENT"
    elif summary["avg_cong"] is None:
        # Has a congestion component, just not posted/available yet.
        cong_display, cong_color, cong_label = "—", "#999", "ON-PEAK AVG CONGESTION"
    else:
        cong_val = summary["avg_cong"]
        cong_display = f"${cong_val:.2f}"
        cong_color = "#C0392B" if cong_val > 5 else "#1A7A3E" if cong_val < -5 else "#666"
        cong_label = "ON-PEAK AVG CONGESTION"

    spark = sparkline_svg(summary["lmp_series"], accent)

    return f"""
    <div class="iso-card" style="--brand:{brand}; --tint:{tint};">
      <div class="card-header">
        <div class="icon-wrap">{icon_svg}</div>
        <div class="title-block">
          <div class="iso-name">{iso['name']}</div>
          <div class="iso-loc">{iso['location']}</div>
        </div>
        <div class="status-pill {status_class}">{status_text} {summary['hours']}/{summary['expected']}</div>
      </div>
      <div class="metric-row">
        <div class="metric-value">{lmp_display}</div>
        <div class="metric-label">ON-PEAK AVG LMP<br>HE {summary['he_start']}&ndash;{summary['he_end']}</div>
      </div>
      <div class="metric-row-sub">
        <div class="metric-value-sub" style="color:{cong_color};">{cong_display}</div>
        <div class="metric-label-sub">{cong_label}</div>
      </div>
      <div class="progress-track"><div class="progress-fill" style="width:{pct}%;"></div></div>
      <div class="sparkline-wrap">{spark}</div>
    </div>"""


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("DA LMP On-Peak Dashboard")

    tomorrow = next_operating_day()
    st.caption(f"Operating Day: {tomorrow.strftime('%B %d, %Y')}  ·  "
               f"Refreshed {datetime.now(EASTERN).strftime('%I:%M:%S %p ET')}")

    isone_user = st.secrets["ISONE_USERNAME"]
    isone_pw = st.secrets["ISONE_PASSWORD"]
    pjm_key = st.secrets["PJM_API_KEY"]
    ye_user = st.secrets["YE_USER"]
    ye_pass = st.secrets["YE_PASS"]

    isone_summary, isone_err = safe_fetch(get_isone, tomorrow.strftime("%Y%m%d"), isone_user, isone_pw)
    pjm_summary, pjm_err = safe_fetch(get_pjm, tomorrow.strftime("%Y-%m-%d"), pjm_key)
    nyiso_summary, nyiso_err = safe_fetch(get_nyiso, tomorrow.strftime("%Y%m%d"))
    ercot_summary, ercot_err = safe_fetch(get_ercot, tomorrow.strftime("%m/%d/%Y"), ye_user, ye_pass)

    results = {
        "isone": (isone_summary, isone_err),
        "pjm": (pjm_summary, pjm_err),
        "nyiso": (nyiso_summary, nyiso_err),
        "ercot": (ercot_summary, ercot_err),
    }

    all_posted = all(
        err is None and summary["posted"] for summary, err in results.values()
    )

    cards = "".join(
        build_card_html(iso, *results[iso["key"]]) for iso in ISOS
    )
    st.markdown(f'<div class="dashboard-grid">{cards}</div>', unsafe_allow_html=True)

    st.write("")
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Refresh now"):
            st.cache_data.clear()
            st.rerun()
    with col2:
        if all_posted:
            st.success("All 4 ISOs posted — auto-refresh stopped.")
        else:
            st.info(f"Auto-refreshing every {POLL_INTERVAL_MS // 1000}s until all 4 ISOs post...")

    if not all_posted:
        st_autorefresh(interval=POLL_INTERVAL_MS, key="poller")


if __name__ == "__main__":
    main()
