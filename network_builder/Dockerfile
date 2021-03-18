FROM python
RUN pip3 install celery cssselect email_validator flask flask-bootstrap 
RUN pip3 install flask-migrate flask-security lxml more-itertools mysqlclient 
RUN pip3 install selenium SQLAlchemy
COPY ./app app
COPY ./network_builder /

ENTRYPOINT ["python3", "build_network.py"]
CMD ["--incremental"]
