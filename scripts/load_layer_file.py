import json
import pathlib

INPUTS = pathlib.Path(__file__).parents[1] / 'inputs'
layerfile_name = 'MCD_maritime_layerfile'
layer_path = str(INPUTS / f'{layerfile_name}.lyrx')
print(layer_path)

with open(layer_path, 'r') as reader:
    layer_file = reader.read()
layer_dict = json.loads(layer_file)