import datetime as dt
import html
import io
import os
from concurrent.futures import ThreadPoolExecutor
import folium
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from dotenv import load_dotenv
import analysis as an
import charts as ch
import theme
import weather_data as wd
from cities import INDIA
from rag import VectorStore, answer

load_dotenv()  # reads ANTHROPIC_API_KEY (and other vars) from a local .env file, if present

st.set_page_config(page_title="India Weather · Satellite + RAG", page_icon="🛰️", layout="wide")
ALL = "All India (one city per state)"
HOME, REPORT, BARS, ASK = "🏠 Home", "📝 Weather report", "📊 Bar charts", "💬 Ask AI"
HAS_KEY = bool(os.getenv("ANTHROPIC_API_KEY"))
EX_ONE = ["Will it rain today?", "Best day this week for outdoor plans?", "How hot will it get?"]
EX_MULTI = ["Which city will get the most rain?", "Which city is hottest today?", "Where is the weather best this weekend?"]

# theme first, so the page is styled as early as possible (the toggle lives in the sidebar)
st.session_state.setdefault("dark", False)
DARK = st.session_state.dark
st.markdown(theme.css(DARK), unsafe_allow_html=True)


# ---------- helpers ----------
def stretch(fn, *a, **k):
    """Full-width widgets across Streamlit versions."""
    try:
        return fn(*a, width="stretch", **k)
    except Exception:
        return fn(*a, use_container_width=True, **k)


def card(parent, name):
    """A styled sidebar card (falls back to a bordered container on older Streamlit)."""
    try:
        return parent.container(key=f"card_{name}")
    except TypeError:
        return parent.container(border=True)


def friendly(e):
    m = str(e).lower()
    if "credit" in m:
        return "your Anthropic account has no credits"
    if "api_key" in m or "authentication" in m or "api key" in m:
        return "the API key is missing or invalid"
    if "connection" in m or "resolve" in m:
        return "no internet connection"
    return type(e).__name__


def icon(cloud, rain):
    return "🌧️" if rain > 0.1 else "☀️" if cloud < 20 else "🌤️" if cloud < 50 else "⛅" if cloud < 80 else "☁️"


