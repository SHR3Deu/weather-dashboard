from osgeo import gdal
import pprint

gdal.UseExceptions()

ds = gdal.Open(
    'HDF5:"cache/radar/latest.hdf"://dataset1/data1/data'
)

print("\n=== DATASET METADATA ===")
pprint.pprint(ds.GetMetadata())

print("\n=== METADATA DOMAINS ===")
print(ds.GetMetadataDomainList())

print("\n=== IMAGE STRUCTURE ===")
pprint.pprint(ds.GetMetadata("IMAGE_STRUCTURE"))

print("\n=== SUBDATASETS ===")
pprint.pprint(ds.GetMetadata("SUBDATASETS"))

print("\n=== GEO TRANSFORM ===")
print(ds.GetGeoTransform())

print("\n=== PROJECTION ===")
print(ds.GetProjection())

band = ds.GetRasterBand(1)

print("\n=== BAND METADATA ===")
pprint.pprint(band.GetMetadata())

print("\n=== BAND NODATA ===")
print(band.GetNoDataValue())

print("\n=== SCALE / OFFSET ===")
print("Scale :", band.GetScale())
print("Offset:", band.GetOffset())
