#!/usr/bin/python3
from flask import Flask, render_template, jsonify, send_from_directory
import json
import os
import subprocess
import re

# /web is the folder that this file lives in
WEB_DIR = os.path.dirname(__file__)
BASE_DIR = os.path.abspath(os.path.join(WEB_DIR, ".."))

app = Flask(
    __name__,
    template_folder=os.path.join(WEB_DIR, "templates"),
    static_folder=os.path.join(WEB_DIR, "static")
)

from datetime import datetime, timezone
@app.template_filter("datetime")
def unix_to_datetime(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc)

LOGO_DIR_CANDIDATES = [
    os.path.abspath(os.path.join(BASE_DIR, "..", "logos")),
    os.path.expanduser(os.path.join("~", "logos")),
]


def offset_badge_class(distance):
    try:
        d = float(distance)
    except Exception:
        return "bg-secondary"
    if d <= 2:
        return "bg-success"
    if d <= 8:
        return "bg-primary"
    if d <= 20:
        return "bg-secondary"
    return "bg-dark"


def route_progress(distance_origin, distance_destination):
    try:
        o = float(distance_origin)
        d = float(distance_destination)
        total = o + d
        if total <= 0:
            return None
        pct = int(round((o / total) * 100))
        return max(0, min(100, pct))
    except Exception:
        return None


app.jinja_env.globals["offset_badge_class"] = offset_badge_class
app.jinja_env.globals["route_progress"] = route_progress


def _parse_timestamp(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        if value.lower() == "fixture":
            return None
        for fmt in ("%b %d %Y, %H:%M:%S", "%b %d %Y, %I:%M:%S %p"):
            try:
                return datetime.strptime(value, fmt)
            except Exception:
                continue
    return None


def time_ago(value):
    dt = _parse_timestamp(value)
    if not dt:
        return None
    delta = datetime.now() - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr ago"
    days = hours // 24
    return f"{days} d ago"


def _logo_path_for(icao):
    if not icao:
        return None
    filename = f"{icao}.png"
    for base in LOGO_DIR_CANDIDATES:
        path = os.path.join(base, filename)
        if os.path.isfile(path):
            return base, filename
    return None


def airline_logo_url(flight):
    icao = flight.get("owner_icao") if isinstance(flight, dict) else getattr(flight, "owner_icao", None)
    found = _logo_path_for(icao)
    if not found:
        return None
    _, filename = found
    return f"/logos/{filename}"


app.jinja_env.globals["time_ago"] = time_ago
app.jinja_env.globals["airline_logo_url"] = airline_logo_url

# JSON flight logs (stored outside /web)
CLOSEST_FILE = os.path.join(BASE_DIR, "close.txt")
FARTHEST_FILE = os.path.join(BASE_DIR, "farthest.txt")
RECENT_FILE = os.path.join(BASE_DIR, "recent_flights.json")

SCREEN_STATE_FILE = os.path.join(BASE_DIR, "screen_state.json")

def read_screen_state():
    try:
        with open(SCREEN_STATE_FILE, "r") as f:
            return json.load(f).get("screen", "on")
    except Exception:
        return "on"

def write_screen_state(state):
    with open(SCREEN_STATE_FILE, "w") as f:
        json.dump({"screen": state}, f)

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Could not load {path}: {e}")
        return default

# network checking
def _run(cmd):
    return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()

def get_wlan_ip():
    try:
        out = _run(["ip", "-4", "addr", "show", "wlan0"])
        for line in out.splitlines():
            if "inet " in line:
                return line.split()[1].split("/")[0]
    except Exception:
        return None
    return None

def get_default_gateway():
    try:
        out = _run(["ip", "route", "show", "default"])
        # default via 192.168.1.1 dev wlan0 ...
        m = re.search(r"default via (\S+)", out)
        return m.group(1) if m else None
    except Exception:
        return None

def get_wifi_ssid():
    try:
        out = _run(["iw", "dev", "wlan0", "link"])
        # Look for "SSID: <name>"
        for line in out.splitlines():
            if line.strip().startswith("SSID:"):
                return line.split("SSID:", 1)[1].strip()
        if "Not connected." in out:
            return None
    except Exception:
        return None
    return None

def dns_ok(domain="api.flightradar24.com"):
    try:
        _run(["getent", "hosts", domain])
        return True
    except Exception:
        return False


@app.get("/")
def index():
    # Load JSON data
    recent = load_json(RECENT_FILE, [])
    closest = load_json(CLOSEST_FILE, [])
    farthest = load_json(FARTHEST_FILE, [])

    # Pick the top entries for each category
    current_recent = recent[0] if recent else None
    current_closest = closest[0] if closest else None
    current_farthest = farthest[0] if farthest else None

    return render_template(
        "index.html",
        recent=current_recent,
        closest=current_closest,
        farthest=current_farthest
    )


@app.get("/closest/json")
def closest_json():
    return jsonify(load_json(CLOSEST_FILE, {}))


@app.get("/farthest/json")
def farthest_json():
    return jsonify(load_json(FARTHEST_FILE, []))


@app.get("/recent/list")
def recent_list():
    recent_flights = load_json(RECENT_FILE, [])
    return render_template("recent_list.html", title="Most Recent Flights", flights=recent_flights)


@app.get("/closest/list")
def closest_list():
    closest_flights = load_json(CLOSEST_FILE, [])
    return render_template("closest_list.html", title="Closest Flights", flights=closest_flights)


@app.get("/farthest/list")
def farthest_list():
    farthest_flights = load_json(FARTHEST_FILE, [])
    return render_template("farthest_list.html", title="Farthest Flights", flights=farthest_flights)


@app.get("/recent")
def recent_page():
    return render_template("recent_map.html")


@app.get("/closest")
def closest_page():
    return render_template("closest_map.html")


@app.get("/farthest")
def farthest_page():
    return render_template("farthest_map.html")


@app.get("/screen")
def get_screen():
    return jsonify({"screen": read_screen_state()})


@app.get("/logos/<path:filename>")
def logos(filename):
    for base in LOGO_DIR_CANDIDATES:
        path = os.path.join(base, filename)
        if os.path.isfile(path):
            return send_from_directory(base, filename)
    return ("", 404)


@app.post("/screen/on")
def screen_on():
    write_screen_state("on")
    return jsonify({"screen": "on"})


@app.post("/screen/off")
def screen_off():
    write_screen_state("off")
    return jsonify({"screen": "off"})


@app.post("/screen/toggle")
def screen_toggle():
    current = read_screen_state()
    new_state = "off" if current == "on" else "on"
    write_screen_state(new_state)
    return jsonify({"screen": new_state})


# Serve PNG map snapshots from /web/static/maps/
@app.get("/maps/<path:filename>")
def maps(filename):
    maps_dir = os.path.join(WEB_DIR, "static/maps")
    return send_from_directory(maps_dir, filename)


@app.get("/api/network")
def api_network():
    hostname = os.uname().nodename
    ssid = get_wifi_ssid()
    ip = get_wlan_ip()
    gw = get_default_gateway()
    dns = dns_ok()

    return jsonify({
        "hostname": hostname,
        "mdns": f"{hostname}.local",
        "ssid": ssid,
        "ip": ip,
        "gateway": gw,
        "dns_ok": dns,
        "wifi_connected": ssid is not None,
        "has_ip": ip is not None,
        "has_gateway": gw is not None,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
