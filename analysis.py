"""Plain-English weather analysis built from Open-Meteo data (no LLM or API key needed)."""
import pandas as pd

RAINY = 2.5  # mm/day; IMD's threshold for "light rain"


def hourly(fc):
    h = pd.DataFrame(fc["hourly"])
    h["time"] = pd.to_datetime(h["time"])
    return h


def daily_df(fc):
    d = pd.DataFrame(fc["daily"])
    d["date"] = pd.to_datetime(d.pop("time"))
    h = hourly(fc)
    d["cloud"] = d["date"].map(h.groupby(h.time.dt.normalize())["cloud_cover"].mean())
    d = d.rename(columns={"temperature_2m_max": "high", "temperature_2m_min": "low", "precipitation_sum": "rain",
                          "precipitation_probability_max": "rain_prob", "wind_speed_10m_max": "wind"})
    d["label"] = d["date"].dt.strftime("%a %d")
    d["day"] = d["date"].dt.strftime("%a %d %b")
    return d


def next_hours(fc, n=24):
    h = hourly(fc)
    return h[h.time >= pd.to_datetime(fc["current"]["time"]).floor("h")].head(n)


def temp_feel(t):
    return ("very hot" if t >= 38 else "hot" if t >= 33 else "warm" if t >= 28 else
            "pleasant" if t >= 22 else "cool" if t >= 15 else "cold")


def sky_text(c):
    return "clear" if c < 20 else "partly cloudy" if c < 50 else "mostly cloudy" if c < 80 else "overcast"


def wind_text(w):
    return "light" if w < 12 else "breezy" if w < 29 else "strong" if w < 50 else "very strong"


def rain_text(mm, prob):
    if mm >= 115.5: return f"very heavy rain (about {mm:.0f} mm), flooding is possible"
    if mm >= 64.5: return f"heavy rain (about {mm:.0f} mm)"
    if mm >= 15.5: return f"moderate rain (about {mm:.0f} mm)"
    if mm >= RAINY: return f"light rain (about {mm:.1f} mm)"
    return "a chance of brief showers" if prob >= 50 else "dry"


def hr(t):
    return t.strftime("%I %p").lstrip("0")


def report(place, fc):
    d, nx, c = daily_df(fc), next_hours(fc), fc["current"]
    rainy = d[d.rain >= RAINY]
    wetness = "mostly dry" if len(rainy) <= 1 else "a mix of sun and showers" if len(rainy) <= 3 else "wet"
    rep = {"headline": f"{temp_feel(d.high.mean()).capitalize()} and {wetness} week ahead for {place}"}
    rep["now"] = (f"Right now it is {c['temperature_2m']:.0f}°C with {sky_text(c['cloud_cover'])} skies, "
                  f"{wind_text(c['wind_speed_10m'])} wind and {c['relative_humidity_2m']:.0f}% humidity.")
    wet_h = nx[nx.precipitation >= 0.2]
    span = (wet_h.time.iloc[-1] - wet_h.time.iloc[0]).total_seconds() / 3600 if len(wet_h) else 0
    rep["next24"] = (f"Rain is expected {'on and off ' if span > 5 else ''}between {hr(wet_h.time.iloc[0])} and {hr(wet_h.time.iloc[-1])} in the next 24 hours "
                     f"(about {nx.precipitation.sum():.1f} mm in total, peak chance {nx.precipitation_probability.max():.0f}%)."
                     if len(wet_h) else
                     f"No significant rain is expected in the next 24 hours (highest chance {nx.precipitation_probability.max():.0f}%).")
    rep["days"] = [f"**{r.day}** — {temp_feel(r.high)} and {sky_text(r.cloud)}, {r.low:.0f}–{r.high:.0f}°C. "
                   f"{rain_text(r.rain, r.rain_prob).capitalize()}. Wind up to {r.wind:.0f} km/h." for r in d.itertuples()]
    ins = []
    if len(rainy):
        wet = d.loc[d.rain.idxmax()]
        ins.append(f"{len(rainy)} of {len(d)} days are expected to bring rain; the wettest is {wet.day} (about {wet.rain:.0f} mm).")
    else:
        ins.append("No day this week is expected to bring meaningful rain.")
    ins.append(f"Hottest day: {d.loc[d.high.idxmax(), 'day']} ({d.high.max():.0f}°C). "
               f"Coolest night: {d.loc[d.low.idxmin(), 'day']} ({d.low.min():.0f}°C).")
    if len(d) >= 6:
        diff = d.high.iloc[-3:].mean() - d.high.iloc[:3].mean()
        ins.append(f"Daytime temperatures are trending {'up' if diff > 0 else 'down'} by about {abs(diff):.1f}°C over the week."
                   if abs(diff) >= 1.5 else "Daytime temperatures stay fairly steady through the week.")
    ins.append(f"Average cloud cover is {d.cloud.mean():.0f}%; the sunniest day is {d.loc[d.cloud.idxmin(), 'day']}.")
    rep["insights"] = ins
    adv = []
    if len(wet_h) or d.rain.iloc[0] >= RAINY:
        adv.append("Carry an umbrella or raincoat today.")
    if d.high.iloc[0] >= 35:
        adv.append("It will be very hot in the afternoon: drink plenty of water and avoid the midday sun.")
    if d.wind.max() >= 40:
        adv.append(f"Strong winds up to {d.wind.max():.0f} km/h are possible on {d.loc[d.wind.idxmax(), 'day']}; secure loose objects.")
    ok = d[(d.rain < RAINY) & (d.high <= 34)]
    if len(ok):
        adv.append(f"Best day for outdoor plans: {ok.sort_values(['rain_prob', 'rain']).iloc[0].day}.")
    rep["advice"] = adv
    rep["note"] = "Days 1–3 are the most reliable; treat days 5–7 as a trend, as they can change."
    return rep


