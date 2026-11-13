# South Lhonak lake-area values

`lake_area_south_lhonak.csv` contains only the five approximate published values supplied for this project. The `area_km2` column is converted from hectares by dividing by 100. These values are **not computed by this project from Sentinel-2 NDWI**.

The NRSC/ISRO entries are radar-based. They are not directly comparable to a Sentinel-2 optical NDWI series. The secondary entries are reported through news and blog sources; check them against the original publication before citing or using them in the final report.

The simulator's lake-area baseline is **1.3 km²** at hour zero before its per-episode offset and sensor noise; it also adds a small hourly trend. This is synthetic, not a South Lhonak measurement, and must not be mixed with the approximate published observations. The CSV values range from 0.603 to 1.7 km², reflecting the supplied observations rather than simulator output.

`extract_lake_area.py` is an untested Google Earth Engine skeleton for a possible future Sentinel-2 NDWI extraction. No values from that script are included in the CSV.
