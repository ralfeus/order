FROM python:3.13-slim
WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium-headless-shell --with-deps

RUN mkdir /data

# JSON string of the PurchaseOrder
ENV PO_JSON=""
# URL to callback when done
ENV CALLBACK_URL=""
# Job ID to pass to the callback
ENV JOB_ID=""

CMD ["python", "main.py"]
