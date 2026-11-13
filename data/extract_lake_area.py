"""UNTESTED Google Earth Engine skeleton for a future Sentinel-2 extraction.

This is a starting point only. Confirm the lake bounding box, NDWI threshold,
cloud handling, dates, and exported results before use. No values from this
script are in lake_area_south_lhonak.csv.
"""


def main():
    # Import Earth Engine only when explicitly running the script; importing
    # this file does not initialize Earth Engine or require its Python package.
    import ee

    ee.Initialize()

    # TODO: Confirm this placeholder rectangle around South Lhonak Lake.
    # Coordinates are [west, south, east, north] in longitude/latitude degrees.
    lake_bounds = ee.Geometry.Rectangle([88.16, 27.90, 88.20, 27.94])

    # TODO: Confirm this water threshold before processing any imagery.
    ndwi_water_threshold = 0.0

    start_date = "2016-01-01"
    end_date = "2023-12-31"
    images = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(lake_bounds)
        .filterDate(start_date, end_date)
    )

    def image_to_area_feature(image):
        image = ee.Image(image)
        # Sentinel-2 Green = B3; Near Infrared = B8.
        ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")
        water_mask = ndwi.gt(ndwi_water_threshold)
        water_area_m2 = ee.Image.pixelArea().updateMask(water_mask).reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=lake_bounds,
            scale=10,
            maxPixels=1e10,
        ).get("area")
        water_area_km2 = ee.Number(water_area_m2).divide(1_000_000)
        water_area_ha = ee.Number(water_area_m2).divide(10_000)
        return ee.Feature(None, {
            "date": image.date().format("YYYY-MM-dd"),
            "area_ha": water_area_ha,
            "area_km2": water_area_km2,
            "source": "Sentinel-2 NDWI (Earth Engine; unverified export)",
            "method": "ndwi_b3_b8_threshold",
        })

    image_list = images.toList(images.size())
    area_features = ee.FeatureCollection(
        image_list.map(image_to_area_feature)
    )

    task = ee.batch.Export.table.toDrive(
        collection=area_features,
        description="South_Lhonak_Sentinel2_NDWI_area_UNTESTED",
        fileNamePrefix="south_lhonak_sentinel2_ndwi_area_UNTESTED",
        fileFormat="CSV",
        selectors=["date", "area_ha", "area_km2", "source", "method"],
    )
    task.start()
    print("Earth Engine export submitted. Inspect and validate it before use.")


if __name__ == "__main__":
    main()
