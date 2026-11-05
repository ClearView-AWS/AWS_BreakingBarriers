# Washington OSPI Report Card (public)

Public school enrollment and graduation from the [Washington State Report Card](https://washingtonstatereportcard.ospi.k12.wa.us/). Used because GreatSchools confidential profile feeds are not available in this sandbox.

| File | Role |
|---|---|
| `Report_Card_Enrollment_*.csv` | School × grade enrollment + student groups (local; large) |
| `Report_Card_Graduation_*.csv` | School × cohort graduation (local; large) |
| `import_ospi.py` | Builds `schools.json` in the Guided Search document shape |
| `schools.json` | **Committed** corpus (~2.3k WA schools) loaded by the API |

```bash
# After dropping new OSPI CSVs into this folder:
python data/wa/import_ospi.py
```

The app loads `schools.json` automatically when the file exists. Disable with `GS_INCLUDE_WA=0`.

**What is filled:** name, district→city, county, public/private type, grade levels, enrollment, ELL / gifted flags, 4-year graduation → `summary_rating` for high schools.  
**What stays Unknown (by design):** after-care, STEM clubs, transportation, etc. — so gap-fill / AI call still applies.

Raw CSVs are gitignored (tens of MB). Keep them locally to regenerate.
