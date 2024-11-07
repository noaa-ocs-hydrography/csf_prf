import json
import pathlib
import arcpy
import json
import copy
import yaml
arcpy.env.overwriteOutput = True


OUTPUTS = pathlib.Path(__file__).parents[1] / 'outputs'
INPUTS = pathlib.Path(__file__).parents[1] / 'inputs'


def build_output_layerfile(points, lines, polygons):
    with open(str(INPUTS / 'layerfile_geometry_template.json'), 'r') as reader:
        layerfile_template = reader.read()
    template = json.loads(layerfile_template)
    output_layerfile = template['Document']
    group_layer = copy.deepcopy(template['GroupLayer'])
    for objl_list in [points, lines, polygons]:
        for objl in objl_list:
            if objl['name']:
                objl_name = f'{objl["name"]}_{objl["abbreviation"]}'
                cim_path = f'CIMPATH=map/{objl_name}.xml'
                group_layer['layers'].append(cim_path)
                geom_template = copy.deepcopy(template[f'{objl["type"]}Layer'])
                geom_template['name'] = f"{objl_name}"
                geom_template['uRI'] = cim_path
                geom_template['featureTable']['dataConnection']['dataset'] = f"main.{objl_name}"
                geom_template['featureTemplates'] = objl['featureTemplates']
                geom_template['renderer']['groups'] = objl['groups']
                output_layerfile['layerDefinitions'].append(geom_template)
                
    # group_layer['layers'].reverse()
    output_layerfile['layerDefinitions'].append(group_layer)

    with open(str(INPUTS / 'MCD_maritime_layerfile.lyrx'), 'w') as writer:
        writer.writelines(json.dumps(output_layerfile, indent=4))


def get_unique_subtype_lookup():
    """
    Create unique codes for all subtypes

    :returns dict[str]: Updated dictionary with unique codes
    """

    with open(str(INPUTS / 'lookups' / 'all_subtypes.yaml'), 'r') as lookup:
        subtype_lookup = yaml.safe_load(lookup)

    for geom_type in subtype_lookup.keys():
        codes = []
        for subtype in subtype_lookup[geom_type].values():
            code = subtype['code']
            if code in codes:
                new_code = code + 1000
                while new_code in codes:
                    new_code += 1
                subtype['code'] = new_code
                codes.append(new_code)
            else:
                codes.append(code)
    return subtype_lookup


def get_layerfile_template():
    with open(str(INPUTS / 'maritime_master_layerfile.lyrx'), 'r') as reader:
        layer_file = reader.read()
    layer_dict = json.loads(layer_file)
    return layer_dict


def load_groups_and_templates(layer_dict):
    points, lines, polygons = [], [], []
    for layer in layer_dict["layerDefinitions"]:
        if layer["name"].endswith("P"):
            if 'featureTemplates' in layer:
                for feature in layer["featureTemplates"]:
                    if feature['name']:
                        geom_dict = {}
                        geom_dict['type'] = 'Point'
                        geom_dict['abbreviation'] = 'P'
                        geom_dict["name"] = '_'.join(feature["name"].split('_')[:-1])
                        geom_dict["featureTemplates"] = [feature]  # groups is a list of dictionaries
                        if 'groups' in layer['renderer']:
                            for group in layer["renderer"]["groups"]:
                                classes = []
                                for class_info in group['classes']:
                                    if class_info['label'] == feature['name']:
                                        classes.append(class_info)
                                        break
                                group_info = copy.deepcopy(group)
                                group_info.pop('heading', None)  # remove attribute heading
                                group_info['classes'] = classes
                                geom_dict["groups"] = [group_info] # groups is a list of dictionaries
                                points.append(geom_dict)
                                break
                    # print('\n', geom_dict)
        elif layer["name"].endswith("L"):
            if 'featureTemplates' in layer:
                for feature in layer["featureTemplates"]:
                    if feature['name']:
                        geom_dict = {}
                        geom_dict['type'] = 'LineString'
                        geom_dict['abbreviation'] = 'L'
                        geom_dict["name"] = '_'.join(feature["name"].split('_')[:-1])
                        geom_dict["featureTemplates"] = [feature] 
                        if 'groups' in layer['renderer']:
                            # Loop through groups and only save the matching OBJL group info
                            for group in layer["renderer"]["groups"]:
                                classes = []
                                for class_info in group['classes']:
                                    if class_info['label'] == feature['name']:
                                        classes.append(class_info)
                                        break
                                group_info = copy.deepcopy(group)
                                group_info.pop('heading', None)
                                group_info['classes'] = classes
                                geom_dict["groups"] = [group_info]
                                lines.append(geom_dict)
                                break
                    # print('\n', geom_dict)
        elif layer["name"].endswith("A"):
            if 'featureTemplates' in layer:
                for feature in layer["featureTemplates"]:
                    if feature['name']:
                        geom_dict = {}
                        geom_dict['type'] = 'Polygon'
                        geom_dict['abbreviation'] = 'A'
                        geom_dict["name"] = '_'.join(feature["name"].split('_')[:-1])
                        geom_dict["featureTemplates"] = [feature] 
                        if 'groups' in layer['renderer']:
                            for group in layer["renderer"]["groups"]:
                                classes = []
                                for class_info in group['classes']:
                                    if class_info['label'] == feature['name']:
                                        classes.append(class_info)
                                        break
                                group_info = copy.deepcopy(group)
                                group_info.pop('heading', None)
                                group_info['classes'] = classes
                                geom_dict["groups"] = [group_info]
                                polygons.append(geom_dict)
                                break
                    # print('\n', geom_dict)
    return points, lines, polygons


