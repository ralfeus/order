import logging

LOG_LEVEL = logging.INFO
SECRET_KEY = '150000$ZdGZazdW$5310a52465082ab169c8b62438fc09d2f69b2c5bf3945c0b99bdb1e082ae4f79'
ADMIN_HASH = '1500004ci4LtPz8641fd1956415e82846cddecb7a419e1fecc34b6e73b3dd6e22a1a943dce9a4a'
SQLALCHEMY_DATABASE_URI = 'mysql+mysqldb://talya:talya@localhost/star?unix_socket=/var/run/mysqld/mysqld.sock'
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = False
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,
    'pool_recycle': 280,
    'pool_size': 100
}

UPLOAD_PATH = '/upload'
PRODUCT_IMPORT_PERIOD = 300
FREE_LOCAL_SHIPPING_AMOUNT_THRESHOLD = 30000
LOCAL_SHIPPING_COST = 2500

PROFILER = True