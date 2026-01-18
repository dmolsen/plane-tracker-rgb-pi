#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime

from FlightRadar24.api import FlightRadar24API

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGO_DIR_CANDIDATES = [
    os.path.abspath(os.path.join(BASE_DIR, "..", "logos")),
    os.path.expanduser(os.path.join("~", "logos")),
]
WEB_LOGO_EXTS = ("png", "jpg", "jpeg", "svg")
LOGO_FETCH_LOG = os.path.join(BASE_DIR, "logo_fetch.log")

DATA_FILES = [
    os.path.join(BASE_DIR, "close.txt"),
    os.path.join(BASE_DIR, "farthest.txt"),
    os.path.join(BASE_DIR, "recent_flights.json"),
]

BLANK_FIELDS = {"", "N/A", "NONE", None}


def _log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOGO_FETCH_LOG, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} {message}\n")
    except Exception:
        pass


def _select_logo_dir():
    for base in LOGO_DIR_CANDIDATES:
        if os.path.isdir(base):
            return base
    return LOGO_DIR_CANDIDATES[-1]


def _web_logo_exists(icao: str, base: str):
    for ext in WEB_LOGO_EXTS:
        if os.path.isfile(os.path.join(base, f"{icao}--web.{ext}")):
            return True
    return False


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
    api = FlightRadar24API()
    logo_dir = _select_logo_dir()
    os.makedirs(logo_dir, exist_ok=True)

    entries = []
    for path in DATA_FILES:
        entries.extend(_load_entries(path))

    codes = _extract_codes(entries)
    if not codes:
        print("No airline codes found.")
        return

    for icao, iata in codes:
        if _web_logo_exists(icao, logo_dir):
            continue
        try:
            result = api.get_airline_logo(iata or icao, icao)
        except Exception:
            _log(f"LOGO_FAIL icao={icao} iata={iata or '-'} error=exception")
            continue

        if not result:
            _log(f"LOGO_MISS icao={icao} iata={iata or '-'}")
            continue

        content, ext = result
        if not content or not ext:
            _log(f"LOGO_BAD icao={icao} iata={iata or '-'}")
            continue

        ext = ext.lower().split("?", 1)[0]
        filename = f"{icao}--web.{ext}"
        path = os.path.join(logo_dir, filename)
        try:
            with open(path, "wb") as f:
                f.write(content)
            _log(f"LOGO_OK icao={icao} iata={iata or '-'} file={filename} size={len(content)}")
        except Exception:
            _log(f"LOGO_WRITE_FAIL icao={icao} iata={iata or '-'} file={filename}")
        time.sleep(1)


if __name__ == "__main__":
    main()
