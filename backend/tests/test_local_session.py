from fastapi.testclient import TestClient
from pydantic import SecretStr
from app.main import create_app


def test_prefill_is_opt_in_and_local_only(settings):
    enabled = settings.model_copy(update={'local_token_prefill': True, 'execution_token': SecretStr('local-test')})
    with TestClient(create_app(enabled), base_url='http://localhost') as client:
        response = client.get('/api/local-operator-session')
        assert response.json() == {'token': 'local-test'}
        assert response.headers['cache-control'] == 'no-store'
        assert client.get('/api/local-operator-session', headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.get('/api/local-operator-session', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        assert client.get('/api/local-operator-session', headers={'Host': 'public.example'}).status_code == 403
    with TestClient(create_app(settings.model_copy(update={'local_token_prefill': False}))) as client:
        assert client.get('/api/local-operator-session').status_code == 404
    with TestClient(create_app(enabled.model_copy(update={'execution_enabled': False}))) as client:
        assert client.get('/api/local-operator-session').status_code == 404
