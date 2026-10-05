import os
import pathlib
from osgeo import gdal, ogr

gdal.AllRegister()
gdal.UseExceptions()


CSFPRF_MODULE = pathlib.Path(__file__).parents[0] / 'src'
import sys
sys.path.append(str(CSFPRF_MODULE))

from csf_prf.engines.class_code_lookup import class_codes as CLASS_CODES


# Paths Setup
OUTPUTS = pathlib.Path(__file__).parents[1] / 'outputs'

ENC_FILE = OUTPUTS / 'US4AK4TM.000'
GPKG_FILE = OUTPUTS / 'enc_data.gpkg'
# ---------------------------------------------------------------------------
# S-57 Environment Configuration
# ---------------------------------------------------------------------------
def set_s57_env_for_features():
    """Configure GDAL options for reading S-57 feature objects."""
    gdal.SetConfigOption("OGR_S57_OPTIONS", "SPLIT_MULTIPOINT=ON,ADD_SOUNDING_CLEANUP=ON")


def set_s57_env_for_vectors():
    """Configure GDAL options for reading S-57 vector primitives (QUAPOS)."""
    gdal.SetConfigOption("OGR_S57_OPTIONS", "RETURN_PRIMITIVES=ON,SPLIT_MULTIPOINT=ON")


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------
def read_enc_features(enc_path: str | pathlib.Path) -> dict[str, list[ogr.Feature]]:
    """Reads S-57 Feature records and categorizes them by geometry type."""
    set_s57_env_for_features()
    ds = ogr.Open(str(enc_path))
    if ds is None:
        raise FileNotFoundError(f"Could not open ENC file: {enc_path}")

    features_by_type = {
        "Point": [],
        "LineString": [],
        "Polygon": []
    }

    for i in range(ds.GetLayerCount()):
        layer = ds.GetLayerByIndex(i)
        layer.ResetReading()

        for feat in layer:
            geom = feat.GetGeometryRef()
            if geom is None:
                continue

            geom_name = geom.GetGeometryName()
            if geom_name in ["POINT", "MULTIPOINT"]:
                features_by_type["Point"].append(feat.Clone())
            elif geom_name in ["LINESTRING", "MULTILINESTRING"]:
                features_by_type["LineString"].append(feat.Clone())
            elif geom_name in ["POLYGON", "MULTIPOLYGON"]:
                features_by_type["Polygon"].append(feat.Clone())

    ds = None
    return features_by_type


