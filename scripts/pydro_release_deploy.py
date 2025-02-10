"""Script for migrating the minimum necessary CSF/PRF files for Pydro24"""


import shutil
import pathlib

DEV_CSF_PRF_TOOLBOX = pathlib.Path(r'C:\Pydro24_Dev\NOAA\site-packages\Python3\svn_repo\HSTB\csf_prf_toolbox')
RELEASE_CSF_PRF_TOOLBOX = pathlib.Path(r'C:\Pydro24\NOAA\site-packages\Python3\svn_repo\HSTB\csf_prf_toolbox')


def clear_folder(folder):
    """Recursively clear contents of a folder"""
    
    for path in folder.iterdir():
        if path.is_file():
            path.unlink()
        else:
            clear_folder(path)
    folder.rmdir()


def deploy_csf_to_pydro():
    """Clear release folder and copy over the Dev contents"""

    clear_folder(RELEASE_CSF_PRF_TOOLBOX)
    RELEASE_CSF_PRF_TOOLBOX.mkdir()

    shutil.copytree(
        DEV_CSF_PRF_TOOLBOX,
        RELEASE_CSF_PRF_TOOLBOX,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("run*.py", "*pycache*", "*.xml"),
    )


if __name__ == "__main__":    
    deploy_csf_to_pydro()
    print('Done')
