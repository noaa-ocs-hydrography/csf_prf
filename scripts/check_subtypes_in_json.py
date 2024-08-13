import json
import pathlib
import arcpy
import yaml
import json
import os
arcpy.env.overwriteOutput = True


OUTPUTS = pathlib.Path(__file__).parents[1] / 'outputs'
INPUTS = pathlib.Path(__file__).parents[1] / 'inputs'


with open(str(INPUTS / 'maritime_master_layerfile.lyrx'), 'r') as reader:
    layer_file = reader.read()
layer_dict = json.loads(layer_file)


points = {"name": '', "featureTemplates": [], "groups": []}
lines = {"name": '', "featureTemplates": [], "groups": []}
polygons = {"name": '', "featureTemplates": [], "groups": []}


# Join all featureTemplates and groups arrays
for layer in layer_dict["layerDefinitions"]:
    if layer["name"].endswith("P"):
        points["name"] = "Point"
        points["featureTemplates"] += layer["featureTemplates"]
        points["groups"] += layer["renderer"]["groups"]
    elif layer["name"].endswith("L"):
        lines["name"] = "LineString"
        lines["featureTemplates"] += layer["featureTemplates"]
        if 'groups' in layer['renderer']:
            lines["groups"] += layer["renderer"]["groups"]
    elif layer["name"].endswith("A"):
        polygons["name"] = "Polygon"
        polygons["featureTemplates"] += layer["featureTemplates"]
        polygons["groups"] += layer["renderer"]["groups"]


for geom in [points, lines, polygons]:
    codes = []
    new_subtype_codes = {}
    # update codes in featureTemplates section
    for feature in geom['featureTemplates']:
        name = '_'.join(feature['name'].split('_')[:-1])
        if 'defaultValues' in feature:
            propertySetItems = feature['defaultValues']['propertySetItems']
            for i, item in enumerate(propertySetItems):
                if item == 'fcsubtype':
                    code = feature['defaultValues']['propertySetItems'][i+1]
            if code in codes:
                new_code = code + 1000
                while new_code in codes:
                    new_code += 1
                codes.append(new_code)
                # update the code
                new_subtype_codes[name] = new_code
                
                for i, item in enumerate(propertySetItems):
                    if item == 'fcsubtype':
                        feature['defaultValues']['propertySetItems'][i+1] = new_code
            else:
                codes.append(code)
    # update codes in groups section
    for group in geom['groups']:
        for subtype in group['classes']:
            subtype_string = subtype['label']
            name = '_'.join(subtype_string.split('_')[:-1])
            if name in new_subtype_codes:
                new_code = new_subtype_codes[name]
                subtype['values'][0]['fieldValues'][0] = str(new_code)
    print(geom["name"])
    print(codes)
    print(new_subtype_codes)


output = {
    'Point': points,
    'LineString': lines,
    'Polygon': polygons
}


with open(str(INPUTS / 'maritime_layerfile_template.lyrx'), 'r') as reader:
    layer_file = reader.read()
layer_dict = json.loads(layer_file)

for layer in layer_dict["layerDefinitions"]:
    if layer['name'] in output:
        # featureTemplates = json.dumps(output[layer['name']]['featureTemplates'], indent=4)
        # groups = json.dumps(output[layer['name']]['groups'], indent=4)
        featureTemplates = output[layer['name']]['featureTemplates']
        groups = output[layer['name']]['groups']
        layer['featureTemplates'] = featureTemplates
        layer["renderer"]["groups"] = groups
with open(str(OUTPUTS / 'maritime_layerfile.lyrx'), 'w') as writer:
    writer.writelines(json.dumps(layer_dict, indent=4))


# get list of subtypes
# with open(r'C:\Users\Stephen.Patterson\Data\Repos\csf_prf\inputs\lookups\all_subtypes.yaml', 'r') as lookup:
#     subtype_lookup = yaml.safe_load(lookup)

