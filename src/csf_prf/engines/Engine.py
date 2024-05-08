import arcpy


class Engine:
    def __init__(self) -> None:
        pass

    def add_column_and_constant(self, layer, column, expression=None, field_type='TEXT', field_length=255, nullable=False) -> None:
        """
        Add the asgnment column and 
        :param arcpy.FeatureLayerlayer layer: In memory layer used for processing
        """

        if nullable:
            arcpy.management.AddField(layer, column, field_type, field_length=field_length, field_is_nullable='NULLABLE')
        else:
            arcpy.management.AddField(layer, column, field_type, field_length=field_length)
            arcpy.management.CalculateField(
                layer, column, expression, expression_type="PYTHON3", field_type=field_type
            )

    def reverse(self, geom_list):
        """
        Reverse all the inner polygon geometries
        - Esri inner polygons are supposed to be counterclockwise
        - Shapely.is_ccw() could be used to properly test
        :return list[arcpy.Geometry]: List of reversed inner polygon geometry
        """

        return list(reversed(geom_list))