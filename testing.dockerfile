# vim: set syntax=dockerfile:

FROM osgeo/gdal:alpine-normal-3.1.0 as build-stage-1

RUN apk update && apk add gcc musl-dev python3-dev
RUN pip3 install --upgrade pip && pip3 install --prefix=/usr/local "pyproj>=2.6.0,<2.7.0"


FROM osgeo/gdal:alpine-normal-3.1.0
ARG VERSION

RUN apk update && apk add --no-cache sqlite py3-yaml

ENV VERSION="${VERSION}"
ENV PYTHON_VERSION="3.8"
ENV PYTHONPATH="/usr/local/lib/python${PYTHON_VERSION}/site-packages"

COPY --from=build-stage-1 /usr/local/ /usr/local

RUN pip3 install --upgrade pip
COPY requirements.txt requirements-testing.txt ./
RUN pip3 install --prefix=/usr/local -r requirements.txt -r requirements-testing.txt

ENV FLASK_APP="transform" FLASK_ENV="testing" FLASK_DEBUG="false"
ENV OUTPUT_DIR="./output" SECRET_KEY_FILE="./secret_key"