def ago(t):
    m = int((dt.datetime.now() - t).total_seconds() // 60)
    return "just now" if m < 1 else f"{m} min ago" if m < 60 else f"{m // 60} h ago"


def draw(df, col, ylabel, bar=False):
    """Interactive chart coloured for the current theme."""
    try:
        stretch(st.altair_chart, ch.alt_chart(df, col, ylabel, DARK, bar), theme=None)
    except ImportError:
        (st.bar_chart if bar else st.line_chart)(df[[col]])


def html_table(rows):
    def cell(c, v):
        if c in ("Cloud %", "Rain chance %"):
            v = float(v or 0)
            return f'<td><div class="bar"><div style="width:{min(v, 100):.0f}%"></div><span>{v:.0f}%</span></div></td>'
        return f"<td>{html.escape(str(v))}</td>"
    cols = list(rows[0])
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body = "".join("<tr>" + "".join(cell(c, r[c]) for c in cols) + "</tr>" for r in rows)
    st.markdown(f'<div class="wx-wrap"><table class="wx-table"><tr>{head}</tr>{body}</table></div>',
                unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def find(name):
    return wd.search_places(name, "IN")


@st.cache_data(ttl=900, show_spinner=False)
def load(locs):
    def one(l):
        try:
            return wd.fetch_forecast(l[1], l[2])
        except Exception:
            return None
    with ThreadPoolExecutor(8) as ex:
        fcs = list(ex.map(one, locs))
    sat = wd.fetch_satellite(locs[0][1], locs[0][2]) if len(locs) == 1 else None
    return fcs, sat


@st.cache_data(ttl=900, show_spinner=False)
def png(kind, key, dark, _fc=None, _d=None, _cmp=None):
    """Render a chart once (per theme) and cache the image so page switches are instant."""
    make = {
        "next24": lambda: ch.next24(_fc),
        "temp": lambda: ch.temp_bars(_d),
        "rain": lambda: ch.rain_bars(_d),
        "cloud": lambda: ch.bar(_d.label, _d.cloud, "Average cloud cover", "%", color=ch.GREY),
        "wind": lambda: ch.bar(_d.label, _d.wind, "Maximum wind speed", "km/h", color=ch.ORANGE),
        "cmp_rain": lambda: ch.hbar(_cmp.place, _cmp.rain_week, "Expected rain, next 7 days", "mm", ch.BLUE),
        "cmp_temp": lambda: ch.hbar(_cmp.place, _cmp.high_today, "Today's high temperature", "°C", ch.RED),
    }[kind]
    with plt.rc_context(ch.rc(dark)):
        fig = make()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110)
        plt.close(fig)
    return buf.getvalue()


def get_store():
    """Build the AI search index lazily, only when someone actually asks a question."""
    s = st.session_state
    sig = (s.key, s.fetched)
    if s.get("store_sig") != sig:
        docs, tags = [], []
        for label, (l, fc) in s.data.items():
            d = wd.build_documents(label, fc, s.sat, detailed=len(s.data) == 1)
            docs += d
            tags += [label.split(",")[0]] * len(d)
        s.store, s.store_sig = VectorStore(docs, tags), sig
    return s.store


def builtin_answer(prompt, focus):
    """Answers the question directly from the live forecast data (no LLM, no API key needed)."""
    s = st.session_state
    return an.answer_query(prompt, focus, s.data)


def reply(prompt, focus, multi, scope):
    """Returns (text, hits, note, note_ok)."""
    if not HAS_KEY:
        return builtin_answer(prompt, focus), None, "Automated answer, computed from the live forecast data.", True
    try:
        with st.spinner("Reading the forecast..."):
            text, hits = answer(get_store(), scope, prompt, k=16 if multi else 8)
        return text, hits, None, True
    except Exception as e:
        return (builtin_answer(prompt, focus), None,
                f"AI answer unavailable: {friendly(e)}. Showing the automated data analysis instead.", False)


def show_msg(m):
    if m.get("note"):
        (st.caption if m.get("note_ok") else st.warning)(m["note"])
    st.markdown(m["content"])
    if m.get("hits"):
        with st.expander("Data used for this answer"):
            st.write("\n\n".join(m["hits"]))


def ask_page(focus, multi, scope):
    top = st.columns([5, 1])
    top[0].subheader("💬 Ask AI")
    chat = st.session_state.setdefault("chat", [])
    if chat and stretch(top[1].button, "🗑️ Clear"):
        chat.clear()
        st.rerun()
    st.caption(f"Asking about **{scope}** · answers use the latest forecast data.")
    for m in chat:
        with st.chat_message(m["role"]):
            if m["role"] == "assistant":
                st.caption(f"📍 {m['scope']}")
            show_msg(m) if m["role"] == "assistant" else st.write(m["content"])
    clicked, chips = None, st.empty()
    if not chat:
        with chips.container():
            st.markdown("**Try asking:**")
            ex = EX_MULTI if multi else EX_ONE
            cols = st.columns(len(ex))
            for i, e in enumerate(ex):
                if stretch(cols[i].button, e, key=f"ex{i}"):
                    clicked = e
    prompt = st.chat_input("Ask about the weather...") or clicked
    if prompt:
        chips.empty()
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            st.caption(f"📍 {scope}")
            text, hits, note, note_ok = reply(prompt, focus, multi, scope)
            msg = {"role": "assistant", "content": text, "hits": hits, "note": note, "note_ok": note_ok, "scope": scope}
            show_msg(msg)
        chat += [{"role": "user", "content": prompt}, msg]
        del chat[:-30]


# ---------- sidebar ----------
sb = st.sidebar
sb.markdown('<div class="brand">🛰️ <b>India Weather</b><br><span>Satellite forecasts + AI</span></div>',
            unsafe_allow_html=True)
with card(sb, "look"):
    st.markdown("**🎨 Appearance**")
    st.toggle("🌙 Dark mode", key="dark")

with card(sb, "loc"):
    st.markdown("**📍 Location**")
    mode = st.radio("Look up", ["City", "State / UT", "Search"], horizontal=True, label_visibility="collapsed")
    if mode == "City":
        state = st.selectbox("State / UT", list(INDIA), index=list(INDIA).index("Goa"))
        city = st.selectbox("City", [c[0] for c in INDIA[state]])
        _, la, lo = next(c for c in INDIA[state] if c[0] == city)
        scope, locs = f"{city}, {state}", [(f"{city}, {state}", la, lo)]
    elif mode == "State / UT":
        state = st.selectbox("State / UT (or all of India)", [ALL] + list(INDIA))
        if state == ALL:
            locs = [(f"{v[0][0]}, {s_}", v[0][1], v[0][2]) for s_, v in INDIA.items()]
        else:
            locs = [(f"{c}, {state}", a, b) for c, a, b in INDIA[state]]
        scope = state
    else:
        q0 = st.text_input("Place name", "Panjim")
        try:
            found = find(q0)
        except Exception:
            st.error("Couldn't search right now. Check your internet connection.")
            st.stop()
        if not found:
            st.warning("No place found. Try another spelling.")
            st.stop()
        pick = st.selectbox("Pick the right match", found, format_func=lambda m: m["label"])
        scope, locs = pick["label"], [(pick["label"], pick["lat"], pick["lon"])]

data_card = card(sb, "data")
with data_card:
    st.markdown("**🔄 Data**")
    refresh = stretch(st.button, "Refresh data")
with sb.expander("ℹ️ How to use"):
    st.markdown("- Use the menu at the top of the page to switch views, then pick a city, a state, or search a place.\n"
                "- **Home**: the dashboard. **Report**: the forecast in plain English.\n"
                "- **Bar charts**: easy-to-read charts. **Ask AI**: chat about the weather.")
if refresh:
    st.cache_data.clear()
locs = tuple(locs)

# ---------- load data ----------
st.title("🛰️ India Weather · Satellite + RAG")
try:
    _nav = st.container(key="mainnav")
except TypeError:
    _nav = st.container()
with _nav:
    page = st.radio("View", [HOME, REPORT, BARS, ASK], horizontal=True, label_visibility="collapsed")
if refresh or st.session_state.get("key") != locs:
    with st.status(f"Getting the latest forecast for {len(locs)} location(s)...", expanded=False) as status:
        fcs, sat = load(locs)
        data = {l[0]: (l, fc) for l, fc in zip(locs, fcs) if fc is not None}
        if not data:
            status.update(label="Couldn't reach the weather service", state="error")
            st.error("Could not load weather data. Check your internet connection and press Refresh.")
            st.stop()
        st.session_state.update(key=locs, scope=scope, data=data, sat=sat, fetched=dt.datetime.now())
        n_fail = len(locs) - len(data)
        status.update(label="Forecast ready" + (f" ({n_fail} location(s) unavailable)" if n_fail else ""),
                      state="complete")
s = st.session_state
data, multi = s.data, len(s.data) > 1
with data_card:
    st.caption(f"Updated {ago(s.fetched)} · cached for 15 min")

st.subheader(f"{s.scope} · {len(data)} locations" if multi else next(iter(data)))
focus = st.selectbox("Show details for", list(data)) if multi else next(iter(data))
(label, la, lo), fc = data[focus]
c, dly = fc["current"], fc["daily"]
st.caption(f"{icon(c['cloud_cover'], c['precipitation'])} Local time at {focus.split(',')[0]}: "
           f"{pd.to_datetime(c['time']):%a %d %b, %I:%M %p}")

# ================= HOME =================
if page == HOME:
    if multi:
        html_table([{"Location": k, "Now °C": f_["current"]["temperature_2m"], "Cloud %": f_["current"]["cloud_cover"],
                     "High °C": f_["daily"]["temperature_2m_max"][0], "Low °C": f_["daily"]["temperature_2m_min"][0],
                     "Rain mm": f_["daily"]["precipitation_sum"][0],
                     "Rain chance %": f_["daily"]["precipitation_probability_max"][0]}
                    for k, (_, f_) in data.items()])
    m = st.columns(6)
    m[0].metric("🌡️ Now (°C)", c["temperature_2m"])
    m[1].metric("↕️ Today high / low", f"{dly['temperature_2m_max'][0]:.0f}° / {dly['temperature_2m_min'][0]:.0f}°")
    m[2].metric("🌧️ Rain chance", f"{dly['precipitation_probability_max'][0]}%", help="Highest chance of rain today")
    m[3].metric("☁️ Cloud cover", f"{c['cloud_cover']}%")
    m[4].metric("💧 Humidity", f"{c['relative_humidity_2m']}%")
    m[5].metric("💨 Wind (km/h)", c["wind_speed_10m"])

    left, right = st.columns(2)
    with left:
        st.caption("7-day forecast")
        h = wd.hourly_df(fc).set_index("time")
        t1, t2, t3 = st.tabs(["🌡️ Temperature", "🌧️ Rain chance", "☁️ Cloud cover"])
        with t1:
            draw(h, "temperature_2m", "°C")
        with t2:
            draw(h, "precipitation_probability", "%")
        with t3:
            draw(h, "cloud_cover", "%")
        if s.sat is not None and not multi:
            st.caption("Satellite-derived solar radiation (W/m²)")
            draw(s.sat.assign(time=pd.to_datetime(s.sat.time)).set_index("time"), "radiation", "W/m²")
    with right:
        st.caption("NASA GIBS satellite imagery (MODIS true colour, yesterday)")
        day = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        fmap = folium.Map(location=[la, lo], zoom_start=5 if multi else 7)
        folium.TileLayer(
            tiles=("https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/"
                   f"default/{day}/GoogleMapsCompatible_Level9/{{z}}/{{y}}/{{x}}.jpg"),
            attr="NASA GIBS", max_native_zoom=9, name="Satellite").add_to(fmap)
        for k, ((_, a_, b_), _) in data.items():
            folium.Marker([a_, b_], tooltip=k).add_to(fmap)
        st_folium(fmap, height=380, use_container_width=True, returned_objects=[])

# ================= REPORT =================
elif page == REPORT:
    if multi:
        st.markdown("### Overview: " + s.scope)
        st.markdown("\n".join(f"- {x}" for x in an.compare(data)[1]))
        st.divider()
    st.markdown(an.to_markdown(an.report(focus, fc)))

# ================= BAR CHARTS =================
elif page == BARS:
    d = an.daily_df(fc)
    k = f"{focus}|{s.fetched:%H%M%S}"
    stretch(st.image, png("next24", k, DARK, _fc=fc))
    a, b = st.columns(2)
    with a:
        stretch(st.image, png("temp", k, DARK, _d=d))
        stretch(st.image, png("cloud", k, DARK, _d=d))
    with b:
        stretch(st.image, png("rain", k, DARK, _d=d))
        stretch(st.image, png("wind", k, DARK, _d=d))
    if s.sat is not None and not multi:
        st.caption("Satellite-derived solar radiation (W/m²): low values in the daytime mean thick cloud")
        draw(s.sat.assign(time=pd.to_datetime(s.sat.time)).set_index("time"), "radiation", "W/m²", bar=True)
    if multi:
        cmp_df = an.compare(data)[0]
        st.subheader("Compare locations")
        a, b = st.columns(2)
        ck = f"{s.scope}|{s.fetched:%H%M%S}"
        with a:
            stretch(st.image, png("cmp_rain", ck, DARK, _cmp=cmp_df))
        with b:
            stretch(st.image, png("cmp_temp", ck, DARK, _cmp=cmp_df))

# ================= ASK AI (separate page) =================
else:
    ask_page(focus, multi, s.scope)

st.caption("Data: Open-Meteo forecasts and NASA GIBS imagery. Forecasts are model estimates and can change.")
