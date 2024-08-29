import json
import pathlib
import arcpy
import json
import copy
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


name_lookup = {
    'Point': 'features_points_layer_FCSubtype',
    'LineString': 'features_lines_layer_FCSubtype',
    'Polygon': 'features_polygons_layer_FCSubtype',
}

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
                        # Add long field names as well as short field names
                        feature['defaultValues']['propertySetItems'].append(name_lookup[geom['name']])
                        feature['defaultValues']['propertySetItems'].append(new_code)
            else:
                codes.append(code)
                # Add long field names as well as short field names
                feature['defaultValues']['propertySetItems'].append(name_lookup[geom['name']])
                feature['defaultValues']['propertySetItems'].append(code)
                

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


# Sort codes and add new code lists
with open(str(INPUTS / 'maritime_layerfile_template.lyrx'), 'r') as reader:
    layer_file = reader.read()
layer_dict = json.loads(layer_file)

for layer in layer_dict["layerDefinitions"]:
    if layer['name'] in output:
        # Sort the featureTemplates
        featureTemplates = sorted(output[layer['name']]['featureTemplates'], key=lambda data: data['name'])
        groups = output[layer['name']]['groups']
        labelClasses = output[layer['name']]['labelClasses']

        layer['featureTemplates'] = featureTemplates
        layer['labelClasses'] = []
        for i, group in enumerate(groups):
            group['heading'] = "FCSubtype"
        layer["renderer"]["groups"] = groups


# Create layer definitions for CSF/PRF layers
csf_prf_layers = []
for layer in layer_dict["layerDefinitions"]:
    output_types = ['assigned', 'unassigned']
    for output_type in output_types:
        current_layer = copy.deepcopy(layer)
        if 'featureTable' in current_layer:
            fc_name = f"{current_layer['name']}_features_{output_type}"
            current_layer["featureTable"]["dataConnection"] = {
                "type" : "CIMStandardDataConnection",
                "workspaceConnectionString" : "DATABASE=.\\{~}.gdb",
                "workspaceFactory" : "FileGDB",
                "dataset" : fc_name,  # this is always the second index
                "datasetType" : "esriDTFeatureClass"
            }
            current_layer["name"] = fc_name
            current_layer["uRI"] = f"CIMPATH=map/{fc_name}.xml"
            csf_prf_layers.append(current_layer)

# Reset layers to be only csf/prf layers and group layer
csf_prf_layers.append(layer_dict["layerDefinitions"][-1])
layer_dict["layerDefinitions"] = csf_prf_layers


# Write out the final layerfile
with open(str(INPUTS / 'maritime_layerfile.lyrx'), 'w') as writer:
    writer.writelines(json.dumps(layer_dict, indent=4))

print('Done')
