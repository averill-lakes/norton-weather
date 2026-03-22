"""
Norton VT Weather Agent - Backend
Fetches from NOAA api.weather.gov and serves it to the frontend.
"""

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

LAT = 44.9897
LON = -71.7978
NOAA = "https://api.weather.gov"
HEADERS = {"User-Agent": "NortonVTWeatherAgent/1.0 (weather-agent@example.com)"}


def noaa(url):
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()

def c_to_f(c):
    return round((c * 9 / 5) + 32, 1) if c is not None else None

def ms_to_mph(ms):
    return round(ms * 2.23694, 1) if ms is not None else None


@app.route("/api/weather")
def weather():
    try:
        pts = noaa(f"{NOAA}/points/{LAT},{LON}")["properties"]
        gid, gx, gy = pts["gridId"], pts["gridX"], pts["gridY"]

        stations = noaa(f"{NOAA}/gridpoints/{gid}/{gx},{gy}/stations")
        station_id = stations["features"][0]["properties"]["stationIdentifier"]

        obs    = noaa(f"{NOAA}/stations/{station_id}/observations/latest")["properties"]
        hourly = noaa(pts["forecastHourly"])["properties"]["periods"][:24]
        daily  = noaa(pts["forecast"])["properties"]["periods"]
        alerts = noaa(f"{NOAA}/alerts/active?point={LAT},{LON}")["features"]

        current = {
            "station":          station_id,
            "timestamp":        obs.get("timestamp"),
            "textDescription":  obs.get("textDescription"),
            "temperature_f":    c_to_f(obs.get("temperature", {}).get("value")),
            "temperature_c":    round(obs.get("temperature", {}).get("value") or 0, 1),
            "dewpoint_f":       c_to_f(obs.get("dewpoint", {}).get("value")),
            "humidity_pct":     round(obs.get("relativeHumidity", {}).get("value") or 0),
            "windDirection_deg":obs.get("windDirection", {}).get("value"),
            "windSpeed_mph":    ms_to_mph(obs.get("windSpeed", {}).get("value")),
            "windGust_mph":     ms_to_mph(obs.get("windGust", {}).get("value")),
            "visibility_km":    round((obs.get("visibility", {}).get("value") or 0) / 1000, 1),
            "pressure_hpa":     round((obs.get("seaLevelPressure", {}).get("value") or 0) / 100, 1),
        }

        return jsonify({
            "meta": {"gridId": gid, "gridX": gx, "gridY": gy, "station": station_id},
            "current": current,
            "hourly": [{"startTime": p["startTime"], "temperature": p["temperature"],
                        "temperatureUnit": p["temperatureUnit"], "shortForecast": p["shortForecast"],
                        "windSpeed": p["windSpeed"], "windDirection": p["windDirection"]} for p in hourly],
            "daily":  [{"name": p["name"], "isDaytime": p["isDaytime"], "temperature": p["temperature"],
                        "temperatureUnit": p["temperatureUnit"], "windSpeed": p["windSpeed"],
                        "windDirection": p["windDirection"], "shortForecast": p["shortForecast"],
                        "detailedForecast": p["detailedForecast"]} for p in daily],
            "alerts": [{"event": a["properties"].get("event"), "headline": a["properties"].get("headline"),
                        "description": a["properties"].get("description"),
                        "expires": a["properties"].get("expires")} for a in alerts],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
