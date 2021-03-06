# Transform micro-service

[![Build Status](https://ci.dev-1.opertusmundi.eu:9443/api/badges/OpertusMundi/transform/status.svg?ref=refs/heads/master)](https://ci.dev-1.opertusmundi.eu:9443/OpertusMundi/transform)

## Description

The purpose of this package is to deploy a micro-service which transforms a spatial (vector or raster) file. Transformation includes reprojection into another spatial reference system (and resampling in case of raster reprojection) and/or change of the file format (e.g. shapefile into csv). The service is built on *flask* and *sqlite* and GDAL is used for transformation.

## Installation

The package requires at least Python 3.7, *GDAL 3.1.* and *sqlite3*. To install with **pip**:
```
pip install git+https://github.com/OpertusMundi/transform.git
```
Initialize sqlite database by running:
```
flask init-db
```

The following environment variables should be set:
- `FLASK_ENV`: `development` or `production`.
- `FLASK_APP`: `transform` (if running in a container, this is automatically set)
- `OUTPUT_DIR`: The location (full path), which will be used to store the resulting files (for the case of *deferred* request, see below).
- (optional) `TEMPDIR`: The location of storing temporary files. If not set, the system temporary path location will be used.
- (optional) `CORS`: List or string of allowed origins.
- (optional) `LOGGING_FILE_CONFIG`: Logging configuration file, otherwise the default logging configuration file will be used.
- (optional) `LOGGING_ROOT_LEVEL`: The level of detail for the root logger; one of `DEBUG`, 'INFO', `WARNING`.

A development server could be started with:
```
flask run
```

## Usage

You can browse the full [OpenAPI documentation](https://opertusmundi.github.io/transform/)

The main endpoint */transform* is accessible via a **POST** request and expects the following parameters:
- **src_type** (required): *Vector* (default) or *raster*.
- **resource** (required): A string representing the spatial file resolvable path **or** a stream containing the spatial file.
- **from**: The spatial file native CRS. If not given, it will be extracted from the data.
- **to**: The CRS that the spatial file will be projected into. If not given, no reprojection will take place.
- **format**: The expected format of the resulting file in the form of GDAL short drivers name. (See GDAL documentation [for vectors](https://gdal.org/drivers/vector/index.html) and [for rasters](https://gdal.org/drivers/raster/index.html).) If not given, the source file format will be used.
- **response**: *prompt* (default) or *deferred* (see below).

The source file is contained in the *resource* field of the request. There are two possible ways to pass the source file to the service:
1. The *resource* has a string value representing the resolvable path of the spatial file. In this case the resulting file is again determined by its path indicated in the response.
2. The *resource* is the spatial file itself uploaded in the body of the request. In this case the response is a stream returning the resulting file.

In each case, the requester could determine whether the service should promptly initiate the transformation process and wait to finish in order to return the response (**prompt** response) or should response immediately returning a ticket with the request (**deferred** response). In latter case, one could request */status/\<ticket\>* and */resource/\<ticket\>* in order to get the status and the resulting file corresponding to a specific ticket.

Once deployed, info about the endpoints and their possible HTTP parameters could be obtained by requesting the index of the service, i.e. for development environment http://localhost:5000.

## Build and run as a container

Copy `.env.example` to `.env` and configure if needed (e.g `FLASK_ENV` variable).

Copy `compose.yml.example` to `compose.yml` (or `docker-compose.yml`) and adjust to your needs (e.g. specify volume source locations etc.). You will at least need to configure the network (inside `compose.yml`) to attach to. 

For example, you can create a private network named `opertusmundi_network`:

    docker network create --attachable opertusmundi_network

Build:

    docker-compose -f compose.yml build

Prepare the following files/directories:

   * `./data/transform.sqlite`:  the SQLite database (an empty database, if running for first time)
   * `./data/secret_key`: file needed for signing/encrypting session data
   * `./logs`: a directory to keep logs under
   * `./output`: a directory to be used as root of a hierarchy of output files

Start application:
    
    docker-compose -f compose.yml up


## Run tests

Copy `compose-testing.yml.example` to `compose-testing.yml` and adjust to your needs. This is a just a docker-compose recipe for setting up the testing container.

Run nosetests (in an ephemeral container):

    docker-compose -f compose-testing.yml run --rm --user "$(id -u):$(id -g)" nosetests -v

