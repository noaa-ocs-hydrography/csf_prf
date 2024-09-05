import pathlib
import yaml
import os
import requests

INPUTS = pathlib.Path(__file__).parents[1] / 'inputs'
OUTPUTS = pathlib.Path(__file__).parents[1] / 'outputs'


def get_config_item(parent: str, child: str=False) -> tuple[str, int]:
    """Load config and return speciific key"""

    with open(str(INPUTS / 'lookups' / 'config.yaml'), 'r') as lookup:
        config = yaml.safe_load(lookup)
        parent_item = config[parent]
        if child:
            return parent_item[child]
        else:
            return parent_item
        

def download_gc(download_inputs) -> None:
    output_folder, enc, path, basefilename = download_inputs

    enc_folder = output_folder / enc
    enc_folder.mkdir(parents=True, exist_ok=True)
    dreg_api = get_config_item('GC', 'DREG_API').replace('{Path}', path).replace('{BaseFileName}', basefilename)
    print('api:', dreg_api)
    gc_folder = enc_folder / basefilename.replace('.zip', '')
    print('folder:', gc_folder)
    if not os.path.exists(gc_folder):
        print(f'Downloading GC: {basefilename}')
        enc_zip = requests.get(dreg_api)
        output_file = enc_folder / basefilename
        with open(output_file, 'wb') as file:
            for chunk in enc_zip.iter_content(chunk_size=128):
                file.write(chunk)


if __name__ == "__main__":
    download_gc((OUTPUTS, 'US3LA02M', '2024\\GC', 'GC11852.zip'))