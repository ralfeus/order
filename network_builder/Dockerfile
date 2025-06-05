FROM python:3.13-alpine
# RUN apt update
RUN apk add --no-cache geos geos-dev gcc musl-dev linux-headers curl
RUN pip install setuptools
RUN pip install werkzeug==2.0.3
RUN pip install flask==2.1.2
RUN pip install neomodel==4.0.7
RUN pip install psutil requests tqdm-loggable
COPY ./utils /app/utils
COPY ./network_builder /app
COPY ./exceptions.py /app

EXPOSE 5001

WORKDIR "/app"
ENV FLASK_APP=netman_app
ENTRYPOINT ["flask", "run", "--host", "0.0.0.0", "--port", "5001"]
