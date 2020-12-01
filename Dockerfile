# vim: set syntax=dockerfile:

FROM osgeo/gdal:alpine-normal-3.1.0 as build-stage-1

RUN apk update && apk add gcc musl-dev python3-dev
RUN pip3 install --upgrade pip
RUN pip3 install --prefix=/usr/local "pyproj>=2.6.0,<2.7.0"


FROM osgeo/gdal:alpine-normal-3.1.0
ARG VERSION

LABEL language="python"
LABEL framework="flask"
LABEL usage="transform microservice for rasters and vectors"

RUN apk update && apk add --no-cache sqlite py3-yaml

ENV VERSION="${VERSION}"
ENV PYTHON_VERSION="3.8"
ENV PYTHONPATH="/usr/local/lib/python${PYTHON_VERSION}/site-packages"

RUN addgroup flask && adduser -h /var/local/transform -D -G flask flask

COPY --from=build-stage-1 /usr/local/ /usr/local

RUN pip3 install --upgrade pip

RUN mkdir /usr/local/transform/
COPY setup.py requirements.txt requirements-production.txt /usr/local/transform/
COPY transform /usr/local/transform/transform

RUN cd /usr/local/transform && pip3 install --prefix=/usr/local -r requirements.txt -r requirements-production.txt
RUN cd /usr/local/transform && python setup.py install --prefix=/usr/local

COPY wsgi.py docker-command.sh /usr/local/bin/
RUN chmod a+x /usr/local/bin/wsgi.py /usr/local/bin/docker-command.sh

WORKDIR /var/local/transform
RUN mkdir ./logs && chown flask:flask ./logs
COPY --chown=flask logging.conf .

ENV FLASK_ENV="production" \
    FLASK_DEBUG="false" \
    LOGGING_ROOT_LEVEL="" \
    INSTANCE_PATH="/var/local/transform/data/" \
    OUTPUT_DIR="/var/local/transform/output/" \
    SECRET_KEY_FILE="/var/local/transform/secret_key" \
    TLS_CERTIFICATE="" \
    TLS_KEY=""

USER flask
CMD ["/usr/local/bin/docker-command.sh"]

EXPOSE 5000
EXPOSE 5443
