"""Unit tests for network_manager endpoints."""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import docker
import docker.errors

# ---------------------------------------------------------------------------
# Stub out heavy / connection-requiring dependencies before importing the app
# ---------------------------------------------------------------------------

def _stub_module(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod

_stub_module('neomodel', db=MagicMock(), config=MagicMock())
_stub_module('common.model', AtomyPerson=MagicMock())

# netman_app must expose a real Flask app so that @app.route decorators work
from flask import Flask
_flask_app = Flask(__name__)
_flask_app.config['TESTING'] = True
_stub_module('netman_app', app=_flask_app)

import network_manager.network_manager  # noqa: E402 – registers routes on _flask_app


class TestStartBuilderDockerUnavailable(unittest.TestCase):

    def setUp(self):
        self.client = _flask_app.test_client()

    def _make_docker_unavailable_exc(self):
        cause = FileNotFoundError(2, 'No such file or directory')
        exc = docker.errors.DockerException(
            f'Error while fetching server API version: {cause}'
        )
        exc.__cause__ = cause
        return exc

    # ------------------------------------------------------------------
    # Reproduces the reported bug: Docker socket missing → must get 503
    # ------------------------------------------------------------------
    @patch('network_manager.network_manager._test_db_connection', return_value=True)
    @patch('network_manager.network_manager._get_builder_container', return_value=None)
    @patch('network_manager.network_manager.sleep')
    @patch('network_manager.network_manager.docker.from_env')
    def test_503_when_docker_socket_missing(
            self, mock_from_env, _sleep, _get_container, _db):
        mock_from_env.side_effect = self._make_docker_unavailable_exc()

        response = self.client.get('/api/v1/builder/start')

        self.assertEqual(response.status_code, 503)
        data = response.get_json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('Docker', data['description'])

    # ------------------------------------------------------------------
    # Happy path: Docker available → builder starts
    # ------------------------------------------------------------------
    @patch('network_manager.network_manager._test_db_connection', return_value=True)
    @patch('network_manager.network_manager._get_builder_container', return_value=None)
    @patch('network_manager.network_manager.sleep')
    @patch('network_manager.network_manager.docker.from_env')
    def test_started_when_docker_available(
            self, mock_from_env, _sleep, _get_container, _db):
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        mock_client.containers.get.side_effect = docker.errors.NotFound('not found')

        response = self.client.get('/api/v1/builder/start')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'started')

    # ------------------------------------------------------------------
    # Container must be started with auto_remove=True so it is removed
    # after execution without manual cleanup
    # ------------------------------------------------------------------
    @patch('network_manager.network_manager._test_db_connection', return_value=True)
    @patch('network_manager.network_manager._get_builder_container', return_value=None)
    @patch('network_manager.network_manager.sleep')
    @patch('network_manager.network_manager.docker.from_env')
    def test_container_auto_removed_after_execution(
            self, mock_from_env, _sleep, _get_container, _db):
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        mock_client.containers.get.side_effect = docker.errors.NotFound('not found')

        self.client.get('/api/v1/builder/start')

        _, kwargs = mock_client.containers.run.call_args
        self.assertTrue(
            kwargs.get('auto_remove'),
            "Container must be started with auto_remove=True so it is cleaned up after execution",
        )

    # ------------------------------------------------------------------
    # Already running: must short-circuit before touching Docker
    # ------------------------------------------------------------------
    @patch('network_manager.network_manager._test_db_connection', return_value=True)
    @patch('network_manager.network_manager._get_builder_container')
    @patch('network_manager.network_manager.sleep')
    def test_already_running(self, _sleep, mock_get_container, _db):
        mock_get_container.return_value = MagicMock()  # container is running

        response = self.client.get('/api/v1/builder/start')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'already running')


if __name__ == '__main__':
    unittest.main()
