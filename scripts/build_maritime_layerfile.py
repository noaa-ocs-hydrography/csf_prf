import json
import pathlib
import arcpy
import json
import copy
import yaml
arcpy.env.overwriteOutput = True


OUTPUTS = pathlib.Path(__file__).parents[1] / 'outputs'
INPUTS = pathlib.Path(__file__).parents[1] / 'inputs'


def get_unique_subtype_codes(subtype_lookup):
    """
    Create unique codes for all subtypes

    :param dict[str] subtype_lookup: all_subtypes.yaml as dictionary
    :returns dict[str]: Updated dictionary with unique codes
    """

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
with open(str(INPUTS / 'lookups' / 'all_subtypes.yaml'), 'r') as lookup:
    subtype_lookup = yaml.safe_load(lookup)
unique_subtype_codes = get_unique_subtype_codes(subtype_lookup)


for geom in [points, lines, polygons]:
    for feature in geom['featureTemplates']:
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
        name = '_'.join(feature['name'].split('_')[:-1])
        # Sample unique_subtype_codes value
        #   SOUNDG:
        #     code: 1
        #     objl_string: SOUNDG_Soundings
        if name:
            subtype_data = unique_subtype_codes[geom['name']][name]

            if 'defaultValues' in feature:
                propertySetItems = feature['defaultValues']['propertySetItems']

                for i, item in enumerate(propertySetItems):
                    if item == 'fcsubtype':
                        feature['defaultValues']['propertySetItems'][i+1] = subtype_data['code']

                        # Add long field names as well as short field names
                        feature['defaultValues']['propertySetItems'].append(name_lookup[geom['name']])
                        feature['defaultValues']['propertySetItems'].append(subtype_data['code'])


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
            if name in unique_subtype_codes[geom['name']]:
                subtype_data = unique_subtype_codes[geom['name']][name]
                subtype['values'][0]['fieldValues'][0] = str(subtype_data['code'])


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
            current_layer["featureTable"]["dataConnection"]["dataset"] = f'main.{fc_name}'
            current_layer["featureTable"]["dataConnection"]["sqlQuery"] = f'select OBJECTID,Shape,AGEN,CATBRG,CATCAN,CATCBL,CATCOA,CATNAV,CATRUN,CATSLC,CATTRK,COLOUR,COLPAT,CONDTN,CONRAD,CONVIS,DATEND,DATSTA,DRVAL1,DRVAL2,ELEVAT,FFPT_RIND,FIDN,FIDS,GRUP,HEIGHT,HORACC,HORCLR,HORLEN,HORWID,ICEFAC,INFORM,LNAM,LNAM_REFS,NATCON,NINFOM,NOBJNM,NTXTDS,OBJL,OBJNAM,ORIENT,PEREND,PERSTA,PICREP,PRIM,QUASOU,RCID,RECDAT,RECIND,RVER,SCALE_LVL,SCAMAX,SCAMIN,SORDAT,SORIND,SOUACC,STATUS,TECSOU,TRAFIC,TXTDSC,VALDCO,VERACC,VERCCL,VERCLR,VERCOP,VERCSA,VERDAT,VERLEN,WATLEV,hypcat,OBJL_NAME,asgnmt,invreq,FCSubtype from main.{fc_name}'
            current_layer["name"] = f'{fc_name}'
            current_layer["uRI"] = f"CIMPATH=map/{fc_name}.xml"
            csf_prf_layers.append(current_layer)

# Reset layers to be only csf/prf layers and group layer
csf_prf_layers.append(layer_dict["layerDefinitions"][-1])
layer_dict["layerDefinitions"] = csf_prf_layers

# Write out the final layerfile
with open(str(INPUTS / 'maritime_layerfile.lyrx'), 'w') as writer:
    writer.writelines(json.dumps(layer_dict, indent=4))


# Setting featureTemplates and groups in the MCD_maritime_layerfile
with open(str(INPUTS / 'MCD_maritime_layerfile_template.lyrx'), 'r') as reader:
    layer_file = reader.read()
MCD_layer_dict = json.loads(layer_file)

for layer in MCD_layer_dict["layerDefinitions"]:
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
for layer in MCD_layer_dict["layerDefinitions"]:
    current_layer = copy.deepcopy(layer)
    if 'featureTable' in current_layer:
        fc_name = f"{current_layer['name']}_features"
        current_layer["featureTable"]["dataConnection"] = {
                "type" : "CIMStandardDataConnection",
                "workspaceConnectionString" : "UTHENTICATION_MODE=OSA;DATABASE=.\\{~}.gpkg",
                "workspaceFactory" : "Sql",
                "sqlQuery" : f"select OBJECTID_1,Shape,AGEN,BCNSHP,BOYSHP,BUISHP,CALSGN,CATBUA,CATDPG,CATFOG,CATLAM,CATLIT,CATLMK,\
                    CATLND,CATOBS,CATOFP,CATROS,CATSIL,CATSPM,CATWRK,CLSDEF,CLSNAM,COLOUR,COLPAT,COMCHA,CONDTN,CONRAD,CONVIS,CURVEL,\
                        DATEND,DATSTA,DEPTH,ELEVAT,ESTRNG,EXCLIT,EXPSOU,FFPT_RIND,FIDN,FIDS,FUNCTN,GRUP,HEIGHT,INFORM,LITCHR,LITVIS,LNAM,\
                            LNAM_REFS,MARSYS,MLTYLT,NATCON,NATION,NATQUA,NATSUR,NINFOM,NOBJNM,NTXTDS,OBJL,OBJNAM,ORIENT,PEREND,PERSTA,\
                                PICREP,PRIM,PRODCT,QUASOU,RCID,RECDAT,RECIND,RESTRN,RVER,RYRMGV,SCALE_LVL,SCAMAX,SCAMIN,SECTR1,SECTR2,\
                                    SIGFRQ,SIGGEN,SIGGRP,SIGPER,SIGSEQ,SORDAT,SORIND,SOUACC,STATUS,SYMINS,TECSOU,TOPSHP,TXTDSC,VALACM,\
                                        VALMAG,VALMXR,VALNMR,VALSOU,VERACC,VERDAT,VERLEN,WATLEV,OBJL_NAME,asgnmt,invreq,FCSubtype,\
                                            OBJECTID,Join_Count,TARGET_FID,POSACC,QUAPOS,RCID_1,RCNM,RUIN,RVER_1,SCALE_LVL_1 from main.%{fc_name}",
                "dataset" : f'main.%{fc_name}',  # this is always the second index
                "datasetType" : "esriDTFeatureClass"
            }
        current_layer["name"] = fc_name
        current_layer["uRI"] = f"CIMPATH=map/{fc_name}.xml"
        csf_prf_layers.append(current_layer)

# Reset layers to be only csf/prf layers and group layer
csf_prf_layers.append(MCD_layer_dict["layerDefinitions"][-1])
MCD_layer_dict["layerDefinitions"] = csf_prf_layers

with open(str(INPUTS / 'MCD_maritime_layerfile.lyrx'), 'w') as writer:
    writer.writelines(json.dumps(MCD_layer_dict, indent=4))

print('Done')
