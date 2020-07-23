import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    SECRET_KEY = '150000$ZdGZazdW$5310a52465082ab169c8b62438fc09d2f69b2c5bf3945c0b99bdb1e082ae4f79'
    ADMIN_HASH = '1500004ci4LtPz8641fd1956415e82846cddecb7a419e1fecc34b6e73b3dd6e22a1a943dce9a4a'
    SQLALCHEMY_DATABASE_URI = 'mysql+mysqldb://talya:talya@sandlet/talya'
    SQLALCHEMY_TRACK_MODIFICATIONS = False