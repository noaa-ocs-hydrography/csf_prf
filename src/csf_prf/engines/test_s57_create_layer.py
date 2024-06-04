import pathlib
from osgeo import ogr


# OUTPUTS = pathlib.Path(__file__).parents[0]
OUTPUTS = pathlib.Path(__file__).parents[3] / 'inputs' / 'test' / 'clipped'

output_path = str(OUTPUTS / 'US5_Joined_ENC.000')
driver = ogr.GetDriverByName('S57')
output_enc = driver.Open(str(output_path), 0)

# output_enc = driver.CreateDataSource(output_path)
# lights = output_enc.GetLayerByName('LIGHTS')  # ENC's always have the defined layers
# print(dir(lights))
# print(lights.GetName())

for i, layer in enumerate(output_enc):
    print(layer.GetName())
    print(i)
    for feature in layer:
        print(feature.ExportToJson())
