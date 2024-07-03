import arcpy
import json


dictionary = {'type': 'LineString', 'coordinates': [[-81.0528058, 29.2868003], [-81.0521728, 29.2870589], [-81.0493116, 29.2882275]]}

layer = arcpy.management.CreateFeatureclass(
    'memory', 
    'test_layer',
    'POLYLINE'
)

with arcpy.da.InsertCursor(layer, 'SHAPE@JSON', explicit=True) as cursor: 
    cursor.insertRow([arcpy.AsShape(dictionary).JSON])

print('done')