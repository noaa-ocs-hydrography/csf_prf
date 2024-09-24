"""Script for migrating the miniimum necessary CSF/PRF files for Pydro"""


import shutil
import os
import pathlib


CSF_PRF_TOOLBOX = pathlib.Path(r'C:\Pydro24_Dev\NOAA\site-packages\Python3\svn_repo\HSTB\csf_prf_toolbox\csf_prf')
INPUTS = pathlib.Path(__file__).parents[1] / 'inputs'
CSF_PRF = pathlib.Path(__file__).parents[1] / 'src' / 'csf_prf'
SRC_FOLDER = CSF_PRF.parents[1]


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


    # inputs folder
    shutil.copytree(INPUTS / 'lookups', CSF_PRF_TOOLBOX / 'inputs' / 'lookups', dirs_exist_ok=True)
    shutil.copytree(INPUTS / 'sql', CSF_PRF_TOOLBOX / 'inputs' / 'sql', dirs_exist_ok=True)
    shutil.copy2(INPUTS / 'maritime_layerfile.lyrx', CSF_PRF_TOOLBOX / 'inputs' / 'maritime_layerfile.lyrx')
    shutil.copy2(INPUTS / 'MCD_maritime_layerfile.lyrx', CSF_PRF_TOOLBOX / 'inputs' / 'MCD_maritime_layerfile.lyrx')


    # src/csf_prf 
    shutil.copytree(CSF_PRF / 'engines', 
                    CSF_PRF_TOOLBOX / 'src' / 'csf_prf' / 'engines', 
                    dirs_exist_ok=True, 
                    ignore=shutil.ignore_patterns('run*.py'))
    for tool in CSF_PRF.glob('*Tool*.py'):
        shutil.copy2(tool, CSF_PRF_TOOLBOX / 'src' / 'csf_prf' / tool.name)
    for tool in CSF_PRF.glob('*Tool*.pyt'):
        shutil.copy2(tool, CSF_PRF_TOOLBOX / 'src' / 'csf_prf' / tool.name)
    shutil.copy2(CSF_PRF / '__init__.py', CSF_PRF_TOOLBOX / 'src' / 'csf_prf' / '__init__.py')


    # pydro specific files
    shutil.copy2(SRC_FOLDER / 'README.md', CSF_PRF_TOOLBOX.parents[0] / 'README.md')


if __name__ == "__main__":
    deploy_csf_to_pydro()
    print('Done')