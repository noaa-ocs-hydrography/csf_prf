import pytest
import pathlib
import sys
import arcpy

CSFPRF_MODULE = pathlib.Path(__file__).parents[1]
sys.path.append(str(CSFPRF_MODULE))
from csf_prf.helpers.tools import Param
from csf_prf.engines.MHWBufferEngine import MHWBufferEngine


REPO = pathlib.Path(__file__).parents[2]
INPUTS = REPO / 'inputs'
OUTPUTS = REPO / 'outputs'


@pytest.fixture
def victim():
    victim = MHWBufferEngine(
        param_lookup={'enc_files': Param(str(str(INPUTS / 'US2EC02M.000') + ';' + str(INPUTS / 'US5SC21M.000'))),
                      'output_folder': Param(str(OUTPUTS))})
    return victim


@pytest.fixture
def willing_victim(victim):
    victim.set_driver()
    victim.return_primitives_env()
    victim.get_scale_bounds()
    return victim
    

def test___init__(victim):
    assert hasattr(victim, 'intersected')
    assert hasattr(victim, 'scale_bounds')
    assert 'dissolved' in victim.layers.keys()
    assert 'LNDARE' in victim.features.keys()
    assert 'LNDARE' in victim.layers.keys()


def test_get_scale_bounds(willing_victim):
    assert 2 in willing_victim.scale_bounds.keys()
    assert 5 in willing_victim.scale_bounds.keys()
    assert 3 not in willing_victim.scale_bounds.keys()


def test_get_high_water_features(willing_victim):
    assert not willing_victim.features['COALNE']
    assert not willing_victim.features['SLCONS']
    assert not willing_victim.features['LNDARE']
    willing_victim.get_high_water_features()
    assert len(willing_victim.features['COALNE']) == 1082
    assert len(willing_victim.features['SLCONS']) == 415
    assert len(willing_victim.features['LNDARE']) == 530


def test_erase_lndare_features(willing_victim):
    willing_victim.get_high_water_features()
    willing_victim.build_area_features()
    assert int(arcpy.management.GetCount(willing_victim.layers['LNDARE'])[0]) == 530
    willing_victim.erase_lndare_features()
    assert int(arcpy.management.GetCount(willing_victim.layers['LNDARE'])[0]) == 521
