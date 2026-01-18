#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGO_DIR_CANDIDATES = [
    os.path.abspath(os.path.join(BASE_DIR, "..", "logos")),
    os.path.expanduser(os.path.join("~", "logos")),
]
WEB_LOGO_EXTS = ("png", "jpg", "jpeg", "svg")

DATA_FILES = [
    os.path.join(BASE_DIR, "close.txt"),
    os.path.join(BASE_DIR, "farthest.txt"),
    os.path.join(BASE_DIR, "recent_flights.json"),
]

BLANK_FIELDS = {"", "N/A", "NONE", None}

PRIMARY_LOGO_URL = "https://cdn.flightradar.com/assets/airlines/logotypes/{}_{}.png"
ALT_LOGO_URL = "https://www.flightradar.com/static/images/data/operators/{}_logo0.png"
FLIGHTAWARE_LOGO_URL = "https://www.flightaware.com/images/airline_logos/180px/{}.png"


def _load_entries(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _extract_codes(entries):
    codes = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        owner_icao = entry.get("owner_icao")
        owner_iata = entry.get("owner_iata")
        icao = str(owner_icao or "").upper()
        iata = str(owner_iata or "").upper()
        if icao in BLANK_FIELDS:
            continue
        if iata in BLANK_FIELDS:
            iata = ""
        codes.add((icao, iata))
    return sorted(codes)


def main():
    entries = []
    for path in DATA_FILES:
        entries.extend(_load_entries(path))

    codes = _extract_codes(entries)
    if not codes:
        print("No airline codes found.")
        return

    for icao, iata in codes:
        primary = PRIMARY_LOGO_URL.format(iata or icao, icao)
        alt = ALT_LOGO_URL.format(icao)
        flightaware = FLIGHTAWARE_LOGO_URL.format(icao)
        print(f"{icao} {iata or '-'}")
        print(f"  {primary}")
        print(f"  {alt}")
        print(f"  {flightaware}")


if __name__ == "__main__":
    main()
