import os
import json
import math
from time import sleep
from threading import Thread, Lock
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

try:
    from PIL import Image, ImageEnhance, ImageOps
except Exception:
    Image = None

from FlightRadar24.api import FlightRadar24API
from requests.exceptions import ConnectionError
from urllib3.exceptions import NewConnectionError, MaxRetryError

from config import (
    DISTANCE_UNITS,
    CLOCK_FORMAT,
    MAX_FARTHEST,
    MAX_CLOSEST,
)

from setup import email_alerts
from web import map_generator, upload_helper

# Optional config values
try:
    from config import MIN_ALTITUDE
except (ImportError, ModuleNotFoundError, NameError):
    MIN_ALTITUDE = 0

try:
    from config import ZONE_HOME, LOCATION_HOME
    ZONE_DEFAULT = ZONE_HOME
    LOCATION_DEFAULT = LOCATION_HOME
except (ImportError, ModuleNotFoundError, NameError):
    ZONE_DEFAULT = {"tl_y": 41.904318, "tl_x": -87.647367,
                    "br_y": 41.851654, "br_x": -87.573027}
    LOCATION_DEFAULT = [41.882724, -87.623350]

# New: max recent flights to track
try:
    from config import MAX_RECENT_FLIGHTS
except (ImportError, ModuleNotFoundError, NameError):
    MAX_RECENT_FLIGHTS = 20

# Constants
RETRIES = 3
RATE_LIMIT_DELAY = 1
MAX_FLIGHT_LOOKUP = 5
MAX_ALTITUDE = 100000
EARTH_RADIUS_M = 3958.8
BLANK_FIELDS = ["", "N/A", "NONE"]

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
LOG_FILE = os.path.join(BASE_DIR, "close.txt")
LOG_FILE_FARTHEST = os.path.join(BASE_DIR, "farthest.txt")
LOG_FILE_RECENT = os.path.join(BASE_DIR, "recent_flights.json")
LOG_FILE_DEBUG = os.path.join(BASE_DIR, "debug_latest_flight.json")

FLAGS_DIR = os.path.join(BASE_DIR, "flags")
FIXTURE_FLAG_FILE = os.path.join(FLAGS_DIR, "force_fixture.on")
FIXTURE_DATA_FILE = os.path.join(BASE_DIR, "fixtures", "fixture_flights.json")

LOGO_DIR_CANDIDATES = [
    os.path.abspath(os.path.join(BASE_DIR, "..", "logos")),
    os.path.expanduser(os.path.join("~", "logos")),
]
WEB_LOGO_EXTS = ("png", "jpg", "jpeg", "svg")
FLIGHTAWARE_LOGO_URL = "https://www.flightaware.com/images/airline_logos/180px/{}.png"
LOGO_USER_AGENT = "Mozilla/5.0"
DISPLAY_LOGO_SIZE = (16, 16)

# --- Utility Functions ---

def safe_load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def safe_write_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def fixture_mode_enabled() -> bool:
    return os.path.exists(FIXTURE_FLAG_FILE)

def load_fixture_flights():
    data = safe_load_json(FIXTURE_DATA_FILE)
    # Ensure it's a list of dicts
    return data if isinstance(data, list) else []


def _select_logo_dir():
    for base in LOGO_DIR_CANDIDATES:
        if os.path.isdir(base):
            return base
    return LOGO_DIR_CANDIDATES[-1]


def _web_logo_exists(icao: str, base: str):
    for ext in WEB_LOGO_EXTS:
        path = os.path.join(base, f"{icao}--web.{ext}")
        if os.path.isfile(path):
            return True
    return False


def _write_display_logo(content: bytes, path: str):
    if Image is None:
        return
    try:
        from io import BytesIO
        with Image.open(BytesIO(content)) as img:
            img = img.convert("RGBA")
            img = img.resize(DISPLAY_LOGO_SIZE, Image.LANCZOS)
            background = Image.new("RGBA", DISPLAY_LOGO_SIZE, (255, 255, 255, 255))
            background.paste(img, (0, 0), img)
            flattened = background.convert("RGB")
            flattened = ImageOps.autocontrast(flattened)
            flattened = ImageEnhance.Contrast(flattened).enhance(1.4)
            flattened = ImageEnhance.Color(flattened).enhance(1.2)
            flattened.save(path, format="PNG")
    except Exception:
        pass

def ordinal(n: int):
    return f"{n}{'tsnrhtdd'[(n//10 % 10 != 1) * (n % 10 < 4) * n % 10::4]}"


