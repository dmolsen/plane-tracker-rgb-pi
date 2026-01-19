#!/usr/bin/env python3
import io
import json
import os
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGO_DIR_CANDIDATES = [
    os.path.abspath(os.path.join(BASE_DIR, "..", "logos")),
    os.path.expanduser(os.path.join("~", "logos")),
]

DATA_FILES = [
    os.path.join(BASE_DIR, "close.txt"),
    os.path.join(BASE_DIR, "farthest.txt"),
    os.path.join(BASE_DIR, "recent_flights.json"),
]

BLANK_FIELDS = {"", "N/A", "NONE", None}

PRIMARY_LOGO_URL = "https://cdn.flightradar.com/assets/airlines/logotypes/{}_{}.png"
ALT_LOGO_URL = "https://www.flightradar.com/static/images/data/operators/{}_logo0.png"
FLIGHTAWARE_LOGO_URL = "https://www.flightaware.com/images/airline_logos/180px/{}.png"
OUTPUT_EXT = "png"
DISPLAY_LOGO_SIZE = (16, 16)

try:
    from PIL import Image, ImageEnhance, ImageOps
except Exception:
    Image = None


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


def _select_logo_dir():
    for base in LOGO_DIR_CANDIDATES:
        if os.path.isdir(base):
            return base
    return LOGO_DIR_CANDIDATES[-1]


def _fetch_logo(url: str):
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp:
            return resp.read()
    except (HTTPError, URLError):
        return None


def _write_display_logo(content: bytes, path: str):
    if Image is None:
        print("Pillow not available; skipping 16x16 logo.")
        return
    try:
        with Image.open(io.BytesIO(content)) as img:
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
        print(f"  display logo resize failed: {path}")


def main():
    entries = []
    for path in DATA_FILES:
        entries.extend(_load_entries(path))

    codes = _extract_codes(entries)
    if not codes:
        print("No airline codes found.")
        return

    logo_dir = _select_logo_dir()
    os.makedirs(logo_dir, exist_ok=True)

    for icao, iata in codes:
        flightaware = FLIGHTAWARE_LOGO_URL.format(icao)
        web_filename = f"{icao}--web.{OUTPUT_EXT}"
        web_path = os.path.join(logo_dir, web_filename)
        display_path = os.path.join(logo_dir, f"{icao}.png")

        if os.path.isfile(web_path):
            print(f"{icao} {iata or '-'}")
            print(f"  {flightaware} (overwrite)")

        content = _fetch_logo(flightaware)
        if not content:
            print(f"{icao} {iata or '-'}")
            print(f"  {flightaware} (miss)")
            continue

        try:
            with open(web_path, "wb") as f:
                f.write(content)
            print(f"{icao} {iata or '-'}")
            print(f"  {flightaware} -> {web_filename}")
            _write_display_logo(content, display_path)
        except Exception:
            print(f"{icao} {iata or '-'}")
            print(f"  {flightaware} (write failed)")


if __name__ == "__main__":
    main()
