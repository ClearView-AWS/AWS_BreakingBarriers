# Synthetic data (Seattle)

- `../../Sample Data/`: the 25 schools and 25 programs GreatSchools provided (Florida, anonymized names). They stay unchanged.
- `generate.py` writes `sample_seattle.json` (the 25 sample schools moved to Seattle: new ids `School wa-…`, city, county, district, address and map point; ratings, reviews and missing fields unchanged), `schools.json` (275 generated Seattle schools), `programs.json` (generated after-school programs) and one static page per generated school in `websites/`. Every generated or moved record is marked `_synthetic: true`. Run it from the repo root with `python data/synthetic/generate.py`; the output is the same on every run.
- The app loads `sample_seattle.json` instead of the Florida sample schools. The sample programs (spread across the US) still load from `Sample Data/`.
- Every generated school has `osp.admission_type` (`zoned`, `choice`, `lottery` or `application`). About the sample's share also have `application_deadline_date`, `admissions_url` and `application_requirements`, and a few have `seats_by_grade` and `applicants_last_year`, each with an `as_of` date. Demo schools in Seattle are hand-set so every Getting in status appears. The sample schools keep their own fields.
- Every pin is moved to the nearest street point, so none sits in water. To check the pins, run `python data/synthetic/map_preview.py pins.html`, open the file, and switch to the satellite layer.
- `generate_community.py` writes `community_seed.json`, the seed threads for the parent community.

## Street data

`street_points.json` holds points along 37 Seattle arterials, traced by hand in `seattle_streets.py` because the workspace that built it could not reach OpenStreetMap. Run `python data/synthetic/seattle_streets.py` to rebuild it. With network access, `fetch_streets.py` downloads exact OpenStreetMap street points for Seattle into the same file; then run `generate.py` again.

OpenStreetMap street data © OpenStreetMap contributors, available under the [Open Database License](https://www.openstreetmap.org/copyright).
