"""Fetch weather + satellite data and turn it into text documents for RAG."""
import requests
import pandas as pd

http = requests.Session()
http.trust_env = False  # ignore stray proxy environment variables

GEO = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
SATELLITE = "https://satellite-api.open-meteo.com/v1/archive"  # satellite-derived radiation


def search_places(name, country_code=""):
    params = {"name": name, "count": 10}
    if country_code:
        params["countryCode"] = country_code.upper()
    res = http.get(GEO, params=params, timeout=15).json().get("results") or []
    return [{"label": ", ".join(x for x in (r["name"], r.get("admin1"), r.get("country")) if x),
             "lat": r["latitude"], "lon": r["longitude"]} for r in res]


def fetch_forecast(lat, lon, days=7):
    params = {
        "latitude": lat, "longitude": lon, "forecast_days": days, "timezone": "auto",
        "current": "temperature_2m,relative_humidity_2m,precipitation,cloud_cover,wind_speed_10m,pressure_msl",
        "hourly": "temperature_2m,precipitation_probability,precipitation,cloud_cover,wind_speed_10m,shortwave_radiation",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max",
    }
    r = http.get(FORECAST, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_satellite(lat, lon):
    """Best effort: recent satellite-derived shortwave radiation (a cloud-cover proxy).
    Coverage depends on the satellite; failure is non-fatal."""
    try:
        r = http.get(SATELLITE, params={
            "latitude": lat, "longitude": lon, "hourly": "shortwave_radiation",
            "past_days": 1, "forecast_days": 1, "timezone": "auto"}, timeout=20)
        r.raise_for_status()
        h = r.json()["hourly"]
        return pd.DataFrame({"time": h["time"], "radiation": h["shortwave_radiation"]}).dropna()
    except Exception:
        return None


def hourly_df(fc):
    df = pd.DataFrame(fc["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    return df


def build_documents(place, fc, sat, detailed=True):
    """Chunk the data into small, self-contained text documents."""
    docs, u = [], fc["current_units"]
    c = fc["current"]
    docs.append(
        f"Current conditions in {place} at {c['time']}: temperature {c['temperature_2m']}{u['temperature_2m']}, "
        f"humidity {c['relative_humidity_2m']}%, cloud cover {c['cloud_cover']}%, "
        f"precipitation {c['precipitation']} mm, wind {c['wind_speed_10m']} {u['wind_speed_10m']}, "
        f"sea-level pressure {c['pressure_msl']} hPa.")
    d = fc["daily"]
    for i, day in enumerate(d["time"]):
        docs.append(
            f"Daily forecast for {place} on {day}: high {d['temperature_2m_max'][i]}°C, low {d['temperature_2m_min'][i]}°C, "
            f"total rain {d['precipitation_sum'][i]} mm, max rain probability {d['precipitation_probability_max'][i]}%, "
            f"max wind {d['wind_speed_10m_max'][i]} km/h.")
    df = hourly_df(fc)
    for start in (range(0, len(df), 6) if detailed else []):
        b = df.iloc[start:start + 6]
        docs.append(
            f"Forecast for {place} from {b.time.iloc[0]:%Y-%m-%d %H:%M} to {b.time.iloc[-1]:%Y-%m-%d %H:%M}: "
            f"temperature {b.temperature_2m.min():.1f}-{b.temperature_2m.max():.1f}°C, "
            f"rain probability up to {b.precipitation_probability.max():.0f}%, rain {b.precipitation.sum():.1f} mm, "
            f"average cloud cover {b.cloud_cover.mean():.0f}%, max wind {b.wind_speed_10m.max():.0f} km/h.")
    if sat is not None and len(sat):
        for day, g in sat.groupby(sat.time.str[:10]):
            docs.append(
                f"Satellite-derived solar radiation for {place} on {day}: peak {g.radiation.max():.0f} W/m2, "
                f"mean {g.radiation.mean():.0f} W/m2 (low values at midday indicate heavy cloud).")
    return docs