def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1 = map(math.radians, (lat1, lon1))
    lat2, lon2 = map(math.radians, (lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    miles = EARTH_RADIUS_M * c
    return miles * 1.609 if DISTANCE_UNITS == "metric" else miles


def degrees_to_cardinal(deg):
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((deg + 22.5) / 45)
    return dirs[idx % 8]


def _parse_recent_timestamp(value):
    if not value:
        return datetime.min
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except Exception:
            return datetime.min
    if isinstance(value, str):
        for fmt in ("%b %d %Y, %H:%M:%S", "%b %d %Y, %I:%M:%S %p"):
            try:
                return datetime.strptime(value, fmt)
            except Exception:
                continue
    return datetime.min


def plane_bearing(flight, home=LOCATION_DEFAULT):
    lat1, lon1 = map(math.radians, home)
    lat2, lon2 = map(math.radians, (flight.latitude, flight.longitude))
    b = math.atan2(
        math.sin(lon2 - lon1) * math.cos(lat2),
        math.cos(lat1) * math.sin(lat2)
        - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    )
    return (math.degrees(b) + 360) % 360


def distance_from_flight_to_home(flight):
    return haversine(flight.latitude, flight.longitude, LOCATION_DEFAULT[0], LOCATION_DEFAULT[1])


def distance_to_point(flight, lat, lon):
    return haversine(flight.latitude, flight.longitude, lat, lon)

def is_recent_map_compatible(e):
    return all(
        e.get(k) is not None
        for k in (
            "plane_latitude",
            "plane_longitude",
            "origin_latitude",
            "origin_longitude",
            "destination_latitude",
            "destination_longitude",
        )
    )


def _trend_from_trail(trail, key, min_points=5, threshold=1):
    if not isinstance(trail, list):
        return None
    values = [p.get(key) for p in trail if isinstance(p, dict) and p.get(key) is not None]
    if len(values) < min_points:
        return None
    delta = values[0] - values[min_points - 1]
    if delta > threshold:
        return "up"
    if delta < -threshold:
        return "down"
    return "steady"

def build_flightaware_urls(entry):
    """
    Returns a dict with:
      - live: always present, points to the live flight page
      - history: optional, points to the history page if scheduled departure exists
    """
    urls = {}
    callsign = entry.get("callsign")
    if not callsign:
        return {"live": None, "history": None}

    # Live URL
    urls["live"] = f"https://www.flightaware.com/live/flight/{callsign}"

    # History URL (optional)
    origin_icao = entry.get("origin_icao")
    dest_icao = entry.get("destination_icao")
    dep_ts = entry.get("time_scheduled_departure")

    if origin_icao and dest_icao and dep_ts:
        try:
            dt = datetime.fromtimestamp(dep_ts, tz=timezone.utc)
            urls["history"] = (
                f"https://www.flightaware.com/live/flight/"
                f"{callsign}/history/"
            )
        except Exception:
            urls["history"] = None
    else:
        urls["history"] = None

    # Optional hint string
    if dep_ts:
        dt_local = datetime.fromtimestamp(dep_ts)  # local time
        urls["hint"] = dt_local.strftime("%b %d %Y %I:%M %p")
    else:
        urls["hint"] = "Scheduled departure unknown"

    return urls


# --- Closest Flights Logging ---

def log_flight_data(entry: dict):
    try:
        entry["timestamp"] = email_alerts.get_timestamp()
        lst = safe_load_json(LOG_FILE)
        callsigns = {f.get("callsign"): f for f in lst}
        new_call = entry.get("callsign")
        new_dist = entry.get("distance", float("inf"))
        notify = False

        if new_call in callsigns:
            idx = next(i for i, f in enumerate(lst) if f.get("callsign") == new_call)
            if new_dist < lst[idx].get("distance", float("inf")):
                lst[idx] = entry
            else:
                return
        else:
            lst.append(entry)

        lst.sort(key=lambda x: x.get("distance", float("inf")))
        top_n = lst[:MAX_CLOSEST]

        if new_call not in [f["callsign"] for f in top_n]:
            return

        rank = next(i + 1 for i, f in enumerate(top_n) if f["callsign"] == new_call)
        if new_call not in callsigns:
            notify = True

        safe_write_json(LOG_FILE, top_n)

        if notify:
            html = map_generator.generate_closest_map(top_n, filename="closest.html")
            url = upload_helper.upload_map_to_server(html)
            subject = f"New {ordinal(rank)} Closest Flight - {entry.get('callsign','Unknown')}"
            email_alerts.send_flight_summary(subject, entry, map_url=url)

    except Exception as e:
        print("Failed to log closest flight:", e)


# --- Farthest Flights Logging ---

def log_farthest_flight(entry: dict):
    try:
        d_o = entry.get("distance_origin", -1)
        d_d = entry.get("distance_destination", -1)
        if d_o < 0 and d_d < 0:
            return
        reason = "origin" if d_o >= d_d else "destination"
        far = d_o if reason == "origin" else d_d
        airport = entry.get(reason)
        if not airport:
            return

        entry["timestamp"] = email_alerts.get_timestamp()
        entry["reason"] = reason
        entry["farthest_value"] = far
        entry["_airport"] = airport

        lst = safe_load_json(LOG_FILE_FARTHEST)
        airport_map = {f["_airport"]: f for f in lst}
        existing = airport_map.get(airport)
        notify = False
        updated = False

        if existing:
            if entry["distance"] < existing.get("distance", 9e9):
                lst = [entry if f["_airport"] == airport else f for f in lst]
                updated = True
            else:
                return
        else:
            if len(lst) >= MAX_FARTHEST and far <= min(f["farthest_value"] for f in lst):
                return
            lst.append(entry)
            notify = True

        lst.sort(key=lambda x: x["farthest_value"], reverse=True)
        lst = lst[:MAX_FARTHEST]
        safe_write_json(LOG_FILE_FARTHEST, lst)

        if notify or updated:
            html = map_generator.generate_farthest_map(lst, filename="farthest.html")
        if notify:
            url = upload_helper.upload_map_to_server(html)
            rank = next(i for i, f in enumerate(lst) if f["_airport"] == airport) + 1
            cs = entry.get("callsign", "UNKNOWN")
            subject = f"{ordinal(rank)}-Farthest Flight ({reason}) - {cs}" if rank != 1 else f"New Farthest Flight ({reason}) - {cs}"
            email_alerts.send_flight_summary(subject, entry, reason, map_url=url)

    except Exception as e:
        print("Failed to log farthest flight:", e)

def write_debug_flight(raw_details, flight):
    try:
        debug = {
            "timestamp": email_alerts.get_timestamp(),
            "callsign": flight.callsign,
            "flight_object": {
                "latitude": flight.latitude,
                "longitude": flight.longitude,
                "altitude": flight.altitude,
                "origin_iata": flight.origin_airport_iata,
                "destination_iata": flight.destination_airport_iata,
                "airline_iata": flight.airline_iata,
                "airline_icao": flight.airline_icao,
            },
            "raw_api_response": raw_details
        }

        with open(LOG_FILE_DEBUG, "w", encoding="utf-8") as f:
            json.dump(debug, f, indent=4)

    except Exception as e:
        print("Failed to write debug flight:", e)


# --- Overhead Class ---

class Overhead:
    def __init__(self):
        self._api = FlightRadar24API()
        self._lock = Lock()
        self._data = []
        self._new_data = False
        self._processing = False
        self._logo_cache = set()

    # Public method
    def grab_data(self):
        Thread(target=self._grab).start()

    # Safe dict access
    def safe_get(self, d, *keys, default=None):
        """Safely get nested dict/list values."""
        for key in keys:
            if isinstance(d, dict):
                d = d.get(key, default)
            elif isinstance(d, list) and isinstance(key, int):
                if 0 <= key < len(d):
                    d = d[key]
                else:
                    return default
            else:
                return default
            if d is None:
                return default
        return d
    

    def trace_safe_get(d, *keys, default=None, label="TRACE"):
        cur = d
        print(f"\n{label}")
        for key in keys:
            print(f"  AT {type(cur).__name__} → getting {key}")
            if isinstance(cur, dict):
                cur = cur.get(key, default)
            elif isinstance(cur, list) and isinstance(key, int):
                cur = cur[key] if 0 <= key < len(cur) else default
            else:
                print("  ❌ type mismatch")
                return default
            print(f"    → {type(cur).__name__}: {str(cur)[:80]}")
            if cur is default or cur is None:
                print("  ❌ became None here")
                return default
        print("  ✅ SUCCESS")
        return cur


    def _cache_airline_logo(self, owner_iata: str, owner_icao: str, callsign: str):
        icao_candidates = []
        if owner_icao and str(owner_icao).upper() not in BLANK_FIELDS:
            icao_candidates.append(str(owner_icao).upper())
        if callsign:
            prefix = str(callsign).strip()[:3].upper()
            if prefix and prefix not in BLANK_FIELDS:
                icao_candidates.append(prefix)

        if not icao_candidates:
            return

        logo_dir = _select_logo_dir()
        os.makedirs(logo_dir, exist_ok=True)

        for icao in icao_candidates:
            if not icao or icao in self._logo_cache:
                continue
            if _web_logo_exists(icao, logo_dir):
                self._logo_cache.add(icao)
                continue

            url = FLIGHTAWARE_LOGO_URL.format(icao)
            try:
                req = Request(url, headers={"User-Agent": LOGO_USER_AGENT})
                with urlopen(req, timeout=10) as resp:
                    content = resp.read()
            except (HTTPError, URLError):
                self._logo_cache.add(icao)
                continue

            if not content:
                self._logo_cache.add(icao)
                continue

            filename = f"{icao}--web.png"
            path = os.path.join(logo_dir, filename)
            try:
                with open(path, "wb") as f:
                    f.write(content)
                _write_display_logo(content, os.path.join(logo_dir, f"{icao}.png"))
            except Exception:
                self._logo_cache.add(icao)
            break


    # Core data grab
    def _grab(self):
        with self._lock:
            self._new_data = False
            self._processing = True
        
        # --- FIXTURE MODE ---
        if fixture_mode_enabled():
            try:
                data = load_fixture_flights()

                # You can optionally sort and truncate like normal:
                data = data[:MAX_FLIGHT_LOOKUP]

                with self._lock:
                    self._new_data = True
                    self._processing = False
                    self._data = data
                return
            except Exception:
                with self._lock:
                    self._new_data = False
                    self._processing = False
                return

        data = []

        try:
            bounds = self._api.get_bounds(ZONE_DEFAULT)
            flights = self._api.get_flights(bounds=bounds)
            flights = [f for f in flights if MIN_ALTITUDE < f.altitude < MAX_ALTITUDE]
            flights.sort(key=lambda f: distance_from_flight_to_home(f))
            flights = flights[:MAX_FLIGHT_LOOKUP]

            for f in flights:
                retries = RETRIES
                while retries:
                    sleep(RATE_LIMIT_DELAY)
                    try:
                        d = self._api.get_flight_details(f)

                        write_debug_flight(d, f)

                        plane = self.safe_get(d, "aircraft", "model", "code", default="") or f.airline_icao or ""
                        airline = self.safe_get(d, "airline", "name", default="")

                        def clean_code(val):
                            if not val or str(val).upper() in BLANK_FIELDS:
                                return ""
                            return val

                        origin = clean_code(f.origin_airport_iata)
                        destination = clean_code(f.destination_airport_iata)
                        callsign = f.callsign or ""

                        t = self.safe_get(d, "time", default={})
                        time_sched_dep = self.safe_get(t, "scheduled", "departure")
                        time_sched_arr = self.safe_get(t, "scheduled", "arrival")
                        time_real_dep = self.safe_get(t, "real", "departure")
                        time_est_arr = self.safe_get(t, "estimated", "arrival")

                        o = self.safe_get(d, "airport", "origin")
                        origin_lat = self.safe_get(o, "position", "latitude")
                        origin_lon = self.safe_get(o, "position", "longitude")
                        origin_name = self.safe_get(o, "name", default=origin)

                        dest = self.safe_get(d, "airport", "destination")
                        dest_lat = self.safe_get(dest, "position", "latitude")
                        dest_lon = self.safe_get(dest, "position", "longitude")
                        dest_name = self.safe_get(dest, "name", default=destination)

                        dist_o = distance_to_point(f, origin_lat, origin_lon) if origin_lat else 0
                        dist_d = distance_to_point(f, dest_lat, dest_lon) if dest_lat else 0

                        entry = {
                            # --- Airline / Aircraft ---
                            "airline": airline,
                            "plane": plane,

                            # --- Callsign ---
                            "callsign": callsign,

                            # --- Origin airport ---
                            "origin": origin,  # IATA (existing behavior)
                            "origin_name": origin_name,
                            "origin_iata": self.safe_get(o, "code", "iata", default=origin),
                            "origin_icao": self.safe_get(o, "code", "icao"),
                            "origin_latitude": origin_lat,
                            "origin_longitude": origin_lon,

                            # --- Destination airport ---
                            "destination": destination,  # IATA (existing behavior)
                            "destination_name": dest_name,
                            "destination_iata": self.safe_get(dest, "code", "iata", default=destination),
                            "destination_icao": self.safe_get(dest, "code", "icao"),
                            "destination_latitude": dest_lat,
                            "destination_longitude": dest_lon,

                            # --- Plane position ---
                            "plane_latitude": f.latitude,
                            "plane_longitude": f.longitude,
                            "vertical_speed": f.vertical_speed,
                            "direction": degrees_to_cardinal(plane_bearing(f)),
                            "heading": (
                                self.safe_get(d, "trail", 0, "hd")
                                or getattr(f, "heading", None)
                            ),
                            "altitude": (
                                self.safe_get(d, "trail", 0, "alt")
                                or getattr(f, "altitude", None)
                            ),
                            "ground_speed": (
                                self.safe_get(d, "trail", 0, "spd")
                                or getattr(f, "ground_speed", None)
                                or getattr(f, "speed", None)
                            ),
                            "altitude_trend": _trend_from_trail(self.safe_get(d, "trail", default=[]), "alt", threshold=200),
                            "speed_trend": _trend_from_trail(self.safe_get(d, "trail", default=[]), "spd", threshold=10),

                            # --- Ownership ---
                            "owner_iata": f.airline_iata or "N/A",
                            "owner_icao": (
                                self.safe_get(d, "owner", "code", "icao", default="")
                                or f.airline_icao
                                or ""
                            ),

                            # --- Timing (UTC epoch seconds) ---
                            "time_scheduled_departure": time_sched_dep,
                            "time_scheduled_arrival": time_sched_arr,
                            "time_real_departure": time_real_dep,
                            "time_estimated_arrival": time_est_arr,

                            # --- Distances ---
                            "distance_origin": dist_o,
                            "distance_destination": dist_d,
                            "distance": distance_from_flight_to_home(f),

                            # --- Aircraft image (JetPhotos via FR24) ---
                            "aircraft_image": self.safe_get(
                                d, "aircraft", "images", "large", 0, "src"
                            ),
                            "aircraft_image_credit": self.safe_get(
                                d, "aircraft", "images", "large", 0, "copyright"
                            ),
                            "aircraft_image_source": self.safe_get(
                                d, "aircraft", "images", "large", 0, "source"
                            ),

                            # --- Metadata ---
                            "timestamp": email_alerts.get_timestamp(),

                        }

                        urls = build_flightaware_urls(entry)
                        entry["flightaware_live"] = urls["live"]
                        entry["flightaware_history"] = urls["history"]
                        entry["flightaware_hint"] = urls["hint"]

                        self._cache_airline_logo(
                            entry.get("owner_iata"),
                            entry.get("owner_icao"),
                            entry.get("callsign"),
                        )

                        # Append to current data
                        data.append(entry)

                        # Log closest/farthest flights
                        log_flight_data(entry)
                        log_farthest_flight(entry)

                        # --- New: Recent Flights JSON ---
                        recent_flights = safe_load_json(LOG_FILE_RECENT)
                        recent_map = {f.get("callsign"): f for f in recent_flights}
                        recent_map[entry["callsign"]] = entry
                        recent_flights = list(recent_map.values())
                        recent_flights.sort(key=lambda x: _parse_recent_timestamp(x.get("timestamp")), reverse=True)
                        recent_flights = recent_flights[:MAX_RECENT_FLIGHTS]
                        safe_write_json(LOG_FILE_RECENT, recent_flights)

                        break
                    except Exception:
                        retries -= 1

            recent_flights = safe_load_json(LOG_FILE_RECENT)
            map_entries = [e for e in recent_flights if is_recent_map_compatible(e)]
            if map_entries:
                map_generator.generate_recent_map(map_entries, filename="recent.html")

            with self._lock:
                self._new_data = True
                self._processing = False
                self._data = data

        except (ConnectionError, NewConnectionError, MaxRetryError):
            with self._lock:
                self._new_data = False
                self._processing = False

    # --- Properties ---
    @property
    def new_data(self):
        with self._lock:
            return self._new_data

    @property
    def processing(self):
        with self._lock:
            return self._processing

    @property
    def data(self):
        with self._lock:
            self._new_data = False
            return self._data

    @property
    def data_is_empty(self):
        return len(self._data) == 0


# --- Main ---
if __name__ == "__main__":
    o = Overhead()
    o.grab_data()
    while not o.new_data:
        print("processing...")
        sleep(1)
    print(o.data)
