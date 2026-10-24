from fastapi.testclient import TestClient
from app.main import create_app


def test_local_personas_enforce_api_permissions(settings):
    config = settings.model_copy(update={'local_token_prefill': True})
    with TestClient(create_app(config), base_url='http://localhost', client=('127.0.0.1', 50000)) as client:
        assert client.get('/api/workspace-role').json()['can_switch'] is True
        for role in ('finance', 'leadership'):
            response = client.post('/api/workspace-role', json={'role': role})
            assert response.status_code == 200
            assert 'HttpOnly' in response.headers['set-cookie']
            assert client.get('/api/workspace-role').json()['role'] == role
            assert client.get('/api/summary').status_code == 200
            assert client.get('/api/expenses').status_code == 200
            assert client.get('/api/execution/proposals').status_code == 403
            assert client.get('/api/local-operator-session').status_code == 403
            assert client.patch('/api/recommendations/any', json={}).status_code == 403
        assert client.post('/api/monitoring/evaluate', json={}).status_code == 403
        assert client.post('/api/workspace-role', json={'role': 'finance'}).status_code == 200
        assert client.post('/api/monitoring/evaluate', json={}).status_code == 200
        assert client.post('/api/workspace-role', json={'role': 'engineer'}).status_code == 200
        assert client.patch('/api/recommendations/any', json={}).status_code != 403


def test_configured_role_cannot_be_changed_or_forged(settings):
    config = settings.model_copy(update={'local_token_prefill': False, 'workspace_role': 'finance'})
    with TestClient(create_app(config)) as client:
        assert client.post('/api/workspace-role', json={'role': 'engineer'}).status_code == 403
        client.cookies.set('cloudpilot_role', 'engineer.forged')
        assert client.get('/api/workspace-role').json()['role'] == 'finance'
        assert client.get('/api/execution/proposals', headers={'Authorization': 'Bearer whatever'}).status_code == 403


def test_demo_switch_rejects_external_origins_and_invalid_roles(settings):
    config = settings.model_copy(update={'local_token_prefill': True})
    with TestClient(create_app(config), base_url='http://localhost', client=('127.0.0.1', 50000)) as client:
        assert client.post('/api/workspace-role', json={'role': 'engineer'}, headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.post('/api/workspace-role', json={'role': 'engineer'}, headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        assert client.post('/api/workspace-role', json={'role': 'admin'}).status_code == 422
