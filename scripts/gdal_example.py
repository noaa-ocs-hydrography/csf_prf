from osgeo import ogr
from osgeo import gdal
gdal.UseExceptions()

ogr.RegisterAll()

enc_driver = ogr.GetDriverByName('S57')
print(dir(enc_driver))
print('\n', enc_driver.GetName())

enc = enc_driver.Open(r"C:\Users\Stephen.Patterson\Data\Projects\CSF_PRF\Data\Boston-Gloucester 2023\Source Files\Charts\US4MA04M.000", 0)
print('\n', dir(enc))


for i, layer in enumerate(range(0, enc.GetLayerCount())):
    enc_layer = enc.GetLayer(layer)
    print(enc_layer.GetName())
    print('geom type:', enc_layer.GetGeomType())
    for i in range(enc_layer.GetFeatureCount()):
        feature = enc_layer.GetFeature(i)
        if feature:
            print('#############################:', i)
            print('geom:', feature.ExportToJson())

    if i == enc.GetLayerCount() - 1:
        print(dir(enc_layer))
    
    