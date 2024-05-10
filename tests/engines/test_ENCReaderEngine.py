import pytest
import pathlib
import os

from csf_prf.engines.ENCReaderEngine import ENCReaderEngine

"""
Unit tests need to havea  .pth file set in your conda ENV that points to CSF-PRF repo
"""

REPO = pathlib.Path(__file__).parents[2]
INPUTS = REPO / 'inputs'
ENC_FILE = str(INPUTS / 'US4MA04M.000')


@pytest.fixture
def victim():
    class Param:
        @property
        def valueAsText(self):
            return ENC_FILE

    victim = ENCReaderEngine(param_lookup={"enc_files": Param()}, sheets_layer=None)
    return victim


def test___init__(victim):
    assert hasattr(victim, 'geometries')
    assert hasattr(victim, 'gdb_name')
    assert victim.gdb_name == 'csf_features'
    assert 'Point' in victim.geometries.keys()


def test_get_all_fields(victim):
    features = [
        {'geojson': {
            'properties': {
                'one': 1,
                'two': 2
            }
        }},
        {'geojson': {
            'properties': {
                'three': 3,
                'four': 4
            }
        }}
    ]
    results = victim.get_all_fields(features)
    assert 'one' in results
    assert 'two' in results
    assert 'three' in results
    assert 'four' in results


def test_get_aton_lookup(victim):
    results = victim.get_aton_lookup()
    assert type(results) == type([])
    assert results[0] == 'BCNCAR'


def test_get_feature_records(victim):
    victim.set_driver()
    victim.split_multipoint_env()
    victim.get_feature_records()
    assert len(victim.geometries['Point']['features']) == 5109
    assert len(victim.geometries['LineString']['features']) == 1857
    assert len(victim.geometries['Polygon']['features']) == 1660


def test_get_vector_records(victim):
    victim.set_driver()
    victim.return_primitives_env()
    victim.get_vector_records()
    assert 'QUAPOS' in victim.geometries['Point'].keys()
    assert victim.geometries['Point']['QUAPOS'][0]['geojson']['properties']['QUAPOS'] == 4


def test_return_primitives_env(victim):
    victim.return_primitives_env()
    assert os.environ["OGR_S57_OPTIONS"] == "RETURN_PRIMITIVES=ON"


def test_split_multipoint_env(victim):
    victim.split_multipoint_env()
    assert os.environ["OGR_S57_OPTIONS"] == "SPLIT_MULTIPOINT=ON"
