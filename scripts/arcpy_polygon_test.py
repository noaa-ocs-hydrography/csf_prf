import arcpy
import pathlib


INPUTS = pathlib.Path(__file__).parents[1] / 'inputs'


def reverse(geom_list):
    """
    Reverse all the inner polygon geometries
    - Esri inner polygons are supposed to be counterclockwise
    - Shapely.is_ccw() could be used to properly test
    """

    return list(reversed(geom_list))

def split_inner_polygons(layer):
    """Get all inner and outer polygon feature geometries"""

    inner_features = []
    outer_features = []
    total_nones = 0
    fields = { # Use for information.  FME used these 6 fields. Might be different sometimes.
        9: 'snm',
        16: 'priority',
        17: 'scale',
        19: 'sub_locali',
        20: 'registry_n',
        # 23: 'invreq'
    }
    for row in arcpy.da.SearchCursor(layer, ['SHAPE@'] + list(fields.values())):
        geom_num = 0
        row_geom = row[0]
        attributes = row[1:]
        for geometry in row_geom:
            if None in geometry:
                # find indexes of all Nones
                none_indexes = [i for i, point in enumerate(geometry) if point is None]
                total_nones += len(none_indexes)
                if len(none_indexes) == 1: # only 1 inner polygon
                    outer_features.append({'attributes': attributes, 
                                            'geometry': geometry[0:none_indexes[0]]}) # First polygon is outer
                    inner_features.append({'attributes': attributes, 
                                            'geometry': reverse(geometry[none_indexes[0]+1:len(geometry)])}) # capture last inner
                else: # > 1 inner polygon
                    # split array on none indexes
                    for i, (current, next) in enumerate(zip(none_indexes[:-1], none_indexes[1:])):
                        if i == 0: # first one
                            outer_features.append({'attributes': attributes, 
                                                    'geometry': geometry[0:current]}) # First polygon is outer
                            inner_features.append({'attributes': attributes, 
                                                    'geometry': reverse(geometry[current+1:next])}) # capture first inner
                        elif i == len(none_indexes) - 2: # last one
                            inner_features.append({'attributes': attributes, 
                                                    'geometry': reverse(geometry[current+1:next])}) # capture current inner
                            inner_features.append({'attributes': attributes, 
                                                    'geometry': reverse(geometry[next+1:len(geometry)])}) # capture last inner
                        else: # in between
                            inner_features.append({'attributes': attributes, 
                                                    'geometry': reverse(geometry[current+1:next])}) # capture current inner
            else:
                outer_features.append({'attributes': attributes, 'geometry': geometry})
                    
            geom_num += 1
                        
    print(f'outer: {len(outer_features)}')
    print(f'inner: {len(inner_features)}')
    print(list(outer_features[0]['geometry']))
    print(list(inner_features[0]['geometry'])[:3])

if __name__ == "__main__":
    layer = str(INPUTS / 'OPR_A325_KR_24_Sheets_09262023_FULL_AREA_NO_LIDAR.shp')
    split_inner_polygons(layer)