def to_markdown(rep):
    out = [f"### {rep['headline']}", rep["now"], rep["next24"], "**Highlights**"]
    out += [f"- {x}" for x in rep["insights"]]
    if rep["advice"]:
        out += ["**Suggestions**"] + [f"- {x}" for x in rep["advice"]]
    out += ["**Day by day**"] + [f"- {x}" for x in rep["days"]] + [f"*{rep['note']}*"]
    return "\n\n".join(out)


def _matches(p, *words):
    return any(w in p for w in words)


def _rain_line(d, nx):
    today = d.iloc[0]
    wet_h = nx[nx.precipitation >= 0.2]
    if len(wet_h):
        span = f"between {hr(wet_h.time.iloc[0])} and {hr(wet_h.time.iloc[-1])}"
        return (f"Yes — {rain_text(today.rain, today.rain_prob)} is expected today, {span} "
                f"(peak chance {nx.precipitation_probability.max():.0f}%).")
    if today.rain_prob >= 30:
        return f"Unlikely, but there's a {today.rain_prob:.0f}% chance of a stray shower today."
    return f"No, it should stay dry today (rain chance {today.rain_prob:.0f}%)."


def _heat_line(d, c):
    today = d.iloc[0]
    return (f"It's {c['temperature_2m']:.0f}°C right now, feeling {temp_feel(c['temperature_2m'])}. "
            f"Today's high should reach about {today.high:.0f}°C ({temp_feel(today.high)}), "
            f"with a low of {today.low:.0f}°C overnight.")


def _wind_line(d, c):
    today = d.iloc[0]
    return (f"Winds are {wind_text(c['wind_speed_10m'])} right now at {c['wind_speed_10m']:.0f} km/h, "
            f"gusting up to {today.wind:.0f} km/h at some point today.")


def _best_day_line(d):
    ok = d[(d.rain < RAINY) & (d.high <= 34)]
    if len(ok):
        pick = ok.sort_values(["rain_prob", "rain"]).iloc[0]
        return f"**{pick.day}** looks best — {temp_feel(pick.high)}, {sky_text(pick.cloud)}, low rain chance ({pick.rain_prob:.0f}%)."
    pick = d.sort_values(["rain", "rain_prob"]).iloc[0]
    return f"Every day has some rain risk this week; **{pick.day}** is the driest option ({rain_text(pick.rain, pick.rain_prob)})."


def _week_line(d):
    rainy = d[d.rain >= RAINY]
    wet = f"{len(rainy)} of {len(d)} days are expected to bring rain" if len(rainy) else "No day this week is expected to bring meaningful rain"
    return (f"{wet}. Hottest day: **{d.loc[d.high.idxmax(), 'day']}** ({d.high.max():.0f}°C). "
            f"Coolest night: **{d.loc[d.low.idxmin(), 'day']}** ({d.low.min():.0f}°C).")


