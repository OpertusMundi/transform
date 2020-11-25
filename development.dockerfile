# vim: set syntax=dockerfile:

FROM dockershelf/python:3.8

LABEL language="python"
LABEL framework="flask"
LABEL usage="transform microservice for rasters and vectors"

RUN apt-get update
RUN apt-get install -y python3-gdal sqlite3

RUN mkdir /usr/local/transform/
COPY setup.py requirements.txt /usr/local/transform/
COPY transform /usr/local/transform/transform

WORKDIR /usr/local/transform
RUN pip install -r requirements.txt
RUN python setup.py install

ADD wsgi.py docker-command.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/wsgi.py /usr/local/bin/docker-command.sh

EXPOSE 5000

ENV FLASK_ENV="production" FLASK_DEBUG="false"
ENV OUTPUT_DIR="/usr/local/transform/output/"
ENV TLS_CERTIFICATE="" TLS_KEY=""

CMD ["/usr/local/bin/docker-command.sh"]
