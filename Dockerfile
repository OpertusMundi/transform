FROM dockershelf/python:3.8

LABEL language="python"
LABEL framework="flask"
LABEL usage="transform microservice for rasters and vectors"

RUN apt-get update
RUN apt-get install -y python3-gdal sqlite3
RUN pip3 install --upgrade pip
ADD . /usr/local/transform
RUN cd /usr/local/transform && python3 setup.py install
ENV FLASK_APP="transform" FLASK_ENV="production" FLASK_DEBUG="false"
ENV OUTPUT_DIR="/usr/local/transform/data/"
RUN cd /usr/local/transform && flask init-db

ADD wsgi.py /usr/local/bin/wsgi.py
RUN chmod +x /usr/local/bin/wsgi.py

EXPOSE 5000

ENV TLS_CERTIFICATE="" TLS_KEY=""

WORKDIR "/usr/local/"
CMD ["/usr/local/bin/wsgi.py"]
