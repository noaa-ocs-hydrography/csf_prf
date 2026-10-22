import requests
import arcpy
import re
import zipfile
import pathlib
import shutil

from collections import defaultdict
from bs4 import BeautifulSoup


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

            # 2. Case A: Direct Windows UNC Network Share access (\\nos.noaa\...)
            # On the NOAA network, direct file copy is significantly faster than HTTP
            if src_path.exists():
                shutil.copy2(src_path, output_file)

            # 3. Case B: HTTP / Web API Download (Fallback)
            else:
                # If using your DREG_API endpoint or a direct URL:
                # e.g., url = dreg_api.replace('{Path}', str(src_path.parent)).replace('{BaseFileName}', basefilename)
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
        

def query_dreg_links(enc_id: str) -> list[str]:
    print(f'Querying GC files for ENC: {enc_id}')

    enc_gc_url = "https://ocs-vs-appd7.nos.noaa/arcgis/rest/services/Joel_Harrington/ENC_GCData_InWork/FeatureServer/0"
    fields = ["Cell", "DREGLink"]

    with arcpy.da.SearchCursor(enc_gc_url, fields, where_clause=f"Cell = '{enc_id}'") as cursor:
        data = defaultdict(list)
        for cell, dreg_link in cursor:
            data[cell].append(dreg_link)
    return data


def query_gc_zip_links(dreg_links: dict[str, list[str]]) -> dict[str, list[str]]:
    gc_zips = {}
    session = requests.Session()
    session.verify = False  # Reuse session with SSL bypass

    for enc_id, urls in dreg_links.items():
        print(f'- ENC - {enc_id} has {len(urls)} GC files')
        gc_zips[enc_id] = []

        for url in urls:
            if not url:
                continue

            try:
                resp = session.get(url, timeout=15)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                file_path = None

                # Method 1: Look for a table cell/label containing "Digital file"
                label_tag = soup.find(lambda tag: tag.name in ["th", "td", "strong", "b", "span", "dt"] 
                                      and "Digital file" in tag.get_text())

                if label_tag:
                    if label_tag.name in ["th", "td"]:
                        next_cell = label_tag.find_next_sibling("td")
                        if next_cell:
                            file_path = next_cell.get_text(strip=True)
                    
                    if not file_path:
                        next_node = label_tag.find_next_sibling()
                        if next_node:
                            file_path = next_node.get_text(strip=True)

                # Method 2 (Fallback): Regex search across the whole text for the NOAA UNC zip path
                if not file_path:
                    match = re.search(r"(\\\\nos\.noaa\\[^\r\n<>\"']+\.zip)", resp.text, re.IGNORECASE)
                    if match:
                        file_path = match.group(1).strip()

                if file_path:
                    gc_zips[enc_id].append(file_path)
                else:
                    print(f"[{enc_id}] 'Digital file' not found at: {url}")

            except requests.RequestException as e:
                print(f"[{enc_id}] Failed to load {url}: {e}")

    return gc_zips


def run() -> None:
    enc_list = ['US3DE01M', 'US3EC08M']
    for enc in enc_list:
        dreg_links = query_dreg_links(enc)
        gc_links = query_gc_zip_links(dreg_links)
        download_gc_zips(gc_links)
        unzip_enc_files()


if __name__ == "__main__":
    run()