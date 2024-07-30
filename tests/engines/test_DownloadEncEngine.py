import pytest
import pathlib
import os

from csf_prf.engines.DownloadEncEngine import DownloadEncEngine


'''
Unit tests need to havea  .pth file set in your conda ENV that points to CSF-PRF repo
'''


REPO = pathlib.Path(__file__).parents[2]
INPUTS = REPO / 'inputs'
OUTPUTS = REPO / 'outputs'
SHEETS = str(INPUTS / 'G322_Sheets_01302024.shp')
ENC_FILE = str(INPUTS / 'US4GA17M.000')
MULTIPLE_ENC = ENC_FILE + ';' + str(INPUTS / 'US5SC21M.000')


@pytest.fixture
def victim():
    class Param:
        def __init__(self, path):
            self.path = path

        @property
        def valueAsText(self):
            return self.path

    param_lookup = {
        'sheets': Param(SHEETS), 
        'enc_files': Param(),
        'output_folder': Param(str(OUTPUTS))
    }
    victim = DownloadEncEngine(param_lookup=param_lookup)
    victim.set_driver()
    return victim


def test___init__(victim):
    assert victim.output_folder == str(OUTPUTS)
    assert hasattr(victim, 'xml_path')
    assert victim.sheets_layer == SHEETS