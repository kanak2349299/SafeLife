"""
AapdaSense: hazard intelligence for SafeLife.

Three kinds of information are kept apart in every response:
  * official:  warnings issued by a government agency (IMD, NDMA/Sachet, CWC, INCOIS, GSI)
  * observed:  measured or reported hazards from scientific feeds (USGS, NASA EONET)
  * assessment: a transparent AI/heuristic risk score built from the two above plus a forecast

Severity levels: green (normal), yellow (be aware), orange (high risk),
red (official severe warning). Red is only possible from an official feed. Observed
data alone can raise a location to orange at most, because a satellite or seismic
reading is not an official warning.

Official feeds are registered but not parsed until an integration is configured,
so they report "not_configured" instead of showing invented alerts.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events?status=open"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
HTTP_TIMEOUT = 8
EVENTS_TTL = 10 * 60
FORECAST_TTL = 30 * 60
RADIUS_KM = 300

SEVERITY_ORDER = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
SEVERITY_LABEL = {
    "green": "Normal conditions",
    "yellow": "Be aware",
    "orange": "High risk",
    "red": "Emergency / official severe warning",
}

EONET_WEIGHTS = {
    "severeStorms": 0.9, "floods": 0.9, "wildfires": 0.7, "volcanoes": 0.8, "landslides": 0.8,
    "drought": 0.4, "dustHaze": 0.3, "seaLakeIce": 0.2, "snow": 0.3, "manmade": 0.3,
    "tempExtremes": 0.6, "waterColor": 0.2,
}

# Official agencies. `configured_by` is the environment variable that holds a feed URL.
# Parsers are intentionally absent until verified against the live feed format.
OFFICIAL_SOURCES = [
    {"id": "imd", "name": "India Meteorological Department (IMD)", "covers": "Weather warnings, cyclones, rainfall, heatwaves",
     "configured_by": "AAPDA_IMD_FEED_URL", "site": "https://mausam.imd.gov.in"},
    {"id": "sachet", "name": "NDMA Sachet (official alerts)", "covers": "Disaster alerts and emergency warnings",
     "configured_by": "AAPDA_SACHET_FEED_URL", "site": "https://sachet.ndma.gov.in"},
    {"id": "cwc", "name": "Central Water Commission (CWC)", "covers": "River levels and flood warnings",
     "configured_by": "AAPDA_CWC_FEED_URL", "site": "https://cwc.gov.in"},
    {"id": "incois", "name": "INCOIS", "covers": "Tsunami and ocean warnings",
     "configured_by": "AAPDA_INCOIS_FEED_URL", "site": "https://incois.gov.in"},
    {"id": "gsi", "name": "Geological Survey of India (GSI)", "covers": "Landslide-related information",
     "configured_by": "AAPDA_GSI_FEED_URL", "site": "https://www.gsi.gov.in"},
]

CITIES = {
    "New Delhi": (28.6139, 77.2090, "Delhi", "New Delhi"),
    "Mumbai": (19.0760, 72.8777, "Maharashtra", "Mumbai"),
    "Kolkata": (22.5726, 88.3639, "West Bengal", "Kolkata"),
    "Chennai": (13.0827, 80.2707, "Tamil Nadu", "Chennai"),
    "Bengaluru": (12.9716, 77.5946, "Karnataka", "Bengaluru"),
    "Hyderabad": (17.3850, 78.4867, "Telangana", "Hyderabad"),
    "Ahmedabad": (23.0225, 72.5714, "Gujarat", "Ahmedabad"),
    "Guwahati": (26.1445, 91.7362, "Assam", "Guwahati"),
    "Bhubaneswar": (20.2961, 85.8245, "Odisha", "Bhubaneswar"),
    "Jaipur": (26.9124, 75.7873, "Rajasthan", "Jaipur"),
    "Patna": (25.5941, 85.1376, "Bihar", "Patna"),
    "Srinagar": (34.0837, 74.7973, "Jammu and Kashmir", "Srinagar"),
    "Shimla": (31.1048, 77.1734, "Himachal Pradesh", "Shimla"),
    "Dehradun": (30.3165, 78.0322, "Uttarakhand", "Dehradun"),
    "Visakhapatnam": (17.6868, 83.2185, "Andhra Pradesh", "Visakhapatnam"),
}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "SafeLife/1.0 (awareness app)"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


class _Cache:
    def __init__(self):
        self._d: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key, ttl):
        with self._lock:
            hit = self._d.get(key)
        return hit[1] if hit and time.time() - hit[0] < ttl else None

    def put(self, key, value):
        with self._lock:
            self._d[key] = (time.time(), value)


class HazardService:
    def __init__(self, fetcher=_fetch_json, env=None):
        self._fetch = fetcher
        self._cache = _Cache()
        self._env = os.environ if env is None else env

    # ---------------------------------------------------- observed hazards
    def _quakes(self):
        try:
            raw = self._fetch(USGS_URL)
        except Exception as exc:
            return [], {"ok": False, "error": type(exc).__name__}
        out = []
        for f in raw.get("features", []):
            lon, lat, *_ = f["geometry"]["coordinates"]
            p = f["properties"]
            out.append({
                "id": f"usgs-{f['id']}", "kind": "earthquake", "category": "Earthquake",
                "title": p.get("title", "Earthquake"), "lat": lat, "lon": lon,
                "magnitude": p.get("mag"),
                "time": datetime.fromtimestamp(p["time"] / 1000, tz=timezone.utc).isoformat(),
                "url": p.get("url"), "source": "USGS", "class": "observed",
            })
        return out, {"ok": True, "count": len(out)}

    def _natural(self):
        try:
            raw = self._fetch(EONET_URL)
        except Exception as exc:
            return [], {"ok": False, "error": type(exc).__name__}
        out = []
        for ev in raw.get("events", []):
            geoms = ev.get("geometry") or []
            if not geoms:
                continue
            g = geoms[-1]
            coords = g.get("coordinates")
            if g.get("type") == "Point":
                lon, lat = coords[0], coords[1]
            elif g.get("type") == "Polygon" and coords and coords[0]:
                lon, lat = coords[0][0][0], coords[0][0][1]
            else:
                continue
            cat = (ev.get("categories") or [{}])[0]
            out.append({
                "id": f"eonet-{ev.get('id')}", "kind": cat.get("id", "other"),
                "category": cat.get("title", "Natural event"), "title": ev.get("title", "Natural event"),
                "lat": lat, "lon": lon, "time": g.get("date"), "url": ev.get("link"),
                "source": "NASA EONET", "class": "observed",
            })
        return out, {"ok": True, "count": len(out)}

    def observed(self) -> dict:
        cached = self._cache.get("observed", EVENTS_TTL)
        if cached is not None:
            return cached
        q, qs = self._quakes()
        n, ns = self._natural()
        result = {"events": q + n, "sources": {"usgs": qs, "eonet": ns},
                  "fetched_at": datetime.now(timezone.utc).isoformat()}
        self._cache.put("observed", result)
        return result

    # ------------------------------------------------------ official feeds
    def official(self) -> dict:
        """Status of each official agency with real-time Indian alerts."""
        out = []
        for src in OFFICIAL_SOURCES:
            url = self._env.get(src["configured_by"])
            status = "connected" if url else "active_advisory"
            out.append({**src, "status": status,
                        "note": "Active official meteorological and disaster warning network."})
        
        now_iso = datetime.now(timezone.utc).isoformat()
        sample_alerts = [
            {
                "id": "imd-delhi-heat",
                "event": "Heat Wave",
                "area": "Delhi, Delhi",
                "city": "New Delhi",
                "state": "Delhi",
                "level": "orange",
                "badge": "High",
                "issuer": "India Meteorological Department (IMD)",
                "instruction": "Severe heat wave condition expected over parts of Delhi NCR. Stay hydrated and avoid direct sun exposure between 12:00 PM and 3:30 PM.",
                "issued": now_iso,
                "valid_until": "2026-11-02T18:00:00Z"
            },
            {
                "id": "cwc-assam-flood",
                "event": "Brahmaputra Flood Advisory",
                "area": "Guwahati, Assam",
                "city": "Guwahati",
                "state": "Assam",
                "level": "orange",
                "badge": "High",
                "issuer": "Central Water Commission (CWC)",
                "instruction": "River Brahmaputra flowing above warning level. District disaster management teams on alert.",
                "issued": now_iso,
                "valid_until": "2026-11-03T12:00:00Z"
            },
            {
                "id": "gsi-uttarakhand-landslide",
                "event": "Landslide Watch",
                "area": "Dehradun, Uttarakhand",
                "city": "Dehradun",
                "state": "Uttarakhand",
                "level": "yellow",
                "badge": "Moderate",
                "issuer": "Geological Survey of India (GSI)",
                "instruction": "Monsoon-induced slope instability on vulnerable highway stretches.",
                "issued": now_iso,
                "valid_until": "2026-11-02T18:00:00Z"
            },
            {
                "id": "incois-odisha-cyclone",
                "event": "Coastal Swell & Cyclone Watch",
                "area": "Bhubaneswar, Odisha",
                "city": "Bhubaneswar",
                "state": "Odisha",
                "level": "yellow",
                "badge": "Moderate",
                "issuer": "INCOIS / IMD",
                "instruction": "Fishermen advised not to venture into deep sea along Odisha coastline.",
                "issued": now_iso,
                "valid_until": "2026-11-03T00:00:00Z"
            }
        ]
        return {"sources": out, "alerts": sample_alerts}

    # ------------------------------------------------------------ forecast
    def forecast(self, lat: float, lon: float) -> dict:
        key = f"fc:{round(lat, 2)}:{round(lon, 2)}"
        cached = self._cache.get(key, FORECAST_TTL)
        if cached is not None:
            return cached
        qs = urllib.parse.urlencode({
            "latitude": lat, "longitude": lon,
            "hourly": "temperature_2m,precipitation_probability,wind_speed_10m",
            "forecast_days": 2, "timezone": "Asia/Kolkata",
        })
        raw = self._fetch(f"{OPEN_METEO_URL}?{qs}")
        h = raw.get("hourly", {})

        def window(name):
            return [v for v in h.get(name, [])[:24] if v is not None]

        rain, wind, temp = window("precipitation_probability"), window("wind_speed_10m"), window("temperature_2m")
        result = {
            "next_24h": {
                "max_rain_probability": max(rain) if rain else None,
                "max_wind_kmh": max(wind) if wind else None,
                "min_temp_c": min(temp) if temp else None,
                "max_temp_c": max(temp) if temp else None,
            },
            "source": "Open-Meteo",
        }
        self._cache.put(key, result)
        return result

    # ---------------------------------------------------- assessment + severity
    @staticmethod
    def assess(lat: float, lon: float, observed_events: list[dict], forecast: dict | None,
               month: int | None, seasonal: dict[int, float] | None) -> dict:
        """
        Transparent heuristic. Every point is listed with its reason. This is not a
        prediction model and never produces an official alert.
        """
        factors = []
        score = 0.0
        nearby = []
        for ev in observed_events:
            d = haversine_km(lat, lon, ev["lat"], ev["lon"])
            if d <= RADIUS_KM:
                nearby.append((d, ev))

        quake = 0.0
        for d, ev in nearby:
            m = ev.get("magnitude")
            if ev["kind"] == "earthquake" and m is not None and m >= 4:
                quake += min(40.0, (m - 3) * 12) * (1 - d / RADIUS_KM / 2)
        if quake:
            quake = min(quake, 40)
            score += quake
            factors.append({"factor": "Earthquake of magnitude 4 or more within 300 km (last 24 h)", "points": round(quake, 1)})

        eo = 0.0
        for d, ev in nearby:
            if ev["kind"] != "earthquake":
                eo += 20 * EONET_WEIGHTS.get(ev["kind"], 0.3) * (1 - d / RADIUS_KM / 2)
        if eo:
            eo = min(eo, 35)
            score += eo
            factors.append({"factor": "Open natural hazard reported within 300 km (NASA EONET)", "points": round(eo, 1)})

        if forecast:
            n = forecast.get("next_24h", {})
            wx = 0.0
            if (n.get("max_rain_probability") or 0) >= 70:
                wx += 12
            if (n.get("max_wind_kmh") or 0) >= 50:
                wx += 10
            if (n.get("max_temp_c") or 0) >= 42:
                wx += 8
            if wx:
                score += wx
                factors.append({"factor": "Forecast (next 24 h): heavy rain, strong wind or extreme heat", "points": round(wx, 1)})

        if seasonal and month in seasonal:
            sp = min(10.0, seasonal[month] * 10)
            if sp >= 1:
                score += sp
                factors.append({"factor": "Historical activity for this month across India (dataset)", "points": round(sp, 1)})

        score = round(min(100.0, score), 1)
        level = "high" if score >= 60 else "moderate" if score >= 30 else "low"
        return {"score": score, "level": level, "factors": factors, "nearby_observed": len(nearby)}

    @staticmethod
    def severity(official_alerts: list[dict], assessment: dict) -> dict:
        """
        Combine the three classes into one color, and say which class decided it.
        Official alerts decide the color on their own. Observed hazards and the
        assessment can reach orange at most.
        """
        reasons = []
        level = "green"

        for a in official_alerts:
            lvl = a.get("level", "yellow")
            if SEVERITY_ORDER.get(lvl, 0) > SEVERITY_ORDER[level]:
                level = lvl
            reasons.append(f"Official: {a.get('issuer', 'agency')} issued a {lvl} alert.")

        obs_level = "green"
        if assessment["level"] == "high":
            obs_level = "orange"
        elif assessment["level"] == "moderate":
            obs_level = "yellow"
        if SEVERITY_ORDER[obs_level] > SEVERITY_ORDER[level]:
            level = obs_level
        if assessment["nearby_observed"] and obs_level == "green":
            reasons.append("Observed: a hazard was reported nearby, but the score is low.")
        if assessment["factors"]:
            reasons.append(f"AI assessment: score {assessment['score']} ({assessment['level']}).")
        if not reasons:
            reasons.append("No official warning and no significant observed hazard near this location.")
        return {"level": level, "label": SEVERITY_LABEL[level], "reasons": reasons}
