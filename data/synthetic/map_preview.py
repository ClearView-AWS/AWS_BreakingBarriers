"""Write an HTML map of every school and program pin, for spot-checking.

    .venv/bin/python data/synthetic/map_preview.py <out.html> [--before <dir>]

Open the file in a browser. Switch to the satellite layer to check that no pin
sits in water. With --before (a folder holding older schools.json and
programs.json), each pin that moved also shows its old spot and a line to the new one.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def _pins(path: Path, kind: str) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for record in json.loads(path.read_text()):
        latlon = record.get("latlon")
        if not isinstance(latlon, str) or "," not in latlon:
            continue
        lat, lon = (float(x) for x in latlon.split(","))
        rows.append(
            {
                "id": record.get("id"),
                "kind": kind,
                "name": record.get("name"),
                "city": record.get("city"),
                "street": record.get("street"),
                "role": record.get("_demo_role") or ("program" if kind == "program" else "sample"),
                "lat": lat,
                "lon": lon,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--before", type=Path, default=None)
    args = parser.parse_args()

    pins = (
        _pins(ROOT / "Sample Data" / "schools_sample.json", "sample")
        + _pins(HERE / "schools.json", "school")
        + _pins(HERE / "programs.json", "program")
    )
    before = {}
    if args.before:
        for name, kind in (("schools.json", "school"), ("programs.json", "program")):
            for pin in _pins(args.before / name, kind):
                before[pin["id"]] = [pin["lat"], pin["lon"]]
    for pin in pins:
        old = before.get(pin["id"])
        if old and (abs(old[0] - pin["lat"]) > 1e-6 or abs(old[1] - pin["lon"]) > 1e-6):
            pin["before"] = old

    html = TEMPLATE.replace("__PINS__", json.dumps(pins))
    args.out.write_text(html)
    moved = sum(1 for pin in pins if "before" in pin)
    print(f"wrote {args.out} with {len(pins)} pins ({moved} moved)")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pin check</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
  html, body { margin: 0; height: 100%; font: 14px system-ui, sans-serif; background: #fff; color: #111; }
  #map { position: absolute; inset: 0; }
  .bar { position: absolute; z-index: 1000; top: 10px; left: 50px; background: #fff; padding: 8px 10px;
         border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,.3); display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  .bar button { font: inherit; padding: 2px 8px; }
  .key span { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin: 0 4px 0 8px; vertical-align: middle; }
</style>
</head>
<body>
<div id="map"></div>
<div class="bar">
  <button data-go="30.30,-81.65,11">Jacksonville</button>
  <button data-go="25.78,-80.22,11">Miami</button>
  <button data-go="28.52,-81.38,11">Orlando</button>
  <button data-go="25.72,-80.15,13">Biggest moves (Miami bay)</button>
  <span class="key"><span style="background:#2563eb"></span>sample (real)
    <span style="background:#ea580c"></span>generated school
    <span style="background:#16a34a"></span>program
    <span style="background:#9ca3af"></span>old spot</span>
</div>
<script>
const pins = __PINS__;
// Esri tiles load from a local file without an API key (CARTO's no longer do).
const streets = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
  { maxZoom: 19, attribution: 'Tiles &copy; Esri' });
const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  { maxZoom: 19, attribution: 'Tiles &copy; Esri' });
const newPins = L.layerGroup();
const oldSpots = L.layerGroup();
const map = L.map('map', { layers: [streets, newPins, oldSpots] }).setView([30.30, -81.65], 11);
L.control.layers(
  { 'Streets': streets, 'Satellite (check for water)': satellite },
  { 'Pins now': newPins, 'Old spots and moves': oldSpots },
  { collapsed: false }
).addTo(map);
const color = { sample: '#2563eb', school: '#ea580c', program: '#16a34a' };
for (const p of pins) {
  if (p.before) {
    L.polyline([p.before, [p.lat, p.lon]], { color: '#374151', weight: 1.5, dashArray: '4 3' }).addTo(oldSpots);
    L.circleMarker(p.before, { radius: 5, color: '#374151', fillColor: '#9ca3af', fillOpacity: 0.7, weight: 1 })
      .bindPopup(`<b>${p.name}</b><br>old spot ${p.before[0].toFixed(5)}, ${p.before[1].toFixed(5)}`).addTo(oldSpots);
  }
  L.circleMarker([p.lat, p.lon], { radius: 6, color: '#fff', fillColor: color[p.kind], fillOpacity: 0.95, weight: 1.5 })
    .bindPopup(`<b>${p.name}</b><br>${p.street || ''}<br>${p.city || ''} &middot; ${p.role}<br>${p.lat}, ${p.lon}`)
    .addTo(newPins);
}
document.querySelectorAll('[data-go]').forEach(b => b.onclick = () => {
  const [lat, lon, z] = b.dataset.go.split(',').map(Number); map.setView([lat, lon], z);
});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
