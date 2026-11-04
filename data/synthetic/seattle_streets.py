"""Write street_points.json for Seattle from hand-traced arterial segments.

The workspace that built the Seattle data could not reach OpenStreetMap, so each
segment below was traced along a real Seattle arterial, away from Green Lake,
Bitter Lake, Lake Union, Lake Washington and the Sound. Points are spaced about
0.04 miles apart along each segment. With network access, fetch_streets.py can
replace this file with exact OpenStreetMap street points.

Run from the repo root:  python data/synthetic/seattle_streets.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent / "street_points.json"
STEP_MILES = 0.04

# (street name, (lat, lon) start, (lat, lon) end)
SEATTLE = [
    # North-south
    ("Greenwood Ave N", (47.7330, -122.3553), (47.6700, -122.3553)),
    ("8th Ave NW", (47.6950, -122.3665), (47.6640, -122.3665)),
    ("15th Ave NW", (47.6950, -122.3765), (47.6645, -122.3765)),
    ("24th Ave NW", (47.6940, -122.3870), (47.6645, -122.3870)),
    ("Meridian Ave N", (47.7330, -122.3335), (47.6935, -122.3335)),
    ("Roosevelt Way NE", (47.6980, -122.3175), (47.6625, -122.3175)),
    ("15th Ave NE", (47.7330, -122.3125), (47.6635, -122.3125)),
    ("35th Ave NE", (47.7180, -122.2905), (47.6660, -122.2905)),
    ("Lake City Way NE", (47.7230, -122.2960), (47.6990, -122.3080)),
    ("Queen Anne Ave N", (47.6450, -122.3570), (47.6265, -122.3570)),
    ("34th Ave W", (47.6550, -122.4000), (47.6385, -122.4000)),
    ("15th Ave E", (47.6390, -122.3125), (47.6160, -122.3125)),
    ("Broadway", (47.6330, -122.3210), (47.6045, -122.3210)),
    ("23rd Ave", (47.6270, -122.3020), (47.5805, -122.3020)),
    ("Beacon Ave S", (47.5880, -122.3110), (47.5405, -122.2930)),
    ("15th Ave S", (47.5850, -122.3125), (47.5470, -122.3125)),
    ("Martin Luther King Jr Way S", (47.5900, -122.2965), (47.5155, -122.2785)),
    ("Rainier Ave S", (47.5900, -122.3010), (47.5245, -122.2705)),
    ("California Ave SW", (47.5700, -122.3870), (47.5235, -122.3870)),
    ("35th Ave SW", (47.5680, -122.3760), (47.5125, -122.3760)),
    ("Delridge Way SW", (47.5640, -122.3620), (47.5185, -122.3550)),
    # East-west
    ("N 130th St", (47.7240, -122.3400), (47.7240, -122.3000)),
    ("NE Northgate Way", (47.7085, -122.3450), (47.7085, -122.3000)),
    ("NW 85th St", (47.6905, -122.3870), (47.6905, -122.3560)),
    ("NE 85th St", (47.6905, -122.3300), (47.6905, -122.2950)),
    ("NW Market St", (47.6687, -122.3950), (47.6687, -122.3560)),
    ("NE 65th St", (47.6760, -122.3180), (47.6760, -122.2860)),
    ("N 45th St", (47.6612, -122.3600), (47.6612, -122.3200)),
    ("NE 45th St", (47.6612, -122.3150), (47.6612, -122.3010)),
    ("W McGraw St", (47.6390, -122.3700), (47.6390, -122.3560)),
    ("E Madison St", (47.6110, -122.3240), (47.6260, -122.2960)),
    ("E Union St", (47.6130, -122.3200), (47.6130, -122.2960)),
    ("S Jackson St", (47.5992, -122.3200), (47.5992, -122.2960)),
    ("SW Alaska St", (47.5610, -122.3950), (47.5610, -122.3650)),
    ("S Othello St", (47.5380, -122.2960), (47.5380, -122.2710)),
    ("S Henderson St", (47.5225, -122.2850), (47.5225, -122.2725)),
    ("SW Roxbury St", (47.5170, -122.3800), (47.5170, -122.3460)),
]


def _miles(a, b) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    hav = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 3958.7613 * 2 * math.asin(math.sqrt(hav))


def build(segments) -> dict:
    streets: list[str] = []
    points: list[list] = []
    for name, start, end in segments:
        if name not in streets:
            streets.append(name)
        index = streets.index(name)
        steps = max(1, int(_miles(start, end) / STEP_MILES))
        for step in range(steps + 1):
            t = step / steps
            lat = round(start[0] + (end[0] - start[0]) * t, 6)
            lon = round(start[1] + (end[1] - start[1]) * t, 6)
            points.append([lat, lon, index])
    return {"streets": streets, "points": points}


def main() -> None:
    payload = {
        "source": "Hand-traced along Seattle arterials (see seattle_streets.py); replace with fetch_streets.py output when OpenStreetMap is reachable.",
        "metros": {"Seattle": build(SEATTLE)},
    }
    OUT.write_text(json.dumps(payload))
    seattle = payload["metros"]["Seattle"]
    print(f"Seattle: {len(seattle['points'])} points on {len(seattle['streets'])} streets -> {OUT}")


if __name__ == "__main__":
    main()