def finalize_layerfile_data(points, lines, polygons, unique_subtype_codes):
    name_lookup = {
        'Point': 'features_points_layer_FCSubtype',
        'LineString': 'features_lines_layer_FCSubtype',
        'Polygon': 'features_polygons_layer_FCSubtype',
    }


    for geom in [points, lines, polygons]:
        for objl in geom:
            # Sample feature
            # {
            #   "type" : "CIMRowTemplate",
            #   "name" : "BCNCAR_BeaconCardinal",
            #   "tags" : "Point",
            #   "defaultToolGUID" : "2a8b3331-5238-4025-972e-452a69535b06",
            #   "defaultValues" : {
            #     "type" : "PropertySet",
            #     "propertySetItems" : [
            #       "fcsubtype",
            #       1
            #     ]
            #   }
            # },
            name = objl['name']
            # Sample unique_subtype_codes value
            #   SOUNDG:
            #     code: 1
            #     objl_string: SOUNDG_Soundings
            if name:
                subtype_data = unique_subtype_codes[objl['type']][name]
                print('name:', subtype_data)
                if 'defaultValues' in objl['featureTemplates'][0]: # only 1 template per layer now
                    propertySetItems = objl['featureTemplates'][0]['defaultValues']['propertySetItems']
                    for i, item in enumerate(propertySetItems):
                        if item == 'fcsubtype':
                            objl['featureTemplates'][0]['defaultValues']['propertySetItems'][i+1] = subtype_data['code']

                            # Add long field names as well as short field names
                            objl['featureTemplates'][0]['defaultValues']['propertySetItems'].append(name_lookup[objl['type']])
                            objl['featureTemplates'][0]['defaultValues']['propertySetItems'].append(subtype_data['code'])


            # update codes in groups section
            # Sort groups alphabetically for AGS Pro display
            for group in objl['groups']:
                for subtype in group['classes']:
                    subtype_string = subtype['label']
                    name = '_'.join(subtype_string.split('_')[:-1])
                    if name in unique_subtype_codes[objl['type']]:
                        subtype_data = unique_subtype_codes[objl['type']][name]
                        subtype['values'][0]['fieldValues'][0] = str(subtype_data['code'])

    return points, lines, polygons


def process():
    layer_dict = get_layerfile_template()
    points, lines, polygons = load_groups_and_templates(layer_dict)
    unique_subtype_codes = get_unique_subtype_lookup()
    points, lines, polygons = finalize_layerfile_data(points, lines, polygons, unique_subtype_codes)
    build_output_layerfile(points, lines, polygons)
    print('Done')

if __name__ == "__main__":
    process()