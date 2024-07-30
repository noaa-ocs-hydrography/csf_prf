import arcpy
import pathlib


class SubtypeReader:
    def __init__(self, gdb_path, feature_dataset=None) -> None:
        self.gdb_path = pathlib.Path(gdb_path)
        self.feature_dataset = feature_dataset
        self.subtypes = set()


    def start(self):
        # 1. use gdb_path to look through all feature classes in feature dataset
        # 2. set up a set() for unique values
        self.get_subtypes()
        # abbreivatied name, string name, subtype number
        # 3. loop through all feature classes
        # 4. read subtypes for feature class
        # 5. add a {number: text} dictionary to the set()
        # 6. write out a YAML file in the lookup folder

        pass

    def get_subtypes(self):
        
        feature_dataset_path = self.gdb_path / self.feature_dataset
        arcpy.env.workspace = str(feature_dataset_path)
        featureclasses = arcpy.ListFeatureClasses()
        for featureclass in featureclasses:
            print(featureclass)
            subtypes = arcpy.da.ListSubtypes(featureclass) 
            for stcode, stdict in list(subtypes.items()):
                for stkey in list(stdict.keys()):
                    if stkey == "FieldValues":
                        print("Fields:")
                        fields = stdict[stkey]
                        for field, fieldvals in list(fields.items()):
                            if field == "FCSubtype":
                                print(f"Code: {stcode}, Name: {field}, values: {fieldvals[0]}")
                    if stkey == "Name":  
                        subtype_string = stdict[stkey] 
                        print(subtype_string)  

                break       


        # subtypes = arcpy.da.ListSubtypes("C:/data/Boston.gdb/Boundary")



if __name__ == "__main__": 
    gdb = r"C:\Users\aubrey.mccutchan\Data\GIS Folder\Maritime.gdb"
    feature_dataset = "Nautical"
    reader = SubtypeReader(gdb, feature_dataset)
    reader.start()