from osgeo import gdal

ds = gdal.Open(f'HDF5:"cache/radar/latest.hdf"://dataset1/data1/data')

print("Projection:")
print(ds.GetProjection())

print()

print("GeoTransform:")
print(ds.GetGeoTransform())

print()

print("Size:")
print(ds.RasterXSize, ds.RasterYSize)
