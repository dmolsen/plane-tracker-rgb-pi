#!/usr/bin/env python3
import os
import re

LOGO_DIR_CANDIDATES = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logos")),
    os.path.expanduser(os.path.join("~", "logos")),
]

WEB_PATTERN = re.compile(r"^([A-Z0-9]{2,4})--web\.(png|jpg|jpeg|svg)$", re.IGNORECASE)


def _select_logo_dir():
    for base in LOGO_DIR_CANDIDATES:
        if os.path.isdir(base):
            return base
    return LOGO_DIR_CANDIDATES[-1]


def main():
    logo_dir = _select_logo_dir()
    if not os.path.isdir(logo_dir):
        print(f"No logos directory found at {logo_dir}")
        return

    deleted = 0
    for name in os.listdir(logo_dir):
        match = WEB_PATTERN.match(name)
        if not match:
            continue
        icao = match.group(1).upper()
        web_path = os.path.join(logo_dir, name)
        display_path = os.path.join(logo_dir, f"{icao}.png")

        try:
            os.remove(web_path)
            deleted += 1
            print(f"Deleted {web_path}")
        except FileNotFoundError:
            pass

        if os.path.isfile(display_path):
            try:
                os.remove(display_path)
                deleted += 1
                print(f"Deleted {display_path}")
            except FileNotFoundError:
                pass

    if not deleted:
        print("No matching logos found.")


if __name__ == "__main__":
    main()
