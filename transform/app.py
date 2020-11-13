from flask import Flask
from flask import request, current_app, make_response, send_file
from werkzeug.utils import secure_filename
from flask_cors import CORS
from os import path, getenv, makedirs, stat
from shutil import move
from tempfile import gettempdir
from uuid import uuid4
from hashlib import md5
import pyproj
from osgeo import ogr, gdal
from datetime import datetime, timezone
from flask_executor import Executor
from apispec import APISpec
from apispec_webframeworks.flask import FlaskPlugin
import zipfile
import tarfile
from . import db
from .gdal_transform import gdal_transform
from .logging import getLoggers
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
        db_result = dbc.execute('SELECT requested_time, filesize FROM tickets WHERE ticket = ?;', [ticket]).fetchone()
        time = db_result['requested_time']
        filesize = db_result['filesize']
        execution_time = round((datetime.now(timezone.utc) - time.replace(tzinfo=timezone.utc)).total_seconds(), 3)
        dbc.execute('UPDATE tickets SET result=?, success=?, status=1, execution_time=?, comment=? WHERE ticket=?;', [filepath, success, execution_time, comment, ticket])
        dbc.commit()
        accountLogger(ticket=ticket, success=success, execution_start=time, execution_time=execution_time, comment=comment, filesize=filesize)

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

#Logging
mainLogger, accountLogger = getLoggers()

# OpenAPI documentation
spec = APISpec(
    title="Transform API",
    version="0.0.1",
    info=dict(
        description="A simple service to transform a spatial (vector or raster) file. Transformation includes reprojection into another spatial reference system (and resampling in case of raster reprojection) and/or change of the file format (e.g. Shapefile into CSV).",
        contact={"email": "pmitropoulos@getmap.gr"}
    ),
    externalDocs={"description": "GitHub", "url": "https://github.com/OpertusMundi/transform"},
    openapi_version="3.0.2",
    plugins=[FlaskPlugin()],
)

# Initialize app
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
    filesize = stat(src_path).st_size
    dbc = db.get_db()
    dbc.execute('INSERT INTO tickets (ticket, filesize) VALUES(?, ?);', [ticket, filesize])
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
    return make_response(spec.to_dict(), 200)

