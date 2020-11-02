from osgeo import ogr, gdal, osr
from os import path, listdir
import tarfile

def gdal_transform(src, tgt, type='vector', srcCRS=None, tgtCRS=None, tgtFormat=None):
    """Transforms src to tgt, changing file type and/or CRS.
    Parameters:
        src (string): Full path of source (original) file.
        tgt (string): Full path of target file.
        type (string): The file general type (vector or raster).
        srcCRS (string): The source file native CRS, if None it is determined from the file metadata.
        tgtCRS (string): The CRS in which the geometries will be projected. If None, no projection will take place.
        tgtFormat (string): The format into which the file will be transformed. It corresponds to GDAL short drivers
            names (https://gdal.org/drivers/vector/index.html & https://gdal.org/drivers/raster/index.html).
            If None, the file will keep the original format.
    """
    gdal.UseExceptions()
    if type == 'vector':
        return vectorTransform(src, tgt, srcCRS=srcCRS, tgtCRS=tgtCRS, tgtFormat=tgtFormat)
    else:
        return rasterTransform(src, tgt, srcCRS=srcCRS, tgtCRS=tgtCRS, tgtFormat=tgtFormat)

def vectorTransform(src, tgt, srcCRS=None, tgtCRS=None, tgtFormat=None):
    """Transforms vector src to tgt, changing file type and/or CRS.
    Parameters:
        src (string): Full path of source (original) file.
        tgt (string): Full path of target file.
        srcCRS (string): The source file native CRS, if None it is determined from the file metadata.
        tgtCRS (string): The CRS in which the geometries will be projected. If None, no projection will take place.
        tgtFormat (string): The format into which the file will be transformed. It corresponds to GDAL vector
            short drivers names (https://gdal.org/drivers/vector/index.html).
            If None, the file will keep the original format.
    """
    src_ds = ogr.Open(src)
    if src_ds is None:
        raise Exception('File driver not supported.')
    layer = src_ds.GetLayer()

    # Reprojection
    if srcCRS is None:
        src_spatial_ref = layer.GetSpatialRef()
    else:
        src_spatial_ref = osr.SpatialReference()
        src_spatial_ref.ImportFromEPSG(srcCRS)
    if tgtCRS is not None:
        tgt_spatial_ref = osr.SpatialReference()
        tgt_spatial_ref.ImportFromEPSG(tgtCRS)
        coordTrans = osr.CoordinateTransformation(src_spatial_ref, tgt_spatial_ref)
    else:
        tgt_spatial_ref = src_spatial_ref
        coordTrans = None

    # Transform file type
    if tgtFormat is None:
        driver = src_ds.GetDriver()
    else:
        driver = ogr.GetDriverByName(tgtFormat)
    if path.exists(tgt):
        driver.DeleteDataSource(tgt)

    if coordTrans is not None:
        if driver.GetName() == 'CSV':
            tgt_ds = driver.CreateDataSource(tgt, options=['GEOMETRY=AS_WKT'])
        else:
            tgt_ds = driver.CreateDataSource(tgt)
        tgt_layer = tgt_ds.CreateLayer(layer.GetName(), srs=tgt_spatial_ref, geom_type=layer.GetGeomType())

        layer_defn = layer.GetLayerDefn()
        for i in range(0, layer_defn.GetFieldCount()):
            field_defn = layer_defn.GetFieldDefn(i)
            tgt_layer.CreateField(field_defn)

        tgt_layer_defn = tgt_layer.GetLayerDefn()
        feature = layer.GetNextFeature()
        while feature:
            geom = feature.GetGeometryRef()
            geom.Transform(coordTrans)
            tgt_feature = ogr.Feature(tgt_layer_defn)
            tgt_feature.SetGeometry(geom)
            for i in range(0, tgt_layer_defn.GetFieldCount()):
                tgt_feature.SetField(tgt_layer_defn.GetFieldDefn(i).GetNameRef(), feature.GetField(i))
            tgt_layer.CreateFeature(tgt_feature)
            tgt_feature = None
            feature = layer.GetNextFeature()
    else:
        if driver.GetName() == 'CSV':
            tgt_ds = driver.CopyDataSource(src_ds, tgt, options=['GEOMETRY=AS_WKT'])
        else:
            tgt_ds = driver.CopyDataSource(src_ds, tgt)

    src_ds = None
    tgt_ds = None

    result = tgt + '.tar.gz'
    with tarfile.open(result, "w:gz") as tar:
        for file in listdir(tgt):
            tar.add(path.join(tgt, file), arcname=file)

    return result

def rasterTransform(src, tgt, srcCRS=None, tgtCRS=None, tgtFormat=None):
    """Transforms and resamples raster src to tgt, changing file type and/or CRS.
    Parameters:
        src (string): Full path of source (original) file.
        tgt (string): Full path of target file.
        srcCRS (string): The source file native CRS, if None it is determined from the file metadata.
        tgtCRS (string): The CRS in which the raster will be projected. If None, no projection will take place.
        tgtFormat (string): The format into which the file will be transformed. It corresponds to GDAL raster
            short drivers names (https://gdal.org/drivers/raster/index.html).
            If None, the file will keep the original format.
    """
    src_ds = gdal.Open(src, gdal.GA_ReadOnly)
    if src_ds is None:
        raise Exception('File driver not supported.')
    if srcCRS is None:
        src_spatial_ref = src_ds.GetSpatialRef()
    else:
        src_spatial_ref = osr.SpatialReference()
        src_spatial_ref.ImportFromEPSG(srcCRS)
    if tgtCRS is not None:
        tgt_spatial_ref = osr.SpatialReference()
        tgt_spatial_ref.ImportFromEPSG(tgtCRS)
        coordTrans = osr.CoordinateTransformation(src_spatial_ref, tgt_spatial_ref)
    else:
        tgt_spatial_ref = src_spatial_ref
        coordTrans = None

    if tgtFormat is None:
        driver = src_ds.GetDriver()
    else:
        driver = gdal.GetDriverByName(tgtFormat)
    filename = path.splitext(path.basename(src))[0]
    extension = driver.GetMetadataItem(gdal.DMD_EXTENSIONS).split(' ')[0]
    tgt_file = path.join(tgt, filename + '.' + extension)

    mem_ds = gdal.Warp('', src_ds, format='VRT', srcSRS=src_spatial_ref, dstSRS=tgt_spatial_ref)
    tgt_ds = driver.CreateCopy(tgt_file, mem_ds, strict=0)

    src_ds = None
    tgt_ds = None
    mem_ds = None

    result = tgt + '.tar.gz'
    with tarfile.open(result, "w:gz") as tar:
        for file in listdir(tgt):
            tar.add(path.join(tgt, file), arcname=file)

    return result
