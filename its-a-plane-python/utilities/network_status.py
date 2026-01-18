import os
import socket
from urllib.request import Request, urlopen
import subprocess


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
FLAGS_DIR = os.path.join(BASE_DIR, "flags")


class NetStatus:
    OK = "ok"
    NO_SSID = "no_ssid"
    NO_WIFI = "no_wifi"
    NO_NET = "no_net"
    API_DOWN = "api_down"


def _flag_on(name: str) -> bool:
    return os.path.exists(os.path.join(FLAGS_DIR, f"{name}.on"))


def read_forced_status() -> str:
    if _flag_on("force_net_no_ssid"):
        return NetStatus.NO_SSID
    if _flag_on("force_net_no_wifi"):
        return NetStatus.NO_WIFI
    if _flag_on("force_net_no_net"):
        return NetStatus.NO_NET
    if _flag_on("force_net_api_down"):
        return NetStatus.API_DOWN
    return NetStatus.OK


def _run_cmd(cmd: list[str]) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        return res.stdout.strip()
    except Exception:
        return ""


def _wifi_connected() -> bool:
    ssid = _run_cmd(["/sbin/iwgetid", "-r"])
    if ssid:
        return True
    ssid = _run_cmd(["/usr/sbin/iwgetid", "-r"])
    if ssid:
        return True
    ssid = _run_cmd(["iwgetid", "-r"])
    return bool(ssid)


def _internet_ok() -> bool:
    try:
        req = Request("https://www.google.com", method="HEAD")
        with urlopen(req, timeout=3) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def current_status() -> str:
    forced = read_forced_status()
    if forced != NetStatus.OK:
        return forced

    if not _wifi_connected():
        return NetStatus.NO_WIFI

    if not _internet_ok():
        return NetStatus.NO_NET

    return NetStatus.OK