gdb = arcpy.CreateFileGDB_management(str(OUTPUTS), 'maritime_layers')
geom_lookup = {
    'Point': 'POINT',
    'LineString': 'POLYLINE',
    'Polygon': 'POLYGON'
}

for geom, data in output.items():
    codes = []
    new_subtype_codes = {}
    fc_name = f'{geom}_maritime_subtype'
    featureclass = os.path.join(gdb, fc_name)
    arcpy.management.CreateFeatureclass(gdb, fc_name, geom_lookup[geom])
    arcpy.management.AddField(featureclass, 'FCSubtype', 'LONG')

    with arcpy.da.InsertCursor(featureclass, ['FCSubtype', 'SHAPE@XY']) as cursor:
        if geom == 'Point':
            x = -79.873184
            y = 32.680892
            half = len(data['featureTemplates']) / 2
            count = 0
            for subtype in data['featureTemplates']:
                location = (x, y)
                for i, value in subtype['defaultValues']['propertySetItems']:
                    if value == 'fcsubtype':
                        code = subtype['defaultValues']['propertySetItems'][i+1]
                cursor.insertRow([code, location])
                x += .001
                count += .001
                if i == half:
                    x -= count
                    y += .006
        elif geom == 'LineString':
            # TODO build lines
            continue
        elif geom == 'Polygon':
            # TODO build polygons
            continue


    arcpy.management.SetSubtypeField(featureclass, "FCSubtype")
    print('Finished creating data')

    print('\nStarting subtypes')
    # TODO update list for setting subtypes
    for subtype, data in subtype_lookup[geom_type].items():
        if subtype in new_subtype_codes:
            code = new_subtype_codes[subtype]
        else:
            code = data['code']
        print(subtype, code)
        arcpy.management.AddSubtype(featureclass, code, data['objl_string']) 
    print('Finished adding subtypes')


# for geom_type, subtypes in subtype_lookup.items():
#     if geom_type == 'Point':
#         # TODO build location geometry for linestring and polygon to automate
#         # TODO certain subtypes have wrong code in output, ie: WRECKS 
#         codes = []
#         new_subtype_codes = {}
#         fc_name = f'{geom_type}_maritime_subtype'
#         featureclass = os.path.join(gdb, fc_name)
#         arcpy.management.CreateFeatureclass(gdb, fc_name, geom_lookup[geom_type])
#         arcpy.management.AddField(featureclass, 'FCSubtype', 'LONG')
#         with arcpy.da.InsertCursor(featureclass, ['FCSubtype', 'SHAPE@XY']) as cursor:
#             x = -79.873184
#             y = 32.680892
#             half = len(subtypes.keys()) / 2
#             count = 0
#             for i, subtype in enumerate(subtypes.keys()):
#                 data = subtypes[subtype]
#                 location = (x, y)
#                 code = data['code']
#                 if code in codes:
#                     new_code = code + 1000
#                     while new_code in codes:
#                         new_code += 1
#                     codes.append(new_code)
# #                     print('"' + subtype + '" : ' + str(new_code) + ',')
#                     new_subtype_codes[subtype] = new_code
#                     cursor.insertRow([new_code, location])
#                 else:
#                     codes.append(code)
#                     cursor.insertRow([code, location])
#                 x += .001
#                 count += .001
#                 if i == half:
#                     x -= count
#                     y += .006
#         arcpy.management.SetSubtypeField(featureclass, "FCSubtype")
#         print('Finished creating data')

#         print('\nStarting subtypes')
#         for subtype, data in subtype_lookup[geom_type].items():
#             if subtype in new_subtype_codes:
#                 code = new_subtype_codes[subtype]
#             else:
#                 code = data['code']
#             print(subtype, code)
#             arcpy.management.AddSubtype(featureclass, code, data['objl_string']) 
#         print('Finished adding subtypes')
            
print('Done')