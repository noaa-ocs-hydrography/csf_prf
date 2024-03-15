import pytest
import pathlib
import arcpy

from engines.CompositeSourceCreatorEngine import CompositeSourceCreatorEngine

"""
Unit tests need to havea  .pth file set in your conda ENV that points to CSF-PRF repo
"""

REPO = pathlib.Path(__file__).parents[2]
INPUTS = REPO / 'inputs'
SHAPEFILE = str(INPUTS / 'OPR_A325_KR_24_Sheets_09262023_FULL_AREA_NO_LIDAR.shp')


@pytest.fixture
def victim():
    victim = CompositeSourceCreatorEngine(param_lookup=[])
    return victim


def test_add_invreq_column(victim):
    
    layer = arcpy.management.CopyFeatures(SHAPEFILE, r'memory\test_layer')
    fields = [field.name for field in arcpy.ListFields(layer)]
    assert 'invreq' not in fields
    victim.add_invreq_column(layer)
    fields = [field.name for field in arcpy.ListFields(layer)]
    assert 'invreq' in fields


def test_esri_convert_sheets(victim):
    class Param:
        @property
        def valueAsText(self):
            return SHAPEFILE
    victim.param_lookup = {
        'sheets': Param()
    }
    outer, inner = victim.esri_convert_sheets()
    assert len(outer) == 34
    assert len(inner) == 96