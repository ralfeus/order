FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    pkg-config \
    default-libmysqlclient-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*
COPY ./requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir 'setuptools<72' gunicorn -r /tmp/requirements.txt
COPY ./common /app/common
COPY ./app /app/app
COPY ./migrations /app/migrations
RUN chmod +x /app/app/entrypoint.sh

EXPOSE 5000

WORKDIR /app
ENTRYPOINT ["/app/app/entrypoint.sh"]
