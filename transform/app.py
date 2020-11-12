from flask import Flask
from flask import request, current_app, make_response, send_file
from werkzeug.utils import secure_filename
from flask_cors import CORS
from os import path, getenv, makedirs
from shutil import move
from tempfile import gettempdir
from uuid import uuid4
from hashlib import md5
import pyproj
from osgeo import ogr, gdal
from datetime import datetime, timezone
from flask_executor import Executor
import zipfile
import tarfile
from . import db
from .gdal_transform import gdal_transform
import json

def mkdir(path):
    """Creates recursively the path, ignoring warnings for existing directories."""
    try:
        makedirs(path)
    except OSError:
        pass

def executorCallback(future):
    """The callback function called when a job has completed."""
    ticket, result, success, comment = future.result()
    if result is not None:
        rel_path = datetime.now().strftime("%y%m%d")
        mkdir(path.join(getenv('OUTPUT_DIR'), rel_path))
        rel_path = path.join(rel_path, path.basename(result))
        filepath = path.join(getenv('OUTPUT_DIR'), rel_path)
        move(result, filepath)
    else:
        filepath = None
    with app.app_context():
        dbc = db.get_db()
        time = dbc.execute('SELECT requested_time FROM tickets WHERE ticket = ?;', [ticket]).fetchone()['requested_time']
        execution_time = round((datetime.now(timezone.utc) - time.replace(tzinfo=timezone.utc)).total_seconds())
        dbc.execute('UPDATE tickets SET result=?, success=?, status=1, execution_time=?, comment=? WHERE ticket=?;', [filepath, success, execution_time, comment, ticket])
        dbc.commit()

def transformProcess(src_file, tgt_path, gdal_params):
    """Checks whether the file is compressed and call gdal_transform."""
    if not path.isdir(src_file):
        src_path = path.dirname(src_file)
        if tarfile.is_tarfile(src_file):
            handle = tarfile.open(src_file)
            handle.extractall(src_path)
            src_file = src_path
            handle.close()
        elif zipfile.is_zipfile(src_file):
            with zipfile.ZipFile(src_file, 'r') as handle:
                handle.extractall(src_path)
            src_file = src_path
    return gdal_transform(src_file, tgt_path, **gdal_params)

if getenv('OUTPUT_DIR') is None:
    raise Exception('Environment variable OUTPUT_DIR is not set.')
app = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    SECRET_KEY='dev',
    DATABASE=path.join(app.instance_path, 'transform.sqlite'),
)

# Ensure the instance folder exists and initialize application, db and executor.
mkdir(app.instance_path)
db.init_app(app)
executor = Executor(app)
executor.add_default_done_callback(executorCallback)

#Enable CORS
if getenv('CORS') is not None:
    if getenv('CORS')[0:1] == '[':
        origins = json.loads(getenv('CORS'))
    else:
        origins = getenv('CORS')
    cors = CORS(app, origins=origins)
@executor.job
def enqueue(ticket, src_path, tgt_path, gdal_params):
    """Enqueue a transform job (in case requested response type is 'deferred')."""
    dbc = db.get_db()
    dbc.execute('INSERT INTO tickets (ticket) VALUES(?);', [ticket])
    dbc.commit()
    try:
        result = transformProcess(src_path, tgt_path, gdal_params)
    except Exception as e:
        return (ticket, None, 0, str(e))
    return (ticket, result, 1, None)

def getTransformParams(request):
    """Get and check the http request parameters for transformation."""
    errors = []
    params = {}
    args = request.values
    from_crs = args.get('from')
    try:
        if from_crs is not None:
            crs = pyproj.crs.CRS.from_user_input(from_crs)
    except Exception as e:
        message = "Unrecognized source crs"
        errors.append(message)
    if from_crs is not None:
        params['from_crs'] = crs.to_epsg()
    else:
        params['from_crs'] = None
    to_crs = args.get('to')
    try:
        if to_crs is not None:
            crs = pyproj.crs.CRS.from_user_input(to_crs)
    except Exception as e:
        message = "Unrecognized target crs"
        errors.append(message)
    if to_crs is not None:
        params['to_crs'] = crs.to_epsg()
    else:
        params['to_crs'] = None
    src_type = args.get('src_type')
    if src_type is None or (src_type != 'vector' and src_type != 'raster'):
        message = "Missing or wrong required parameter 'src_type'"
        errors.append(message)
    params['src_type'] = src_type
    params['format'] = args.get('format')
    if params['format'] is not None:
        if src_type == 'raster':
            driver = gdal.GetDriverByName(params['format'])
        else:
            driver = ogr.GetDriverByName(params['format'])
        if driver is None:
            message = "Unsupported driver for ouput format %s" % (params['format'])
            errors.append(message)
    response_type = args.get('response') or 'prompt'
    if response_type != 'prompt' and response_type != 'deferred':
        message = "Parameter 'response' can take one of: 'prompt', 'deferred'"
        errors.append(message)
    params['response'] = response_type
    resource = args.get('resource')
    if resource is not None and not path.isfile(resource) and not path.isdir(resource):
        message = "File not found."
        errors.append(message)
    params['resource'] = resource
    if len(errors) > 0:
        raise Exception(' / '.join(errors))
    return params

