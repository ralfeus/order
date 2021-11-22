FROM python
RUN pip3 install flask neo4j-driver neobolt Shapely pytz six
COPY ./utils /
COPY ./network_builder /app

EXPOSE 5001

WORKDIR "/app"
ENTRYPOINT ["flask", "run", "--host", "0.0.0.0", "--port", "5001"]
