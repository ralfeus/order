FROM tiangolo/meinheld-gunicorn-flask
RUN useradd order
COPY --chown=order:order ./app /app
COPY --chown=order:order ./migrations /app/migrations

# Install MySQL client
# RUN apt-get update
# RUN apt-get install lsb-release -y
# RUN wget https://dev.mysql.com/get/mysql-apt-config_0.8.15-1_all.deb
# ENV DEBIAN_FRONTEND="noninteractive"
# RUN echo mysql-apt-config mysql-apt-config/select-server select mysql-8.0 | debconf-set-selections
# RUN dpkg -i mysql-apt-config_0.8.15-1_all.deb
RUN apt-get update
# RUN apt-get install mysql-community-client -y
RUN apt-get install mariadb-client -y
#RUN rm /var/cache/apt/archives/partial/*
#RUN rm /var/cache/apt/archives/*
#RUN rm /var/cache/apt/pkgcache.bin
#RUN rm /var/cache/apt/srcpkgcache.bin

# Browser support 
RUN apt-get install chromium -y
COPY ./chromedriver /usr/bin/chromedriver

# Install Python packages
COPY ./requirements.txt /requirements.txt
RUN pip3 install --upgrade pip --no-cache-dir
RUN pip3 install -r /requirements.txt --no-cache-dir

# Celery setup
#RUN useradd celery

# Finalize
USER order
# Set proper Flask port
ENV PORT 5000 