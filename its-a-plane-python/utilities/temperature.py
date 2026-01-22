from datetime import datetime, timedelta
import time
import logging
import socket

from requests import Session
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry

# Attempt to load config data
try:
    from config import TOMORROW_API_KEY
    from config import TEMPERATURE_UNITS
    from config import FORECAST_DAYS

except (ModuleNotFoundError, NameError, ImportError):
    # If there's no config data
    TOMORROW_API_KEY = None
    TEMPERATURE_UNITS = "metric"
    FORECAST_DAYS = 3

if TEMPERATURE_UNITS != "metric" and TEMPERATURE_UNITS != "imperial":
    TEMPERATURE_UNITS = "metric"

from config import TEMPERATURE_LOCATION

def is_dns_error(exc: Exception) -> bool:
    cause = exc
    while cause:
        if isinstance(cause, socket.gaierror):
            return True
        cause = cause.__cause__
    return False
    
_session = None

def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()

        retries = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=2,
            allowed_methods=["GET", "POST"],
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )

        adapter = HTTPAdapter(
            max_retries=retries,
            pool_connections=2,
            pool_maxsize=2,
        )

        _session.mount("https://", adapter)
        _session.mount("http://", adapter)

    return _session
    
# Weather API
TOMORROW_API_URL = "https://api.tomorrow.io/v4"

# Global variable to track last 429
_last_rate_limit_hit = None
_COOLDOWN_SECONDS = 300  # 5 minutes cooldown after 429
_last_cooldown_log = None

def grab_temperature_and_humidity():
    global _last_rate_limit_hit
    global _last_cooldown_log

    # Check if we are still in cooldown
    if _last_rate_limit_hit:
        elapsed = (datetime.now() - _last_rate_limit_hit).total_seconds()
        if elapsed < _COOLDOWN_SECONDS:
            remaining = int(_COOLDOWN_SECONDS - elapsed)
            if (_last_cooldown_log is None) or (_last_cooldown_log != remaining // 60):
                _last_cooldown_log = remaining // 60
                logging.warning(f"Skipping API call, cooldown in effect ({remaining}s left)")
            return None, None
        else:
            _last_rate_limit_hit = None  # reset cooldown
            _last_cooldown_log = None

    try:
        s = get_session()
        request = s.get(
            f"{TOMORROW_API_URL}/weather/realtime",
            params={
                "location": TEMPERATURE_LOCATION,
                "units": TEMPERATURE_UNITS,
                "apikey": TOMORROW_API_KEY
            },
            timeout=(5, 20)
        )

        if request.status_code == 429:
            logging.error("Rate limit reached, entering cooldown")
            _last_rate_limit_hit = datetime.now()
            return None, None

        request.raise_for_status()

        data = request.json().get("data", {}).get("values", {})
        temperature = data.get("temperature")
        humidity = data.get("humidity")

        if temperature is None or humidity is None:
            logging.error("Incomplete data from API")
            return None, None

        return temperature, humidity

    except (RequestException, ValueError) as e:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if is_dns_error(e):
            logging.error(f"[{timestamp}] DNS failure resolving api.tomorrow.io - will retry")
        else:
            logging.error(f"[{timestamp}] Temperature request failed: {e}")

        return None, None
        
# Global variable to track last 429 for forecast
_last_forecast_rate_limit_hit = None
_FORECAST_COOLDOWN_SECONDS = 300  # 5 minutes cooldown after 429
_FORECAST_MIN_INTERVAL_SECONDS = 900  # global throttle across callers
_last_forecast_cooldown_log = None
_last_forecast_success = None

def grab_forecast(tag="unknown"):
    """
    Fetch forecast data from Tomorrow.io with rate limit protection.
    Returns a list of intervals or [] on error.
    """
    global _last_forecast_rate_limit_hit
    global _last_forecast_cooldown_log
    global _last_forecast_success

    if _last_forecast_success:
        elapsed = (datetime.utcnow() - _last_forecast_success).total_seconds()
        if elapsed < _FORECAST_MIN_INTERVAL_SECONDS:
            remaining = int(_FORECAST_MIN_INTERVAL_SECONDS - elapsed)
            if (_last_forecast_cooldown_log is None) or (_last_forecast_cooldown_log != remaining // 60):
                _last_forecast_cooldown_log = remaining // 60
                logging.warning(f"[Forecast:{tag}] Throttled, last success {int(elapsed)}s ago")
            return []

    # Check if we are still in cooldown after a 429
    if _last_forecast_rate_limit_hit:
        elapsed = (datetime.utcnow() - _last_forecast_rate_limit_hit).total_seconds()
        if elapsed < _FORECAST_COOLDOWN_SECONDS:
            remaining = int(_FORECAST_COOLDOWN_SECONDS - elapsed)
            if (_last_forecast_cooldown_log is None) or (_last_forecast_cooldown_log != remaining // 60):
                _last_forecast_cooldown_log = remaining // 60
                logging.warning(f"[Forecast:{tag}] Skipping API call, cooldown in effect "
                                f"({remaining}s left)")
            return []
        else:
            _last_forecast_rate_limit_hit = None  # reset cooldown
            _last_forecast_cooldown_log = None

    current_time = datetime.utcnow()
    dt = current_time + timedelta(hours=6)

    try:
        s = get_session()
        resp = s.post(
            f"{TOMORROW_API_URL}/timelines",
            headers={
                "Accept-Encoding": "gzip",
                "accept": "application/json",
                "content-type": "application/json"
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
                    "moonPhase"
                ],
                "timesteps": ["1d"],
                "startTime": dt.isoformat(),
                "endTime": (dt + timedelta(days=int(FORECAST_DAYS))).isoformat()
            },
            timeout=(5, 20)
        )

        # Handle 429 rate limiting
        if resp.status_code == 429:
            logging.error(f"[Forecast:{tag}] Rate limit reached, entering cooldown")
            _last_forecast_rate_limit_hit = datetime.utcnow()
            return []

        resp.raise_for_status()

        data = resp.json().get("data", {})
        timelines = data.get("timelines", [])
        if not timelines:
            logging.error(f"[Forecast:{tag}] No timelines returned from API")
            return []

        intervals = timelines[0].get("intervals", [])
        if not intervals:
            logging.error(f"[Forecast:{tag}] Timelines returned but no intervals")
            return []

        _last_forecast_success = datetime.utcnow()
        _last_forecast_cooldown_log = None
        return intervals

    except RequestException as e:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        if is_dns_error(e):
            logging.error(f"[{timestamp}] [Forecast:{tag}] DNS failure resolving api.tomorrow.io - will retry")
        else:
            logging.error(f"[{timestamp}] [Forecast:{tag}] API request failed: {e}")
        return []

    except KeyError as e:
        logging.error(f"[Forecast:{tag}] Unexpected data format: {e}")
        return []
