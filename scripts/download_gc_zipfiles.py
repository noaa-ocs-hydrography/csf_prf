import requests
import arcpy
import sys
import zipfile
import pathlib
import urllib3

from collections import defaultdict

CSFPRF_MODULE = pathlib.Path(__file__).parents[1] / 'src'
sys.path.append(str(CSFPRF_MODULE))

from csf_prf.helpers.tools import get_config_item

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


OUTPUTS = pathlib.Path(__file__).parents[1] / 'outputs'


def download_gc_zips(gc_zips: dict[str, list[str]], session: requests.Session = None) -> None:
    """
    Downloads or copies all GC zip files for each ENC cell.
    :param gc_zips: Dictionary of {enc_id: [list of UNC paths or URLs]}
    :param output_folder: Base pathlib.Path (e.g., OUTPUTS)
    """
    geographic_cells = OUTPUTS / "geographic_cells"
    count = 0

    if session is None:
        session = requests.Session()
        session.verify = False

    for enc, zip_paths in gc_zips.items():
        enc_folder = geographic_cells / enc
        enc_folder.mkdir(parents=True, exist_ok=True)

        for path_str in zip_paths:
            if not path_str:
                continue

            src_path = pathlib.Path(path_str)
            basefilename = src_path.name
            output_file = enc_folder / basefilename

            # 1. Skip if already downloaded
            if output_file.exists():
                arcpy.AddMessage(f" - Already downloaded GC: {basefilename}")
                continue

            count += 1
            arcpy.AddMessage(f" - Downloading GC {count}: {basefilename} for {enc}")

            url = path_str
            try:
                with session.get(url, stream=True) as response:
                    response.raise_for_status()
                    with open(output_file, "wb") as f:
                        # 64 KB chunks are much faster than 128 bytes
                        for chunk in response.iter_content(chunk_size=65536):
                            f.write(chunk)
            except requests.RequestException as e:
                arcpy.AddWarning(f"Failed to download {basefilename}: {e}")


def get_token():
    """
    Connected to churnpi ArcGIS Server token service
    :returns str: ArcGIS Server token
    """

    token_url = get_config_item('GC', 'AGS_TOKEN')
    key = get_config_item('GC', 'CSF_USER_KEY')
    auth = get_config_item('GC', 'CSF_USER_AUTH')
    translate_auth = get_translated_csf_auth(key, auth)

    payload = {
        "username": "CSF_PRF_User",
        "password": translate_auth,
        "client": "requestip",
        "expiration": 60,   # In minutes
        "f": "json"
    }
    response = requests.post(token_url, data=payload, verify=False)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise Exception(f"Token generation error: {data['error']['message']}")
        
    return data["token"]


def get_translated_csf_auth(key, auth):
    """Obtain MCD information"""

    from cryptography.fernet import Fernet
    setup = Fernet(key)
    return setup.decrypt(auth).decode()


def unzip_enc_files(file_ending: str = "shp") -> None:
    """
    Extracts all .zip files found under the output folder.
    :param output_folder: Base pathlib.Path
    :param file_ending: Extension to check if extraction is already complete (e.g., 'shp')
    """
    ext = file_ending.lstrip(".")

    output_folder = OUTPUTS / 'geographic_cells'
    for zipped_file in output_folder.rglob("*.zip"):
        # Target extraction folder named after the zip (e.g., .../GC10845/)
        extract_folder = zipped_file.parent / zipped_file.stem

        # Marker file to check if already extracted (e.g., .../GC10845.shp or inside extract_folder)
        expected_marker = zipped_file.with_suffix(f".{ext}")

        if not expected_marker.exists() and not extract_folder.exists():
            arcpy.AddMessage(f" - Extracting: {zipped_file.name}")
            extract_folder.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(zipped_file, "r") as z:
                    z.extractall(extract_folder)
            except zipfile.BadZipFile:
                arcpy.AddWarning(f"Corrupt zip file skipped: {zipped_file.name}")
        else:
            arcpy.AddMessage(f" - Already unzipped: {zipped_file.name}")

    for gc_file in output_folder.rglob('*.zip'):
        arcpy.AddMessage(f' - Remove unzipped: {gc_file.name}')
        gc_file.unlink()


def query_compass_service(enc_id: str) -> list[str]:
    print(f'Querying GC files for ENC: {enc_id}')

    compass_url = get_config_item('GC', 'COMPASS_SERVICE')  # need to be on VPN
    token = get_token()
    params = {
        "where": f"product='{enc_id}' AND source_type='GC' AND is_enc=True",
        "outFields": "product,source_path,source_type,source_number,is_enc",  # TODO remove Product and is_enc?
        "returnGeometry": "false",
        "f": "json",
        "token": token
    }
    # Query with requests to use token
    response = requests.post(compass_url, data=params, verify=False)
    response.raise_for_status()
    json_data = response.json()
    data = defaultdict(list)
    for feature in json_data.get("features", []):
        attrs = feature.get("attributes", {})
        source_path = attrs.get("source_path").split('\\')
        source_type = attrs.get("source_type")
        source_number = attrs.get("source_number")
        updated_source_path = f"{source_path[0]}/{source_path[1]}"
        # http://ocs-mcd-webapps2.nos.noaa/converted_data/2024/GC/GC11603/GC_11603_shape.zip
        zip_path = f"{updated_source_path}/{source_type}{source_number}/{source_type}_{source_number}_shape.zip"
        direct_link = f"{get_config_item('GC', 'FILE_SERVER')}/{zip_path}"
        data[enc_id].append(direct_link)
    return data


def run() -> None:
    enc_list = ['US3DE01M', 'US3EC08M']
    for enc in enc_list:
        dreg_links = query_compass_service(enc)
        download_gc_zips(dreg_links)
    unzip_enc_files()


if __name__ == "__main__":
    import time
    start = time.time()
    run()
    print(f'Done: {(time.time() - start)/60} minutes')
