import arcpy
import pathlib
import yaml


INPUTS = pathlib.Path(__file__).parents[1] / 'inputs'


class SubtypeReader:
    def __init__(self, gdb_path, feature_dataset=False) -> None:
        self.gdb_path = pathlib.Path(gdb_path)
        self.feature_dataset = feature_dataset
        self.geom_lookup = {
            'P': 'points',
            'L': 'lines',
            'A': 'polygons'
        }
    
    def get_subtypes(self):
        workspace = self.gdb_path / self.feature_dataset if self.feature_dataset else self.gdb_path
        arcpy.env.workspace = str(workspace)
        featureclasses = arcpy.ListFeatureClasses()
        subtype_data = {
            'points': {},
            'lines': {},
            'polygons': {}
        }
        objl_count = set()
        for featureclass in featureclasses:
            geom_type = featureclass[-1]
            subtypes = arcpy.da.ListSubtypes(featureclass) 
            featureclass_data = {}
            for stcode, stdict in list(subtypes.items()):
                for stkey in list(stdict.keys()):
                    if stkey == "Name":  
                        subtype_string = stdict[stkey] 
                        subtype_info = subtype_string.split('_')
                        objl_name = '_'.join(subtype_info[:-1])
                        objl_count.add(objl_name)
                        featureclass_data[objl_name] = {'code': stcode, 'objl_string': subtype_string}
            subtype_key = self.geom_lookup[geom_type]
            subtype_data[subtype_key] |= featureclass_data

        # subtypes were missing these OBJL values:
        # 'CANBNK', 'LAKSHR', 'RIVBNK', 'SQUARE', 'M_COVR', 'M_HDAT', 'M_PROD', 
        # 'M_UNIT', 'C_AGGR', 'C_ASSO', 'C_STAC', '$AREAS', '$LINES', 
        # '$COMPS', '$TEXTS'

        # not found in S57 Data Dictionary:
        # 'm_pyup', 'cvrage', 'brklne', 'usrmrk', 'survey', 'surfac', 'prodpf'
        return subtype_data

    def start(self):
        data = self.get_subtypes()
        self.write_yaml(data, 'all_subtypes')

    def write_yaml(self, feature_data, file_name):
        with open(INPUTS / 'lookups' / f'{file_name}.yaml', 'w') as writer:
            yaml.dump(feature_data, writer, default_flow_style=False)


if __name__ == "__main__": 
    # gdb is a Maritime extension geodatabase created from a maritime XML file and has a .000 file imported into it from the Maritime toolbox
    gdb = r"C:\Users\Stephen.Patterson\Data\Repos\csf_prf\outputs\maritime_extension.geodatabase"
    feature_dataset = "Nautical"
    reader = SubtypeReader(gdb, feature_dataset)
    reader.start()