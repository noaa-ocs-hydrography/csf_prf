import json

from osgeo import ogr


class Engine:
    def __init__(self) -> None:
        pass

    def feature_covered_by_upper_scale(self, feature_json, enc_scale):
        """
        Determine if a current Point, LineString, or Polygon intersects an upper scale level ENC extent
        :param dict[str] feature_json: Loaded JSON of current feature
        :param int enc_scale: Current ENC file scale level
        :returns boolean: True or False
        """
        
        if feature_json['geometry'] is None:
            return False
        feature_geometry = ogr.CreateGeometryFromJson(json.dumps(feature_json['geometry']))
        upper_scale = int(enc_scale) + 1
        inside = False
        if upper_scale in self.scale_bounds:
            for xMin, xMax, yMin, yMax in self.scale_bounds[upper_scale]:
                extent_geom = ogr.Geometry(ogr.wkbLinearRing)
                extent_geom.AddPoint(xMin, yMin)
                extent_geom.AddPoint(xMin, yMax)
                extent_geom.AddPoint(xMax, yMax)
                extent_geom.AddPoint(xMax, yMin)
                extent_geom.AddPoint(xMin, yMin)
                extent_polygon = ogr.Geometry(ogr.wkbPolygon)
                extent_polygon.AddGeometry(extent_geom)
            # TODO will there be polygons extending over edge of ENC?
            # Might need to use Contains
            if feature_geometry.Intersects(extent_polygon): 
                inside = True
        return inside

    def reverse(self, geom_list):
        """
        Reverse all the inner polygon geometries
        - Esri inner polygons are supposed to be counterclockwise
        - Shapely.is_ccw() could be used to properly test
        :param list[float] geom_list: 
        :return list[arcpy.Geometry]: List of reversed inner polygon geometry
        """

        return list(reversed(geom_list))