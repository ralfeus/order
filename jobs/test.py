from datetime import datetime
import logging
from time import sleep

logging.basicConfig(level=logging.DEBUG)

for i in range(10):
    print(datetime.now())
    sleep(1)
