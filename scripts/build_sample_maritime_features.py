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


points = {"name": '', "featureTemplates": [], "groups": [], "labelClasses": []}
lines = {"name": '', "featureTemplates": [], "groups": [], "labelClasses": []}
polygons = {"name": '', "featureTemplates": [], "groups": [], "labelClasses": []}


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


# Create new unique subtype codes
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
    group_classes = []
    for group in geom['groups']:
        group_classes += group['classes']
    geom["groups"] = [{"type": "CIMUniqueValueGroup", "classes": group_classes}]


    for group in geom['groups']:
        # Sort groups alphabetically for AGS Pro display
        sorted_classes = sorted(group['classes'], key=lambda data: data['label'])
        group['classes'] = sorted_classes
        for subtype in group['classes']:
            subtype_string = subtype['label']
            name = '_'.join(subtype_string.split('_')[:-1])
            if name in new_subtype_codes:
                new_code = new_subtype_codes[name]
                subtype['values'][0]['fieldValues'][0] = str(new_code)

output = {
    'Point': points,
    'LineString': lines,
    'Polygon': polygons
}


# Create output layer file with new code lists
with open(str(INPUTS / 'maritime_layerfile_template.lyrx'), 'r') as reader:
    layer_file = reader.read()
layer_dict = json.loads(layer_file)

for layer in layer_dict["layerDefinitions"]:
    if layer['name'] in output:
        layer["featureTable"]["dataConnection"] = {
            "type" : "CIMStandardDataConnection",
            "workspaceConnectionString" : "DATABASE=.\\maritime_layers.gdb",
            "workspaceFactory" : "FileGDB",
            "dataset" : f"{layer['name']}_maritime_subtype",
            "datasetType" : "esriDTFeatureClass"
        }
        # Sort the featureTemplates
        featureTemplates = sorted(output[layer['name']]['featureTemplates'], key=lambda data: data['name'])
        groups = output[layer['name']]['groups']
        labelClasses = output[layer['name']]['labelClasses']

        layer['featureTemplates'] = featureTemplates
        layer['labelClasses'] = []
        for i, group in enumerate(groups):
            group['heading'] = "FCSubtype"
        layer["renderer"]["groups"] = groups
with open(str(INPUTS / 'maritime_layerfile.lyrx'), 'w') as writer:
    writer.writelines(json.dumps(layer_dict, indent=4))


# Create sample output GDB for test layers
gdb_path = os.path.join(str(OUTPUTS), 'maritime_layers.gdb')
if not arcpy.Exists(gdb_path):
    arcpy.CreateFileGDB_management(str(OUTPUTS), 'maritime_layers')

geom_lookup = {
    'Point': 'POINT',
    'LineString': 'POLYLINE',
    'Polygon': 'POLYGON'
}


# Add subtypes to each geom type featureclass
def add_subtypes_to_fc(featureclass, data):
    arcpy.management.SetSubtypeField(featureclass, "FCSubtype")
    print('Finished creating data')

    print('\nStarting subtypes')
    # TODO update list for setting subtypes
    for subtype in data['featureTemplates']:
        for i, value in enumerate(subtype['defaultValues']['propertySetItems']):
            if value == 'fcsubtype':
                code = subtype['defaultValues']['propertySetItems'][i+1]
                arcpy.management.AddSubtype(featureclass, code, subtype['name']) 


# Build test layers in output GDB
for geom, data in output.items():
    fc_name = f'{geom}_maritime_subtype'
    featureclass = os.path.join(gdb_path, fc_name)
    arcpy.management.CreateFeatureclass(gdb_path, fc_name, geom_lookup[geom])
    arcpy.management.AddField(featureclass, 'FCSubtype', 'LONG')

    with arcpy.da.InsertCursor(featureclass, ['FCSubtype', 'SHAPE@XY']) as cursor:
        if geom == 'Point':
            x = -79.873184
            y = 32.680892
            half = int(len(data['featureTemplates']) / 2)
            count = 0
            for i, subtype in enumerate(data['featureTemplates']):
                location = (x, y)
                for j, value in enumerate(subtype['defaultValues']['propertySetItems']):
                    if value == 'fcsubtype':
                        code = subtype['defaultValues']['propertySetItems'][j+1]
                cursor.insertRow([code, location])
                x += .001
                count += .001
                if i == half:
                    x -= count
                    y += .006
            add_subtypes_to_fc(featureclass, data)
        elif geom == 'LineString':
            # TODO build lines
            continue
        elif geom == 'Polygon':
            # TODO build polygons
            continue

    print('Finished adding subtypes')

print('Done')
