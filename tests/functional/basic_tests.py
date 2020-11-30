import logging
import json

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

def test_get_documentation_1():
    with app.test_client() as client:
        res = client.get('/', query_string=dict(), headers=dict())
        assert res.status_code == 200
        r = res.get_json();
        assert not (r.get('openapi') is None)

def test_post_transform_1():
    pass
    with app.test_client() as client:
        # Todo request a transformation ... 
        res = client.post('/transform', data=dict(x=42), headers=dict(foo='Bar'))
        assert res.status_code in [200, 202]
        r = res.get_json();
        # Todo examine response ...

