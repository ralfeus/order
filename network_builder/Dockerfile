FROM python:3.13-alpine
RUN apk add --no-cache geos geos-dev gcc musl-dev linux-headers curl bash
RUN pip install 'setuptools<72'
RUN pip install neomodel==4.0.7
RUN pip install requests tqdm-loggable bs4
COPY ./common /app/common
COPY ./network_builder /app
RUN chmod +x /app/entrypoint.sh

WORKDIR "/app"
VOLUME ["/app/output"]
# State server port
EXPOSE 1402
ENTRYPOINT ["/app/entrypoint.sh"]
