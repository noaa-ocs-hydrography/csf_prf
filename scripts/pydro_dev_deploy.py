"""Script for migrating the minimum necessary CSF/PRF files for Pydro24_Dev"""


import shutil
import pathlib

CSF_PRF_TOOLBOX = pathlib.Path(r'C:\Pydro24_Dev\NOAA\site-packages\Python3\svn_repo\HSTB\csf_prf_toolbox')
REPO_FOLDER = pathlib.Path(r'C:\Pydro24_Dev\NOAA\site-packages\Python3\svn_repo\HSTB\csf_prf_toolbox\csf_prf')
INPUTS = pathlib.Path(__file__).parents[1] / 'inputs'
CSF_PRF = pathlib.Path(__file__).parents[1] / 'src' / 'csf_prf'
SRC_FOLDER = CSF_PRF.parents[1]


def clear_folder(folder):
    """Recursively clear contents of a folder"""
    
    for path in folder.iterdir():
        if path.is_file():
            path.unlink()
        else:
            clear_folder(path)
    folder.rmdir()


def deploy_csf_to_pydro():
    # Minimum files needed
    # inputs
    #   /lookups/*
    #   /sql/*
    #   /maritime_layerfile.lyrx
    #   /MCD_maritime_layerfile.lyrx
    # src/csf_prf
    #   /engines/[^run_]*
    #   *Tool.py
    #   *Toolbox.pys
    #   __init__.py
    # README.md

    clear_folder(CSF_PRF_TOOLBOX)
    CSF_PRF_TOOLBOX.mkdir()

    # inputs folder
    shutil.copytree(INPUTS / 'lookups', REPO_FOLDER / 'inputs' / 'lookups', dirs_exist_ok=True)
    shutil.copytree(INPUTS / 'sql', REPO_FOLDER / 'inputs' / 'sql', dirs_exist_ok=True)
    shutil.copy2(INPUTS / 'maritime_layerfile.lyrx', REPO_FOLDER / 'inputs' / 'maritime_layerfile.lyrx')
    shutil.copy2(INPUTS / 'MCD_maritime_layerfile.lyrx', REPO_FOLDER / 'inputs' / 'MCD_maritime_layerfile.lyrx')
    shutil.copy2(INPUTS / '__main__.py', REPO_FOLDER.parents[0] / '__main__.py')


    # src/csf_prf 
    shutil.copytree(CSF_PRF / 'engines', 
                    REPO_FOLDER / 'src' / 'csf_prf' / 'engines', 
                    dirs_exist_ok=True, 
                    ignore=shutil.ignore_patterns('run*.py', '*pycache*'))
    for tool in CSF_PRF.glob('*Tool.py'):
        shutil.copy2(tool, REPO_FOLDER / 'src' / 'csf_prf' / tool.name)
    for tool in CSF_PRF.glob('*Tool*.pyt'):
        shutil.copy2(tool, REPO_FOLDER / 'src' / 'csf_prf' / tool.name)
    shutil.copy2(CSF_PRF / '__init__.py', REPO_FOLDER / 'src' / 'csf_prf' / '__init__.py')
    shutil.copy2(CSF_PRF / '_version.py', REPO_FOLDER / 'src' / 'csf_prf' / '_version.py')


    # pydro specific files
    shutil.copytree(SRC_FOLDER / 'README', REPO_FOLDER.parents[0] / 'README', dirs_exist_ok=True)


def increment_version():
    """Pull code version and write it to the README in Dev"""

    from csf_prf import __version__ as version

    with open(REPO_FOLDER.parents[0] / 'README' / 'README.md', 'r') as reader:
        readme_text = reader.read()
        updated_text = readme_text.replace('{VERSION}', f'v: {version}')
    with open(REPO_FOLDER.parents[0] / 'README' / 'README.md', 'w') as writer:
        writer.write(updated_text)
        print(f'Dev updated to {version}')


if __name__ == "__main__":    
    deploy_csf_to_pydro()
    increment_version()
    print('Done')