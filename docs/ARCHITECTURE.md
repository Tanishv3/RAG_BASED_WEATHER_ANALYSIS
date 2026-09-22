# Architecture deep‑dive

This document goes one level deeper than the main [README](../README.md): how the app boots,
how each of the four views renders, how caching works, and how a location moves through the app
end to end. See the README for the high‑level component diagram and the Ask AI decision flow.

---

## App boot sequence

```mermaid
sequenceDiagram
    participant Streamlit
    participant App as app.py
    participant Env as .env
    participant Theme as theme.py
    participant Sidebar

    Streamlit->>App: run app.py
    App->>Env: load_dotenv()
    App->>App: HAS_KEY = bool(os.getenv("ANTHROPIC_API_KEY"))
    App->>App: st.set_page_config(...)
    App->>Theme: theme.css(dark)
    Theme-->>App: CSS string
    App->>App: st.markdown(css, unsafe_allow_html=True)
    App->>Sidebar: render brand, dark-mode toggle, location picker, data card
    Sidebar-->>App: chosen locs, scope, refresh flag
    App->>App: load(locs) [cached, 15 min TTL]
    App-->>Streamlit: render selected view (Home / Report / Bar charts / Ask AI)
```

---

## Sidebar → location resolution

The sidebar supports three independent ways to choose what to show, all normalized into the same
`locs: [(label, lat, lon), ...]` shape before data loading.

```mermaid
flowchart TD
    START["Sidebar: 'Look up' radio"] --> MODE{Mode}
    MODE -->|City| CITY["Pick State/UT, then City\n(from cities.py)"]
    MODE -->|"State / UT"| STATE{"Which State?"}
    MODE -->|Search| SEARCH["Free-text place name"]

    CITY --> ONE["locs = [ (city, state, lat, lon) ]\n(single location)"]

    STATE -->|"All India"| ALLIN["locs = one city per state\n(36 locations)"]
    STATE -->|"Specific state"| STATECITIES["locs = every city in that state"]

    SEARCH --> GEOCODE["find(query) → Open-Meteo geocoding\n(cached 1h)"]
    GEOCODE --> FOUND{Results?}
    FOUND -->|None| WARN["Show warning, st.stop()"]
    FOUND -->|Yes| PICK["User picks the right match"]
    PICK --> ONE

    ONE --> LOAD["load(locs) → fetch_forecast per location"]
    ALLIN --> LOAD
    STATECITIES --> LOAD
```

---

## Per‑view rendering

```mermaid
flowchart TD
    NAV["Top nav: Home | Report | Bar charts | Ask AI"] --> PAGE{Selected view}

    PAGE -->|Home| HOME["Metrics row (temp, high/low, rain%,\ncloud, humidity, wind)"]
    HOME --> HTABLE{"Multiple locations?"}
    HTABLE -->|Yes| TABLE["Comparison table across locations"]
    HTABLE -->|No| SKIP1[ ]
    HOME --> TABS["Hourly tabs: Temperature / Rain chance / Cloud cover"]
    HOME --> SATCHECK{"Satellite data\navailable & single location?"}
    SATCHECK -->|Yes| SATCHART["Solar radiation chart"]
    HOME --> MAP["folium map + NASA GIBS tile layer\n+ marker per location"]

    PAGE -->|Report| REPORT["analysis.report(focus, fc)\n→ to_markdown()"]
    REPORT --> RMULTI{"Multiple locations?"}
    RMULTI -->|Yes| RCOMPARE["analysis.compare(data) overview\nprepended"]

    PAGE -->|"Bar charts"| BARS["next24 / temp / rain / cloud / wind\nPNGs via charts.py, cached per theme"]
    BARS --> BMULTI{"Multiple locations?"}
    BMULTI -->|Yes| BCOMPARE["Cross-location rain & temp\nhorizontal bar charts"]

    PAGE -->|"Ask AI"| ASK["See Ask AI flow in README.md"]
```

---

## Caching layers

```mermaid
flowchart LR
    subgraph "st.cache_data"
        FIND["find(place_name)\nTTL 1h"]
        LOAD["load(locs)\nTTL 15m — forecast + satellite"]
        PNG["png(kind, key, dark, ...)\nTTL 15m — rendered chart bytes"]
    end
    subgraph "st.session_state"
        DATA["data: {label: (loc, forecast)}"]
        SAT["sat: DataFrame or None"]
        STORE["store: VectorStore\nrebuilt only when (key, fetched) signature changes"]
        CHAT["chat: last 30 messages"]
    end

    FIND --> Sidebar
    LOAD --> DATA
    LOAD --> SAT
    DATA --> STORE
    PNG --> BarsView["Bar charts view"]
```

Pressing **Refresh data** calls `st.cache_data.clear()`, which invalidates `find`, `load`, and
`png` together, forcing a fresh fetch on the next run.

---

## Error handling paths

```mermaid
flowchart TD
    A["fetch_forecast(lat, lon)\nfor each location"] --> B{"Request failed?"}
    B -->|Yes, for one location| C["That location dropped from `data`,\nrest of the app continues"]
    B -->|Yes, for ALL locations| D["st.error shown,\nst.stop()"]
    B -->|No| E["Location included in `data`"]

    F["fetch_satellite(lat, lon)"] --> G{"Request failed?"}
    G -->|Yes| H["Returns None — satellite\nsections simply don't render"]
    G -->|No| I["DataFrame returned"]

    J["Ask AI: Claude call"] --> K{"Exception?"}
    K -->|"Yes (bad key, no credits,\nno internet, etc.)"| L["friendly(e) turns it into\na plain-English reason"]
    L --> M["Falls back to analysis.answer_query()\nshown with a warning"]
    K -->|No| N["AI answer shown normally"]
```

---

## Where to look for what

| I want to change... | Edit... |
|---|---|
| Which cities/states are selectable | `cities.py` |
| Forecast fields fetched from Open‑Meteo | `weather_data.py` → `fetch_forecast` |
| Wording of the plain‑English report | `analysis.py` → `report`, `to_markdown` |
| What the built‑in Q&A engine can answer | `analysis.py` → `single_answer`, `multi_answer` |
| Chart appearance | `charts.py` |
| Light/dark colors and CSS | `theme.py` |
| RAG prompt / retrieval behavior | `rag.py` |
| Page layout, sidebar, session‑state, routing | `app.py`|
