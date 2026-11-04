"""Download named street points for the three demo metros from OpenStreetMap.

Run once; the generator then works offline from street_points.json:

    .venv/bin/python data/synthetic/fetch_streets.py

Bridges and tunnels are left out, so every point sits on land. One point is
kept per grid cell to keep the file small. Points are sorted, so the same
OpenStreetMap data always gives the same file.

The output is derived from OpenStreetMap data, (c) OpenStreetMap contributors,
available under the Open Database License (ODbL) 1.0:
https://www.openstreetmap.org/copyright
"""

from __future__ import annotations

import json
import math
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parent / "street_points.json"
# Public Overpass servers, tried in order; the main one often returns 502 when busy.
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = "team16-greatschools-hackathon/0.1 (synthetic school data generator)"
HIGHWAYS = ["residential", "living_street", "unclassified", "tertiary", "secondary"]
GRID_DEGREES = 0.002

# (south, west, north, east), wide enough to hold every generated point plus a margin.
METROS = {
    "Jacksonville": (30.10, -81.86, 30.47, -81.44),
    "Miami": (25.66, -80.36, 25.94, -80.08),
    "Orlando": (28.38, -81.52, 28.66, -81.24),
}


def _query(bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    kinds = "|".join(HIGHWAYS)
    return (
        "[out:json][timeout:180];"
        f'way["highway"~"^({kinds})$"]["name"]["bridge"!~"."]["tunnel"!~"."]'
        f"({south},{west},{north},{east});"
        "out tags geom;"
    )


def _fetch(bbox: tuple[float, float, float, float]) -> dict:
    data = urllib.parse.urlencode({"data": _query(bbox)}).encode()
    last_error: Exception | None = None
    for attempt in range(2):
        for endpoint in ENDPOINTS:
            request = urllib.request.Request(endpoint, data=data, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(request, timeout=240) as response:
                    return json.loads(response.read())
            except Exception as error:  # Busy servers return 429/502/504; try the next one.
                last_error = error
                print(f"  {endpoint}: {error}", file=sys.stderr)
        time.sleep(30)
    raise RuntimeError(f"every Overpass server failed: {last_error}")


def _points(payload: dict) -> tuple[list[str], list[list]]:
    seen: dict[tuple[int, int], tuple[float, float, str]] = {}
    for element in payload.get("elements", []):
        name = (element.get("tags") or {}).get("name")
        if not name:
            continue
        for node in element.get("geometry") or []:
            lat, lon = node["lat"], node["lon"]
            cell = (math.floor(lat / GRID_DEGREES), math.floor(lon / GRID_DEGREES))
            if cell not in seen:
                seen[cell] = (round(lat, 5), round(lon, 5), name)
    rows = sorted(seen.values())
    streets = sorted({name for _, _, name in rows})
    index = {name: i for i, name in enumerate(streets)}
    return streets, [[lat, lon, index[name]] for lat, lon, name in rows]


def main() -> None:
    metros = {}
    for city, bbox in METROS.items():
        print(f"fetching {city} ...")
        streets, points = _points(_fetch(bbox))
        print(f"  {len(points)} points on {len(streets)} named streets")
        metros[city] = {"bbox": list(bbox), "streets": streets, "points": points}
        time.sleep(5)
    header = {
        "source": "OpenStreetMap via the Overpass API",
        "license": "(c) OpenStreetMap contributors, Open Database License (ODbL) 1.0, https://www.openstreetmap.org/copyright",
        "fetched": date.today().isoformat(),
        "highways": HIGHWAYS,
        "excluded": ["bridge", "tunnel"],
        "grid_degrees": GRID_DEGREES,
    }
    # One point per line keeps the file readable and its diffs small.
    lines = ["{"]
    for key, value in header.items():
        lines.append(f"  {json.dumps(key)}: {json.dumps(value)},")
    lines.append('  "metros": {')
    for m, (city, metro) in enumerate(metros.items()):
        lines.append(f"    {json.dumps(city)}: {{")
        lines.append(f'      "bbox": {json.dumps(metro["bbox"])},')
        lines.append(f'      "streets": {json.dumps(metro["streets"], ensure_ascii=False)},')
        lines.append('      "points": [')
        points = metro["points"]
        for p, point in enumerate(points):
            comma = "," if p < len(points) - 1 else ""
            lines.append(f"        {json.dumps(point, separators=(',', ':'))}{comma}")
        lines.append("      ]")
        lines.append("    }" + ("," if m < len(metros) - 1 else ""))
    lines.append("  }")
    lines.append("}")
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
