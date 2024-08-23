import arcpy
import os
import pathlib
import yaml
from csf_prf.engines.Engine import Engine
arcpy.env.qualifiedFieldNames = True


class StupidException(Exception):
    pass

engine = Engine()

INPUTS = pathlib.Path(r"C:\Users\Stephen.Patterson\Data\Repos\csf_prf\inputs")

with open(str(INPUTS / "lookups" / "all_subtypes.yaml"), "r") as lookup:
    subtype_lookup = yaml.safe_load(lookup)

unique_subtype_lookup = engine.get_unique_subtype_codes(subtype_lookup)
output_gdb = r"C:\Users\Stephen.Patterson\Data\Repos\csf_prf\outputs\csf_features.gdb"
arcpy.env.workspace = output_gdb

featureclasses = arcpy.ListFeatureClasses()
for featureclass in featureclasses: 
    for geom in ['Point', 'LineString', 'Polygon']:
        if geom in featureclass:
            field = [field.name for field in arcpy.ListFields(featureclass) if 'FC' in field.name][0]
            print(geom, featureclass, )
            try:
                arcpy.management.SetSubtypeField(featureclass, field)
            except StupidException as e:
                print(e)
                pass

# print('one')
# arcpy.management.SetSubtypeField(r"C:\Users\Stephen.Patterson\Data\Repos\csf_prf\outputs\csf_features.gdb\Point_features_assigned", "FCSubtype")
# print('two')
# arcpy.management.SetSubtypeField(r"C:\Users\Stephen.Patterson\Data\Repos\csf_prf\outputs\csf_features.gdb\Point_features_unassigned", "FCSubtype")
# print('done')