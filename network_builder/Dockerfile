FROM python
RUN pip3 install flask neomodel
COPY ./utils /
COPY ./network_builder /app

EXPOSE 5001

WORKDIR "/app"
ENTRYPOINT ["flask", "run", "--host", "0.0.0.0", "--port", "5001"]