@app.route("/")
def index():
    """The index route, gives info about the API endpoints."""
    current_app.logger.info("transform: params=%s headers=%s environ=%s", \
        dict(request.values), dict(request.headers), dict(request.environ))
    transform_params = {"from": "<CRS>", "to": "<CRS>", "format": "<FORMAT>", "src_type": "<raster|vector>", "format": "<GDAL Driver>", "response": "<prompt|deferred>"}
    get = {
        "/transform": {"params": {**transform_params, "path": "<source file path>"}, "response": "json"},
        "/status/<ticket>": {"response": "json"},
        "/resource/<ticket>": {"response": "stream"}
    }
    post = {"/transform": {"params": transform_params, "body": {"resource": "stream"}, "response": "json|stream"}}
    response = make_response({"GET": get, "POST": post}, 200)
    return response

@app.route("/transform", methods=["POST"])
def transform():
    """The transformation endpoint.

    It expects the following HTTP form parameters:
        -from: The CRS of the source file (otherwise, CRS will be determined).
        -to: The CRS in which the file will be translated.
        -src_type*: vector or raster.
        -format: The expected format of the returned file.
        -response: prompt (default) or deferred.
        -resource*: A resovable path of source file or the source file itself.
        * Required

    In case the source file is uploaded in the body of the request (resource), the resulting
    file is returned as a stream, otherwise (the case resource represents a resolvable path)
    the response contains a path of the resulted file.
    However, one could determine by adjusting the value of 'response' whether initiates promptly
    the process of transformation and waits for the result ('prompt') or initiates a background
    process and gets a ticket instead ('deferred').
    """
    # Create tmp directory used for storage of uploaded
    # (and created, in case of prompt response) files.
    tempdir = getenv('TEMPDIR') or gettempdir()
    tempdir = path.join(tempdir, 'gdal-transform')
    mkdir(tempdir)
    # Get the http request parameters
    try:
        params = getTransformParams(request)
    except Exception as e:
        current_app.logger.error(e)
        return make_response({'Error': str(e)}, 400)

    # Create a unique ticket for the request
    ticket = md5(str(uuid4()).encode()).hexdigest()
    # ticket = str(uuid4()).replace('-', '')

    # The relative path for storing resulted files in the form /date/ticket/.
    rel_path = datetime.now().strftime("%y%m%d")

    # Form the source full path of the uploaded file
    if params['resource'] is not None:
        src_file = params['resource']
    elif request.files['resource'] is not None:
        resource = request.files['resource']

        src_path = path.join(tempdir, 'src', ticket)
        mkdir(src_path)
        src_file = path.join(src_path, secure_filename(resource.filename))
        resource.save(src_file)
    else:
        return make_response({"Error": "Missing resource."}, 400)

    # Create the response according to requested response type
    gdal_params = {'type': params['src_type'], 'srcCRS': params['from_crs'], 'tgtCRS': params['to_crs'], 'tgtFormat': params['format']}
    tgt_path = path.join(tempdir, ticket)
    mkdir(tgt_path)
    if params['response'] == 'prompt':
        try:
            result = transformProcess(src_file, tgt_path, gdal_params)
        except Exception as e:
            return make_response(str(e), 400)
        if params['resource'] is not None:
            mkdir(path.join(getenv('OUTPUT_DIR'), rel_path))
            rel_path = path.join(rel_path, path.basename(result))
            move(result, path.join(getenv('OUTPUT_DIR'), rel_path))
            return make_response({'filepath': rel_path}, 200)
        else:
            return send_file(result, as_attachment=True)
    else:
        enqueue.submit(ticket, src_file, tgt_path, gdal_params=gdal_params)
        if params['resource'] is not None:
            response = { "ticket": ticket, "filepath": path.join(rel_path, ticket + '.tar.gz') }
        else:
            response = { "ticket": ticket, "endpoint": "/resource/%s" % (ticket), "status": "/status/%s" % (ticket)}
        return make_response(response, 200)

@app.route("/status/<ticket>")
def status(ticket):
    """Get the status of a specific ticket."""
    if ticket is None:
        return make_response('Ticket is missing.', 400)
    dbc = db.get_db()
    results = dbc.execute('SELECT status, success, requested_time, execution_time, comment FROM tickets WHERE ticket = ?', [ticket]).fetchone()
    if results is not None:
        if results['success'] is not None:
            success = bool(results['success'])
        else:
            success = None
        return make_response({"completed": bool(results['status']), "success": success, "requested": results['requested_time'], "execution_time(s)": results['execution_time'], "comment": results['comment']}, 200)
    return make_response('Not found.', 404)

@app.route("/resource/<ticket>")
def resource(ticket):
    """Get the resulted resource associated with a specific ticket."""
    if ticket is None:
        return make_response('Resource ticket is missing.', 400)
    dbc = db.get_db()
    rel_path = dbc.execute('SELECT result FROM tickets WHERE ticket = ?', [ticket]).fetchone()['result']
    if rel_path is None:
        return make_response('Not found.', 404)
    file = path.join(getenv('OUTPUT_DIR'), rel_path)
    if not path.isfile(file):
        return make_response('Resource does not exist.', 507)
    return send_file(file, as_attachment=True)