def read_enc_vectors(enc_path: str | pathlib.Path) -> list[ogr.Feature]:
    """Reads S-57 Vector primitive records containing QUAPOS attributes."""
    set_s57_env_for_vectors()
    ds = ogr.Open(str(enc_path))
    if ds is None:
        raise FileNotFoundError(f"Could not open ENC file: {enc_path}")

    quapos_records = []
    
    for i in range(ds.GetLayerCount()):
        layer = ds.GetLayerByIndex(i)
        layer.ResetReading()

        for feat in layer:
            quapos_idx = feat.GetFieldIndex("QUAPOS")
            if quapos_idx != -1 and feat.IsFieldSet(quapos_idx):
                quapos_records.append(feat.Clone())

    ds = None
    return quapos_records


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------
def write_features_to_geopackage(
    features: list[ogr.Feature], 
    gpkg_path: pathlib.Path, 
    layer_name: str, 
    geom_type: int
):
    """
    Aggregates features into an in-memory layer, converts OBJL integer codes
    to string names via CLASS_CODES lookup, sanitizes field names/widths, 
    and writes cleanly into the target GeoPackage layer.
    """
    if not features:
        print(f" - Layer '{layer_name}' has no features to write. Skipping.")
        return

    # 1. Driver setup & 3D geometry detection
    mem_driver = ogr.GetDriverByName("MEM") or ogr.GetDriverByName("Memory")
    mem_ds = mem_driver.CreateDataSource("mem_ds")
    
    srs = ogr.osr.SpatialReference()
    srs.ImportFromEPSG(4326)

    # Detect 3D (Z) coordinates (e.g., SOUNDG depth points)
    has_z = any(
        feat.GetGeometryRef() is not None and feat.GetGeometryRef().Is3D() 
        for feat in features[:100]
    )
    if has_z and geom_type == ogr.wkbPoint:
        geom_type = ogr.wkbPoint25D

    mem_layer = mem_ds.CreateLayer(layer_name, srs, geom_type)

    # 2. Union unique field definitions across ALL features
    field_defns = {}
    for feat in features:
        defn = feat.GetDefnRef()
        for i in range(defn.GetFieldCount()):
            f_defn = defn.GetFieldDefn(i)
            f_name = f_defn.GetName()
            
            if f_name and f_name.strip() != "" and f_name.lower() != "fid":
                if f_name not in field_defns:
                    # Sanitize to string type with unlimited width to avoid list/truncation warnings
                    new_f_defn = ogr.FieldDefn(f_name, ogr.OFTString)
                    new_f_defn.SetWidth(0)
                    field_defns[f_name] = new_f_defn

    # Ensure OBJL_NAME field definition exists in the output schema
    if "OBJL_NAME" not in field_defns:
        objl_name_defn = ogr.FieldDefn("OBJL_NAME", ogr.OFTString)
        objl_name_defn.SetWidth(0)
        field_defns["OBJL_NAME"] = objl_name_defn

    # Create fields on the memory layer
    for f_defn in field_defns.values():
        mem_layer.CreateField(f_defn)

    # 3. Copy features into memory layer & compute OBJL_NAME
    mem_layer.StartTransaction()
    mem_layer_defn = mem_layer.GetLayerDefn()
    
    for feat in features:
        new_feat = ogr.Feature(mem_layer_defn)
        geom = feat.GetGeometryRef()
        if geom:
            new_feat.SetGeometry(geom.Clone())
        
        # Populate attributes
        for i in range(feat.GetFieldCount()):
            f_name = feat.GetFieldDefnRef(i).GetName()
            if f_name in field_defns and feat.IsFieldSet(i):
                val = feat.GetField(i)
                if isinstance(val, (list, tuple)):
                    val_str = ",".join(map(str, val))
                    new_feat.SetField(f_name, val_str)
                else:
                    new_feat.SetField(f_name, feat.GetFieldAsString(i))

        # --- CLASS_CODES LOOKUP FOR OBJL ---
        objl_idx = feat.GetFieldIndex("OBJL")
        if objl_idx != -1 and feat.IsFieldSet(objl_idx):
            try:
                objl_val = feat.GetFieldAsInteger(objl_idx)
                objl_name = CLASS_CODES.get(objl_val, CLASS_CODES['OTHER'])[0]
                new_feat.SetField("OBJL_NAME", objl_name)
            except Exception:
                new_feat.SetField("OBJL_NAME", "OTHER")

        mem_layer.CreateFeature(new_feat)
        
    mem_layer.CommitTransaction()

    # 4. Drop existing GeoPackage layer if present
    if gpkg_path.exists():
        gpkg_driver = ogr.GetDriverByName("GPKG")
        out_ds = gpkg_driver.Open(str(gpkg_path), update=1)
        if out_ds is not None:
            for idx in range(out_ds.GetLayerCount()):
                lyr = out_ds.GetLayerByIndex(idx)
                if lyr.GetName() == layer_name:
                    out_ds.DeleteLayer(idx)
                    break
            out_ds = None  # Release file lock

    # 5. Translate memory layer to GeoPackage
    options = gdal.VectorTranslateOptions(
        format="GPKG",
        layerName=layer_name,
        accessMode="update" if gpkg_path.exists() else None,
        options=["-overwrite"] if gpkg_path.exists() else []
    )
    
    gdal.VectorTranslate(str(gpkg_path), mem_ds, options=options)
    mem_ds = None


# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------
def main():
    print(f"Reading S-57 ENC File: {ENC_FILE}")

    # 1. Read Feature records
    features = read_enc_features(ENC_FILE)
    print(
        f"Features extracted - "
        f"Points: {len(features['Point'])}, "
        f"Lines: {len(features['LineString'])}, "
        f"Polygons: {len(features['Polygon'])}"
    )

    # 2. Read Vector/QUAPOS records
    vectors = read_enc_vectors(ENC_FILE)
    print(f"Vector QUAPOS records extracted: {len(vectors)}")

    # 3. Write layers out to GeoPackage
    print(f"Writing layers to GeoPackage: {GPKG_FILE}")

    write_features_to_geopackage(
        features["Point"], GPKG_FILE, layer_name="enc_points", geom_type=ogr.wkbPoint
    )
    write_features_to_geopackage(
        features["LineString"], GPKG_FILE, layer_name="enc_lines", geom_type=ogr.wkbLineString
    )
    write_features_to_geopackage(
        features["Polygon"], GPKG_FILE, layer_name="enc_polygons", geom_type=ogr.wkbPolygon
    )

    if vectors:
        write_features_to_geopackage(
            vectors, GPKG_FILE, layer_name="enc_quapos_vectors", geom_type=ogr.wkbUnknown
        )

    print("Completed processing ENC to GeoPackage successfully.")


if __name__ == "__main__":
    main()