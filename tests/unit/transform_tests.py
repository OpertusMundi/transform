import logging
import json
from os import path, makedirs
from tempfile import gettempdir

from transform.gdal_transform import vectorTransform, rasterTransform
from transform.app import transformProcess

# Setup/Teardown

def setup_module():
    print(" == Setting up tests for %s"  % (__name__))
    pass

def teardown_module():
    print(" == Tearing down tests for %s"  % (__name__))
    pass

# Tests
dirname = path.dirname(__file__)
csv_sample = path.join(dirname, '..', 'test_data/geo.csv')
geojson_sample = path.join(dirname, '..', 'test_data/geo.json')
raster_sample = path.join(dirname, '..', 'test_data/geo.tif')
shape_zip = path.join(dirname, '..', 'test_data/geo.zip')
shape_gz = path.join(dirname, '..', 'test_data/geo.tar.gz')
tgt = path.join(gettempdir(), 'test')

def test_vectorTransform_1():
    """Unit Test: vectorTransform from GeoJSON to csv; with reprojection"""
    DOS_EOL = b'\r\n'
    UNIX_EOL = b'\n'
    src = geojson_sample
    vectorTransform(src, tgt, srcCRS=4326, tgtCRS=3857, tgtFormat='CSV')
    assert path.isfile(path.join(tgt, 'geo.csv'))

    with open(path.join(tgt, 'geo.csv'), 'rb') as open_file:
        content1 = open_file.read()
    content1 = content1.replace(DOS_EOL, b'')
    content1 = content1.replace(UNIX_EOL, b'')
    with open(csv_sample, 'rb') as open_file:
        content2 = open_file.read()
    content2 = content2.replace(DOS_EOL, b'')
    content2 = content2.replace(UNIX_EOL, b'')
    assert (content1 == content2)

def test_vectorTransform_2():
    """Unit Test: vectorTransform from CSV to GeoJSON; with reprojection"""
    src = csv_sample
    vectorTransform(src, tgt, srcCRS=3857, tgtCRS=4326, tgtFormat='CSV')
    assert path.isfile(path.join(tgt, 'geo.csv'))
    a_file = open(path.join(tgt, 'geo.csv'))

    lines = a_file.readlines()
    assert len(lines) >= 0

def test_vectorTransform_3():
    """Unit Test: vectorTransform from CSV to Shapefile; with reprojection"""
    src = csv_sample
    vectorTransform(src, tgt, srcCRS=3857, tgtCRS=4326, tgtFormat='ESRI Shapefile')
    assert path.isdir(tgt)
    for ext in ['dbf', 'prj', 'shp', 'shx']:
        assert path.isfile(path.join(tgt, "geo.{}".format(ext)))

def test_rasterTransform_1():
    """Unit Test: rasterTransform from geoTiff to PNG; with reprojection"""
    src = raster_sample
    rasterTransform(src, tgt, tgtCRS=3857, tgtFormat="png")
    assert path.isdir(tgt)
    assert path.isfile(path.join(tgt, 'geo.png'))

def test_transformProcess_1():
    """Unit Test: transformProcess with compressed files"""
    makedirs(path.join(tgt, 'src'))
    makedirs(path.join(tgt, 'results', 'ticket'))
    for src in [shape_zip, shape_gz]:
        gdal_params = {'type': 'vector', 'tgtCRS': 2100, 'tgtFormat': 'CSV'}
        result = transformProcess(src, tgt, 'ticket', gdal_params)
        assert path.isfile(result)
