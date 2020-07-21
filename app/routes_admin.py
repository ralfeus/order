'''
Contains admin routes of the application
'''
from flask import Response, send_from_directory
from flask_login import current_user, login_required, login_user

from app import app
from app.models import User

@app.route('/admin/<key>')
def admin(key):
    '''
    Shows list of ordered products
    '''
    if key == app.config['ADMIN_HASH']:
        login_user(User(0), remember=True)
    if current_user.is_anonymous:
        return Response('Anonymous access is denied', mimetype='text/html')

    return send_from_directory('static/html', 'admin.html')

@app.route('/admin/products')
@login_required
def products():
    '''
    Product catalog management
    '''
    return send_from_directory('static/html', 'products.html')
