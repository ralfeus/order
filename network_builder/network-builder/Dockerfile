FROM python:3.13-alpine
RUN apk add --no-cache geos geos-dev gcc musl-dev linux-headers curl bash
RUN pip install 'setuptools<72'
RUN pip install neomodel==4.0.7
RUN pip install requests tqdm-loggable
COPY ./utils /app/utils
COPY ./network_builder /app
COPY ./exceptions.py /app
RUN chmod +x /app/network-builder/entrypoint.sh

WORKDIR "/app"
VOLUME ["/app/output"]
ENTRYPOINT ["/app/network-builder/entrypoint.sh"]