@app.route("/transform", methods=["POST"])
def transform():
    """Transform a vector or raster file
    ---
    post:
      summary: Transform a vector or raster file
      tags:
        - Transform
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                resource:
                  type: string
                  format: binary
                  description: The spatial file.
                src_type:
                  type: string
                  enum: [vector, raster]
                  description: The type of the spatial file (*vector* or *raster*).
                from:
                  type: string
                  description: The spatial file native CRS. If not given, it will be extracted from the data.
                to:
                  type: string
                  description: The CRS that the spatial file will be projected into. If not given, no reprojection will take place.
                format:
                  type: string
                  description: The expected format of the resulting file in the form of GDAL drivers short names. (See GDAL documentation for [vectors](https://gdal.org/drivers/vector/index.html) and [rasters](https://gdal.org/drivers/raster/index.html).) If not given, the source file format will be used.
                response:
                  type: string
                  enum: [prompt, deferred]
                  default: prompt
                  description: Determines whether the transform proccess should be promptly initiated (*prompt*) or queued (*deferred*). In the first case, the response waits for the result, in the second the response is immediate returning a ticket corresponding to the request.
              required:
                - resource
                - src_type
          application/x-www-form-urlencoded:
            schema:
              type: object
              properties:
                resource:
                  type: string
                  description: The spatial file resolvable path.
                src_type:
                  type: string
                  enum: [vector, raster]
                  description: The type of the spatial file (*vector* or *raster*).
                from:
                  type: string
                  description: The spatial file native CRS. If not given, it will be extracted from the data.
                to:
                  type: string
                  description: The CRS that the spatial file will be projected into. If not given, no reprojection will take place.
                format:
                  type: string
                  description: The expected format of the resulting file in the form of GDAL drivers short names. (See GDAL documentation for [vectors](https://gdal.org/drivers/vector/index.html) and [rasters](https://gdal.org/drivers/raster/index.html).) If not given, the source file format will be used.
                response:
                  type: string
                  enum: [prompt, deferred]
                  default: prompt
                  description: Determines whether the transform proccess should be promptly initiated (*prompt*) or queued (*deferred*). In the first case, the response waits for the result, in the second the response is immediate returning a ticket corresponding to the request.
              required:
                - resource
                - src_type
      responses:
        200:
          description: Transform completed and returned.
          content:
            application/json:
              schema:
                type: object
                properties:
                  filepath:
                    type: string
                    description: The resulting file path
            application/x-tar:
              schema:
                type: string
                format: binary
        202:
          description: Accepted for processing, but transform has not been completed.
          content:
            application/json:
              schema:
                oneOf:
                  -
                    type: object
                    properties:
                      ticket:
                        type: string
                        description: The ticket corresponding to the request.
                      endpoint:
                        type: string
                        description: The *resource* endpoint to get the resulting resource when ready.
                      status:
                        type: string
                        description: The *status* endpoint to poll for the status of the request.
                  -
                    type: object
                    properties:
                      ticket:
                        type: string
                        description: The ticket corresponding to the request.
                      filepath:
                        type: string
                        description: The *resource* endpoint to get the resultin resource when ready.
          links:
            GetStatus:
              operationId: getStatus
              parameters:
                ticket: '$response.body#/ticket'
              description: The `ticket` value returned in the response can be used as the `ticket` parameter in `GET /status/{ticket}`.
        400:
          description: Client error.
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
        mainLogger.info('Client error: %s', str(e))
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
        filesize = stat(src_file).st_size
        start_time = datetime.now()
        try:
            result = transformProcess(src_file, tgt_path, gdal_params)
        except Exception as e:
            execution_time = round((datetime.now() - start_time).total_seconds(), 3)
            accountLogger(success=False, execution_start=start_time, execution_time=execution_time, comment=str(e), filesize=filesize)
            return make_response(str(e), 400)
        execution_time = round((datetime.now() - start_time).total_seconds(), 3)
        accountLogger(success=True, execution_start=start_time, execution_time=execution_time, filesize=filesize)
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
        return make_response(response, 202)

@app.route("/status/<ticket>")
def status(ticket):
    """Get the status of a specific ticket.
    ---
    get:
      summary: Get the status of a transform request.
      operationId: getStatus
      description: Returns the status of a request corresponding to a specific ticket.
      tags:
        - Status
      parameters:
        - name: ticket
          in: path
          description: The ticket of the request
          required: true
          schema:
            type: string
      responses:
        200:
          description: Ticket found and status returned.
          content:
            application/json:
              schema:
                type: object
                properties:
                  completed:
                    type: boolean
                    description: Whether transformation process has been completed or not.
                  success:
                    type: boolean
                    description: Whether transformation process completed succesfully.
                  comment:
                    type: string
                    description: If transformation has failed, a short comment describing the reason.
                  requested:
                    type: string
                    format: datetime
                    description: The timestamp of the request.
                  execution_time(s):
                    type: integer
                    description: The execution time in seconds.
        404:
          description: Ticket not found.
    """
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
    """Get the resulted resource associated with a specific ticket.
    ---
    get:
      summary: Get the resource associated to a transform request.
      description: Returns the resource resulted from a transform request corresponding to a specific ticket.
      tags:
        - Resource
      parameters:
        - name: ticket
          in: path
          description: The ticket of the request
          required: true
          schema:
            type: string
      responses:
        200:
          description: The transformed compressed spatial file.
          content:
            application/x-tar:
              schema:
                type: string
                format: binary
        404:
          description: Ticket not found or transform has not been completed.
        507:
          description: Resource does not exist.
    """
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

with app.test_request_context():
    spec.path(view=transform)
    spec.path(view=status)
    spec.path(view=resource)
