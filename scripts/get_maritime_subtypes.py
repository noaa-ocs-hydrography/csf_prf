import


class SubtypeReader:
    def __init__(self, gdb_path, feature_dataset=None) -> None:
        self.gdb_path = gdb_path
        self.feature_dataset = feature_dataset

    def start(self):
        # 1. use gdb_path to look through all feature classes in feature dataset
        # 2. set up a set() for unique values
        # 3. loop through all feature classes
        # 4. read subtypes for feature class
        # 5. add a {number: text} dictionary to the set()
        # 6. write out a YAML file in the lookup folder

        pass


if __name__ == "__main__":
    reader = SubtypeReader()
    reader.start()