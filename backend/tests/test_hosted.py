"""The hosted demo must not expose or initialize infrastructure execution."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app


def test_hosted_mode_removes_execution_even_with_operator_token(settings):
    hosted = settings.model_copy(update={'execution_enabled': False})
    with patch('app.main.ExecutionService') as execution:
        with TestClient(create_app(hosted)) as client:
            assert client.get('/api/health').status_code == 200
            assert client.get('/api/resources').json()['total'] == 200
            assert client.post('/api/monitoring/evaluate', json={}).status_code == 200
            assert client.get('/api/execution/resources', headers={'Authorization': 'Bearer anything'}).status_code == 404
            assert client.post('/api/execution/demo/setup').status_code == 404
            assert not any(path.startswith('/api/execution') for path in client.get('/openapi.json').json()['paths'])
            assert not hasattr(client.app.state, 'execution')
        execution.assert_not_called()
