FROM python
COPY ./app /app
COPY ./migrations /app/migrations

# Install MySQL client
RUN apt-get update
RUN apt-get install mariadb-client -y

# Install Python packages
COPY ./requirements.txt /requirements.txt
RUN pip3 install --upgrade pip --no-cache-dir
RUN pip3 install -r /requirements.txt --no-cache-dir

# Set proper Flask port
ENV PORT 5000 