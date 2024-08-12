# make a FC with 1 row for each subtype number
import arcpy
import yaml
import json
import os
arcpy.env.overwriteOutput = True

# get list of subtypes
with open(r'C:\Users\Stephen.Patterson\Data\Repos\csf_prf\inputs\lookups\all_subtypes.yaml', 'r') as lookup:
    subtype_lookup = yaml.safe_load(lookup)

gdb = r'C:\Users\Stephen.Patterson\Data\Repos\csf_prf\outputs\csf_features.gdb'
geom_lookup = {
    'Point': 'POINT',
    'LineString': 'POLYLINE',
    'Polygon': 'POLYGON'
}


for geom_type, subtypes in subtype_lookup.items():
    if geom_type == 'Point':
        # TODO build location geometry for linestring and polygon to automate
        # TODO certain subtypes have wrong code in output, ie: WRECKS 
        codes = []
        new_subtype_codes = {}
        fc_name = f'{geom_type}_maritime_subtype'
        featureclass = os.path.join(gdb, fc_name)
        arcpy.management.CreateFeatureclass(gdb, fc_name, geom_lookup[geom_type])
        arcpy.management.AddField(featureclass, 'FCSubtype', 'LONG')
        with arcpy.da.InsertCursor(featureclass, ['FCSubtype', 'SHAPE@XY']) as cursor:
            x = -79.873184
            y = 32.680892
            half = len(subtypes.keys()) / 2
            count = 0
            for i, subtype in enumerate(subtypes.keys()):
                data = subtypes[subtype]
                location = (x, y)
                code = data['code']
                if code in codes:
                    new_code = code + 1000
                    while new_code in codes:
                        new_code += 1
                    codes.append(new_code)
#                     print('"' + subtype + '" : ' + str(new_code) + ',')
                    new_subtype_codes[subtype] = new_code
                    cursor.insertRow([new_code, location])
                else:
                    codes.append(code)
                    cursor.insertRow([code, location])
                x += .001
                count += .001
                if i == half:
                    x -= count
                    y += .006
        arcpy.management.SetSubtypeField(featureclass, "FCSubtype")
        print('Finished creating data')

        print('\nStarting subtypes')
        for subtype, data in subtype_lookup[geom_type].items():
            if subtype in new_subtype_codes:
                code = new_subtype_codes[subtype]
            else:
                code = data['code']
            print(subtype, code)
            arcpy.management.AddSubtype(featureclass, code, data['objl_string']) 
        print('Finished adding subtypes')
            