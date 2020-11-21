# vim: set syntax=dockerfile:

FROM osgeo/gdal:alpine-normal-3.1.0 as build-stage-1

RUN apk update && apk add gcc musl-dev python3-dev
RUN pip3 install --upgrade pip
RUN pip3 install --user "pyproj>=2.6.0,<2.7.0"


FROM osgeo/gdal:alpine-normal-3.1.0

LABEL language="python"
LABEL framework="flask"
LABEL usage="transform microservice for rasters and vectors"

RUN apk update && apk add --no-cache sqlite py3-yaml py3-gunicorn

COPY --from=build-stage-1 /root/.local /root/.local

RUN mkdir /usr/local/transform/
COPY setup.py requirements.txt /usr/local/transform/
COPY transform /usr/local/transform/transform

WORKDIR /usr/local/transform

RUN pip3 install --upgrade pip && pip3 install --user --no-warn-script-location -r requirements.txt
RUN python setup.py install --user

COPY wsgi.py docker-command.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/wsgi.py /usr/local/bin/docker-command.sh

EXPOSE 5000
EXPOSE 5443

ENV FLASK_APP="transform" FLASK_ENV="production" FLASK_DEBUG="false"
ENV OUTPUT_DIR="/var/local/transform/output/"
ENV TLS_CERTIFICATE="" TLS_KEY=""

CMD ["/usr/local/bin/docker-command.sh"]
