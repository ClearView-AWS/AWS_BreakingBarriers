# Synthetic data

- `../../Sample Data/`: the 25 schools and 25 programs GreatSchools provided. They stay unchanged.
- `generate.py` writes `schools.json` (275 generated schools), `programs.json` (49 generated programs) and one static page per generated school in `websites/`. Every generated record is marked `_synthetic: true`. Run it from the repo root with `python data/synthetic/generate.py`; the output is the same on every run.
- Every generated pin is moved to the nearest real street, so none sits in water. To check the pins, run `python data/synthetic/map_preview.py pins.html`, open the file, and switch to the satellite layer.

## Street data

`street_points.json` holds named street locations (no bridges or tunnels) for Jacksonville, Miami and Orlando, from OpenStreetMap via the Overpass API. `fetch_streets.py` downloads it again if needed; the generator itself works offline.

Street data © OpenStreetMap contributors, available under the [Open Database License](https://www.openstreetmap.org/copyright).
