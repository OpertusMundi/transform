import logging
import json
from os import path, getenv
from time import sleep

from transform.app import app

# Setup/Teardown

def setup_module():
    print(" == Setting up tests for %s"  % (__name__))
    app.config['TESTING'] = True
    pass

def teardown_module():
    print(" == Tearing down tests for %s"  % (__name__))
    pass

# Tests
dirname = path.dirname(__file__)
csv_sample = path.join(dirname, '..', 'test_data/geo.csv')
geojson_sample = path.join(dirname, '..', 'test_data/geo.json')
raster_sample = path.join(dirname, '..', 'test_data/geo.tif')
shape_gz = path.join(dirname, '..', 'test_data/geo.tar.gz')

def test_get_documentation_1():
    with app.test_client() as client:
        res = client.get('/', query_string=dict(), headers=dict())
        assert res.status_code == 200
        r = res.get_json();
        assert not (r.get('openapi') is None)

def test_post_transform_1():
    """Functional Test: POST transform with vector file; prompt response type"""
    with app.test_client() as client:
        data = {
            'resource': (open(shape_gz, 'rb'), 'shape.tar.gz'),
            'src_type': 'vector',
            'to': 'EPSG:3857',
            'response': 'prompt'
        }
        res = client.post('/transform', data=data, content_type='multipart/form-data')
        assert res.status_code == 200
        assert res.get_json() is None
        assert res.is_streamed

def test_post_transform_2():
    """Functional Test: POST transform with raster file; prompt response type"""
    with app.test_client() as client:
        data = {
            'resource': (open(raster_sample, 'rb'), 'geo.tif'),
            'src_type': 'raster',
            'to': 'EPSG:3857',
            'response': 'prompt'
        }
        res = client.post('/transform', data=data, content_type='multipart/form-data')
        assert res.status_code == 200
        assert res.get_json() is None
        assert res.is_streamed

def test_post_transform_3():
    """Functional Test: POST transform client error"""
    with app.test_client() as client:
        data = {
            'resource': (open(raster_sample, 'rb'), 'geo.tif'),
            'src_type': 'vector',
            'to': 'EPSG:3857',
            'response': 'prompt'
        }
        res = client.post('/transform', data=data, content_type='multipart/form-data')
        assert res.status_code == 400

def test_post_transform_4():
    """Functional Test: POST transform with vector file path; deferred response type"""
    with app.test_client() as client:
        data = {
            'resource': shape_gz,
            'src_type': 'vector',
            'to': 'EPSG:3857',
            'response': 'deferred'
        }
        res = client.post('/transform', data=data)
        assert res.status_code == 202
        r = res.get_json()
        assert r.get('filepath') is not None
        assert r.get('ticket') is not None
        filepath = path.join(getenv('OUTPUT_DIR'), r.get('filepath'))
    sleep(0.5)
    assert path.isfile(filepath)

def test_get_status_1():
    """Functional Test: GET status of a ticket"""
    with app.test_client() as client:
        res = client.get('/status/ticket')
        assert res.status_code == 404

def test_get_resource_1():
    """Functional Test: GET status of non existent resource"""
    with app.test_client() as client:
        res = client.get('/resource/ticket')
        assert res.status_code == 404

def test_get_status_and_resource_1():
    """Functional Test: GET status and resource after POST transform"""
    with app.test_client() as client:
        data = {
            'resource': (open(shape_gz, 'rb'), 'shape.tar.gz'),
            'src_type': 'vector',
            'to': 'EPSG:3857',
            'response': 'deferred'
        }
        res = client.post('/transform', data=data, content_type='multipart/form-data')
        assert res.status_code == 202
        r = res.get_json()
        status = r.get('status')
        endpoint = r.get('endpoint')
        assert r.get('ticket') is not None
    assert status is not None
    assert endpoint is not None
    sleep(0.5)
    with app.test_client() as client:
        res_status = client.get(status)
        assert res_status.status_code == 200
        res_endpoint = client.get(endpoint)
        assert res_endpoint.status_code == 200
        assert res_endpoint.get_json() is None
        assert res_endpoint.is_streamed
