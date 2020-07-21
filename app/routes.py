'''
Contains all routes of the application
'''

from flask import send_from_directory

from app import app

@app.route('/')
def index():
    '''
    Entry point to the application.
    Takes no arguments
    '''
    return send_from_directory('static/html', 'index.html')
