"""
Norton VT Weather Agent - Backend
- Live weather from api.weather.gov
- Historical precipitation from NOAA Climate Data Online (CDO)
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

LAT = 44.9897
LON = -71.7978
NOAA = "https://api.weather.gov"
NOAA_HEADERS = {"User-Agent": "NortonVTWeatherAgent/1.0 (weather-agent@example.com)"}

# NOAA CDO - Newport VT / Island Pond area stations
CDO_BASE    = "https://www.ncei.noaa.gov/cdo-web/api/v2"
CDO_STATION = "GHCND:USC00430193"  # Lake View Store, Norton VT
CDO_TOKEN   = os.environ.get("CDO_TOKEN", "")


# ── Live weather helpers ───────────────────────────────────────────────────────

def noaa_get(url):
    r = requests.get(url, headers=NOAA_HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()

def c_to_f(c):
    return round((c * 9 / 5) + 32, 1) if c is not None else None

def ms_to_mph(ms):
    return round(ms * 2.23694, 1) if ms is not None else None


# ── CDO helpers ───────────────────────────────────────────────────────────────

def cdo_get(endpoint, params):
    r = requests.get(f"{CDO_BASE}/{endpoint}",
                     headers={"token": CDO_TOKEN},
                     params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def compute_rolling(records, days):
    values = [r["prcp_in"] for r in records]
    out = []
    for i in range(len(records)):
        window = [v for v in values[max(0, i - days + 1):i + 1] if v is not None]
        out.append(round(sum(window), 2) if window else None)
    return out

def find_storm_events(records, threshold_in):
    return sorted(
        [r for r in records if r["prcp_in"] is not None and r["prcp_in"] >= threshold_in],
        key=lambda x: x["prcp_in"], reverse=True
    )[:50]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/weather")
def weather():
    try:
        pts = noaa_get(f"{NOAA}/points/{LAT},{LON}")["properties"]
        gid, gx, gy = pts["gridId"], pts["gridX"], pts["gridY"]
        stations   = noaa_get(f"{NOAA}/gridpoints/{gid}/{gx},{gy}/stations")
        station_id = stations["features"][0]["properties"]["stationIdentifier"]
        obs    = noaa_get(f"{NOAA}/stations/{station_id}/observations/latest")["properties"]
        hourly = noaa_get(pts["forecastHourly"])["properties"]["periods"][:24]
        daily  = noaa_get(pts["forecast"])["properties"]["periods"]
        alerts = noaa_get(f"{NOAA}/alerts/active?point={LAT},{LON}")["features"]

        current = {
            "station":           station_id,
            "timestamp":         obs.get("timestamp"),
            "textDescription":   obs.get("textDescription"),
            "temperature_f":     c_to_f(obs.get("temperature", {}).get("value")),
            "temperature_c":     round(obs.get("temperature", {}).get("value") or 0, 1),
            "dewpoint_f":        c_to_f(obs.get("dewpoint", {}).get("value")),
            "humidity_pct":      round(obs.get("relativeHumidity", {}).get("value") or 0),
            "windDirection_deg": obs.get("windDirection", {}).get("value"),
            "windSpeed_mph":     ms_to_mph(obs.get("windSpeed", {}).get("value")),
            "windGust_mph":      ms_to_mph(obs.get("windGust", {}).get("value")),
            "visibility_km":     round((obs.get("visibility", {}).get("value") or 0) / 1000, 1),
            "pressure_hpa":      round((obs.get("seaLevelPressure", {}).get("value") or 0) / 100, 1),
        }

        return jsonify({
            "meta":    {"gridId": gid, "gridX": gx, "gridY": gy, "station": station_id},
            "current": current,
            "hourly":  [{"startTime": p["startTime"], "temperature": p["temperature"],
                         "temperatureUnit": p["temperatureUnit"], "shortForecast": p["shortForecast"],
                         "windSpeed": p["windSpeed"], "windDirection": p["windDirection"]} for p in hourly],
            "daily":   [{"name": p["name"], "isDaytime": p["isDaytime"], "temperature": p["temperature"],
                         "temperatureUnit": p["temperatureUnit"], "windSpeed": p["windSpeed"],
                         "windDirection": p["windDirection"], "shortForecast": p["shortForecast"],
                         "detailedForecast": p["detailedForecast"]} for p in daily],
            "alerts":  [{"event": a["properties"].get("event"), "headline": a["properties"].get("headline"),
                         "description": a["properties"].get("description"),
                         "expires": a["properties"].get("expires")} for a in alerts],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/historical")
def historical():
    """
    Query params:
      start_date  YYYY-MM-DD  (default: 1 year ago)
      end_date    YYYY-MM-DD  (default: today)
      threshold   inches      (default: 0.5 — storm event flag)
    """
    try:
        end_date   = request.args.get("end_date",   datetime.today().strftime("%Y-%m-%d"))
        start_date = request.args.get("start_date", (datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d"))
        threshold  = float(request.args.get("threshold", 0.5))

        # Page through CDO results (max 1000 per call)
        all_results, offset = [], 1
        while True:
            data    = cdo_get("data", {"datasetid": "GHCND", "stationid": CDO_STATION,
                                       "startdate": start_date, "enddate": end_date,
                                       "datatypeid": "PRCP,TMAX,TMIN,SNOW,SNWD",
                                       "units": "standard", "limit": 1000, "offset": offset})
            results = data.get("results", [])
            all_results.extend(results)
            count = data.get("metadata", {}).get("resultset", {}).get("count", 0)
            if offset + 1000 > count:
                break
            offset += 1000

        # Pivot to one record per date
        daily_map = {}
        for r in all_results:
            date  = r["date"][:10]
            dtype = r["datatype"]
            val   = r["value"]
            if date not in daily_map:
                daily_map[date] = {"date": date, "prcp_in": None, "tmax_f": None,
                                   "tmin_f": None, "snow_in": None, "snow_depth_in": None}
            if   dtype == "PRCP": daily_map[date]["prcp_in"]       = round(val, 2)
            elif dtype == "TMAX": daily_map[date]["tmax_f"]        = round(val, 1)
            elif dtype == "TMIN": daily_map[date]["tmin_f"]        = round(val, 1)
            elif dtype == "SNOW": daily_map[date]["snow_in"]       = round(val, 1)
            elif dtype == "SNWD": daily_map[date]["snow_depth_in"] = round(val, 1)

        records = sorted(daily_map.values(), key=lambda x: x["date"])

        # Rolling totals
        r3  = compute_rolling(records, 3)
        r7  = compute_rolling(records, 7)
        r14 = compute_rolling(records, 14)
        for i, rec in enumerate(records):
            rec["rolling3_in"]  = r3[i]
            rec["rolling7_in"]  = r7[i]
            rec["rolling14_in"] = r14[i]

        prcp_vals = [r["prcp_in"] for r in records if r["prcp_in"] is not None]
        summary = {
            "start_date":      start_date,
            "end_date":        end_date,
            "station":         CDO_STATION,
            "total_days":      len(records),
            "rainy_days":      len([v for v in prcp_vals if v > 0]),
            "total_precip_in": round(sum(prcp_vals), 2) if prcp_vals else 0,
            "max_daily_in":    round(max(prcp_vals), 2) if prcp_vals else 0,
            "avg_daily_in":    round(sum(prcp_vals) / len(prcp_vals), 3) if prcp_vals else 0,
            "storm_threshold": threshold,
            "storm_count":     len([v for v in prcp_vals if v >= threshold]),
        }

        return jsonify({
            "summary":      summary,
            "records":      records,
            "storm_events": find_storm_events(records, threshold),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stations")
def stations():
    """Find CDO stations near Norton VT."""
    try:
        data = cdo_get("stations", {"datasetid": "GHCND",
                                    "extent": "44.7,-72.1,45.2,-71.5", "limit": 20})
        return jsonify(data.get("results", []))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
