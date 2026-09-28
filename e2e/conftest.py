'''
Fixtures for browser (end-to-end) tests.

The application runs in a background thread on a random port against a
temporary SQLite file (an in-memory database isn't shared between the test
thread and the server thread). Tests drive it with Playwright's Chromium.

Prerequisite: `playwright install chromium`
'''
import os
import tempfile
import threading

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from werkzeug.serving import make_server

_db_file = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
os.environ['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{_db_file.name}'

from app import create_app, db  # noqa: E402 - must be imported after DB URI is set

PASSWORD_HASH = 'pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576'
PASSWORD = '1'


@pytest.fixture(scope='session')
def app():
    flask_app = create_app('../tests/config-test.json')
    with flask_app.app_context():
        yield flask_app
    os.unlink(_db_file.name)


@pytest.fixture(scope='session')
def base_url(app):
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()


@pytest.fixture(autouse=True)
def clean_db(app):
    db.drop_all()
    db.create_all()
    yield
    db.session.remove()


@pytest.fixture(scope='session')
def browser():
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch()
        yield chromium
        chromium.close()


@pytest.fixture
def context(browser: Browser, base_url):
    # Fixed locale keeps currency formatting deterministic ("$12.50")
    browser_context = browser.new_context(base_url=base_url, locale='en-US')
    yield browser_context
    browser_context.close()


@pytest.fixture
def page(context: BrowserContext) -> Page:
    return context.new_page()


def login(context: BrowserContext, username: str, password: str = PASSWORD):
    '''Logs in via HTTP; the session cookie is shared with the context's pages'''
    response = context.request.post('/login', form={
        'username': username, 'password': password
    })
    assert response.ok, response.text()