def single_answer(prompt, place, fc):
    """Answer a specific question about one place using only the fetched data (no LLM)."""
    p = prompt.lower()
    d, nx, c = daily_df(fc), next_hours(fc), fc["current"]
    lines = []
    if _matches(p, "rain", "umbrella", "wet", "shower", "monsoon"):
        lines.append(_rain_line(d, nx))
    if _matches(p, "hot", "heat", "warm", "temperature", "cold", "cool"):
        lines.append(_heat_line(d, c))
    if _matches(p, "wind", "breez", "gust"):
        lines.append(_wind_line(d, c))
    if _matches(p, "best day", "outdoor", "plan", "picnic", "trip"):
        lines.append(_best_day_line(d))
    if _matches(p, "week", "weekend", "days ahead", "forecast"):
        lines.append(_week_line(d))
    if _matches(p, "cloud", "sun", "sky"):
        lines.append(f"Skies are {sky_text(c['cloud_cover'])} right now ({c['cloud_cover']:.0f}% cloud cover); "
                     f"today's average is {d.cloud.iloc[0]:.0f}%.")
    if lines:
        return f"**{place}**\n\n" + "\n\n".join(lines)
    # generic / unmatched question -> full plain-English report
    return to_markdown(report(place, fc))


def multi_answer(prompt, data):
    """Answer a specific question across several places using only the fetched data (no LLM)."""
    p = prompt.lower()
    cmp_df, lines = compare(data)
    if _matches(p, "which", "where", "what city", "what place"):
        if _matches(p, "rain", "wet", "monsoon"):
            row = cmp_df.loc[cmp_df.rain_week.idxmax()]
            return f"**{row.place}** is expected to get the most rain this week (about {row.rain_week:.0f} mm)."
        if _matches(p, "hot", "heat", "warm"):
            row = cmp_df.loc[cmp_df.high_today.idxmax()]
            return f"**{row.place}** is the hottest today at {row.high_today:.0f}°C."
        if _matches(p, "cool", "cold"):
            row = cmp_df.loc[cmp_df.high_today.idxmin()]
            return f"**{row.place}** is the coolest today at {row.high_today:.0f}°C."
        if _matches(p, "best", "outdoor", "good weather", "nice weather"):
            ok = cmp_df[cmp_df.rain_today < RAINY]
            pick = (ok.sort_values(["rain_week", "avg_high"]).iloc[0] if len(ok)
                    else cmp_df.sort_values("rain_week").iloc[0])
            return f"**{pick.place}** looks best overall — low rain and a {pick.avg_high:.0f}°C average high this week."
        if _matches(p, "dry", "sunny", "clear"):
            row = cmp_df.loc[cmp_df.rain_week.idxmin()]
            return f"**{row.place}** is driest this week (about {row.rain_week:.0f} mm expected)."
    if _matches(p, "rain", "wet", "umbrella", "shower"):
        n_rain = int((cmp_df.rain_today >= RAINY).sum())
        detail = ("Rain is expected today in " + ", ".join(cmp_df[cmp_df.rain_today >= RAINY].place) if n_rain
                  else "No location expects meaningful rain today")
        return f"{detail}. " + lines[0]
    if _matches(p, "hot", "warm", "temperature", "cold", "cool"):
        return lines[1]
    # generic / unmatched question -> overview across all locations
    return "\n".join(f"- {x}" for x in lines)


def answer_query(prompt, focus, data):
    """Best-effort automated answer to `prompt`, computed directly from real-time weather data."""
    multi = len(data) > 1
    parts = []
    if multi:
        parts.append(multi_answer(prompt, data))
    (_, fc) = data[focus]
    parts.append(single_answer(prompt, focus, fc))
    return "\n\n---\n\n".join(parts) if multi else parts[0]


def compare(data):
    """data: {label: (loc, fc)} -> (DataFrame, plain-English lines)"""
    rows = []
    for k, (_, fc) in data.items():
        d = daily_df(fc)
        rows.append(dict(place=k.split(",")[0], full=k, high_today=d.high.iloc[0], low_today=d.low.iloc[0],
                         rain_today=d.rain.iloc[0], rain_week=d.rain.sum(), rain_days=int((d.rain >= RAINY).sum()),
                         cloud=d.cloud.mean(), avg_high=d.high.mean()))
    df = pd.DataFrame(rows)
    w, dr = df.loc[df.rain_week.idxmax()], df.loc[df.rain_week.idxmin()]
    h, cl = df.loc[df.high_today.idxmax()], df.loc[df.high_today.idxmin()]
    n_rain = int((df.rain_today >= RAINY).sum())
    lines = [f"Wettest this week: **{w.place}** (about {w.rain_week:.0f} mm). Driest: **{dr.place}** ({dr.rain_week:.0f} mm).",
             f"Hottest today: **{h.place}** ({h.high_today:.0f}°C). Coolest today: **{cl.place}** ({cl.high_today:.0f}°C).",
             f"Rain is expected today in {n_rain} of {len(df)} locations." if n_rain else
             f"No meaningful rain is expected today in any of the {len(df)} locations."]
    return df, lines
