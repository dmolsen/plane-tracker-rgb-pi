#!/usr/bin/python3
from flask import Flask, render_template, jsonify, send_from_directory
import json
import os

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

# JSON flight logs (stored outside /web)
CLOSEST_FILE = os.path.join(BASE_DIR, "close.txt")
FARTHEST_FILE = os.path.join(BASE_DIR, "farthest.txt")
RECENT_FILE = os.path.join(BASE_DIR, "recent_flights.json")

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Could not load {path}: {e}")
        return default


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


# Serve PNG map snapshots from /web/static/maps/
@app.get("/maps/<path:filename>")
def maps(filename):
    maps_dir = os.path.join(WEB_DIR, "static/maps")
    return send_from_directory(maps_dir, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
