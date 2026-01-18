# Fixture Flights

This folder holds sample flight payloads for local testing.

How to use:
1) Pick a fixture file.
2) Copy it to `fixture_flights.json` in this same folder.
3) Enable fixture mode: rename `flags/force_fixture.off` -> `flags/force_fixture.on`.

Examples:
```
cp fixture_flights_one.json fixture_flights.json
mv ../flags/force_fixture.off ../flags/force_fixture.on
```

Notes:
- Logos will not render in fixture mode because the fixture JSON does not include `owner_icao`.
