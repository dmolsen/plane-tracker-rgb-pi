#!/usr/bin/env python3
import json
from datetime import datetime, timedelta

import requests

try:
    from config import TOMORROW_API_KEY, TEMPERATURE_LOCATION, TEMPERATURE_UNITS, FORECAST_DAYS
except Exception as exc:
    raise SystemExit(f"Config missing: {exc}")


BASE_URL = "https://api.tomorrow.io/v4"


def _print_response(label, resp):
    print(f"{label} status={resp.status_code}")
    try:
        data = resp.json()
        print(json.dumps(data, indent=2)[:2000])
    except Exception:
        print(resp.text[:2000])


def test_realtime():
    resp = requests.get(
        f"{BASE_URL}/weather/realtime",
        params={
            "location": TEMPERATURE_LOCATION,
            "units": TEMPERATURE_UNITS,
            "apikey": TOMORROW_API_KEY,
        },
        timeout=10,
    )
    _print_response("realtime", resp)


def test_forecast():
    now = datetime.utcnow()
    start = now + timedelta(hours=6)
    end = start + timedelta(days=int(FORECAST_DAYS))
    resp = requests.post(
        f"{BASE_URL}/timelines",
        headers={
            "Accept-Encoding": "gzip",
            "accept": "application/json",
            "content-type": "application/json",
        },
        params={"apikey": TOMORROW_API_KEY},
        json={
            "location": TEMPERATURE_LOCATION,
            "units": TEMPERATURE_UNITS,
            "fields": [
                "temperatureMin",
                "temperatureMax",
                "weatherCodeFullDay",
                "sunriseTime",
                "sunsetTime",
                "moonPhase",
            ],
            "timesteps": ["1d"],
            "startTime": start.isoformat(),
            "endTime": end.isoformat(),
        },
        timeout=10,
    )
    _print_response("forecast", resp)


if __name__ == "__main__":
    test_realtime()
    test_forecast()
