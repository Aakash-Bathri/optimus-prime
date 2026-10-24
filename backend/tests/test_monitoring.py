import json
from unittest.mock import patch

import httpx
import pytest

from app.engine.monitoring import Scenario, project
from app.engine.service import CloudPilot, Filters


def test_forecast_and_schedule_reconcile(client):
    data = client.post('/api/monitoring/evaluate', json={'days': 90}).json()
    assert len(data['points']) == 90
    assert data['baseline_total'] == round(sum(p['baseline'] for p in data['points']), 2)
    assert data['scenario_total'] == round(sum(p['scenario'] for p in data['points']), 2)
    assert data['conditional_savings'] > 0
    assert all(0 <= p['scenario'] <= p['baseline'] <= p['upper'] for p in data['points'])
    assert all(0 <= p['lower'] <= p['baseline'] for p in data['points'])
    assert data['usage']['avoided_vcpu_hours'] == sum(r['vcpu'] for r in data['selected_resources']) * 12 * 90
    assert data['sustainability']['avoided_kwh'] <= data['sustainability']['baseline_kwh']
    assert data['as_of'] < data['points'][0]['date']


def test_disabled_and_empty_weekdays(client):
    for body in [{'shutdown': False}, {'weekdays': []}]:
        data = client.post('/api/monitoring/evaluate', json=body).json()
        assert data['conditional_savings'] == 0
        assert data['usage']['avoided_vcpu_hours'] == 0
        assert data['sustainability']['avoided_kwh'] == 0


@pytest.mark.parametrize('body', [{'days': 29}, {'days': 91}, {'timezone': 'Bad/Zone'}, {'weekdays': [7]}, {'weekdays': [1, 1]}, {'stop_hour': 8, 'start_hour': 8}, {'budget': -1}, {'pue': 0.5}, {'demand_growth_pct': 101}])
def test_validation(client, body):
    assert client.post('/api/monitoring/evaluate', json=body).status_code == 422


def test_scoping_empty_and_budget_alert(client):
    empty = client.post('/api/monitoring/evaluate?team=missing-team', json={}).json()
    assert empty['resource_count'] == 0
    assert empty['baseline_total'] == 0
    assert empty['alerts'] == []
    assert empty['selected_resources'] == []
    data = client.post('/api/monitoring/evaluate?environment=production', json={'budget': 1}).json()
    assert data['selected_resources'] == []
    assert any(a['category'] == 'budget_overrun' and a['severity'] == 'critical' for a in data['alerts'])
    relaxed = client.post('/api/monitoring/evaluate', json={'cost_increase_pct': 1000, 'capacity_pct': 100}).json()
    assert not any(a['category'] == 'cost_increase' for a in relaxed['alerts'])


def test_carbon_factors_and_demand(client):
    baseline = client.post('/api/monitoring/evaluate', json={}).json()
    growth = client.post('/api/monitoring/evaluate', json={'demand_growth_pct': 50, 'carbon_kg_per_kwh': 0}).json()
    assert growth['baseline_total'] > baseline['baseline_total']
    assert growth['sustainability']['avoided_kg_co2e'] == 0
    assert growth['usage']['estimated_busy_vcpu_hours'] > baseline['usage']['estimated_busy_vcpu_hours']


def test_exports_include_scoped_findings(client):
    for format, extension in [('markdown', 'md'), ('json', 'json'), ('terraform', 'tf')]:
        response = client.post(f'/api/monitoring/export?format={format}&team=missing-team', json={})
        assert response.status_code == 200
        assert response.headers['content-disposition'].endswith(f'.{extension}"')
        if format == 'json':
            assert response.json()['recommendations'] == []
        elif format == 'terraform':
            assert 'Creates no resources' in response.text
            encoded = response.text.split('jsondecode(', 1)[1].split(')\n}', 1)[0]
            assert json.loads(json.loads(encoded))['resource_ids'] == []
        else:
            assert '## Assumptions' in response.text
    assert client.post('/api/monitoring/export?format=sh', json={}).status_code == 422


def test_qwen_success_and_safe_fallback(client):
    config = {'QWEN_API_KEY': 'test-secret', 'QWEN_BASE_URL': 'https://example.test/v1', 'QWEN_MODEL': 'qwen-test'}
    with patch('app.api.monitoring.dotenv_values', return_value=config), patch.dict('os.environ', config):
        response = httpx.Response(200, json={'choices': [{'message': {'content': 'Review the historical evidence before scheduling.'}}]}, request=httpx.Request('POST', 'https://example.test'))
        with patch('httpx.AsyncClient.post', return_value=response) as call:
            result = client.post('/api/monitoring/explain', json={'scenario': {}}).json()
            assert result['source'] == 'qwen'
            assert call.call_args.kwargs['json']['model'] == 'qwen-test'
        with patch('httpx.AsyncClient.post', side_effect=httpx.ConnectError('test-secret')):
            result = client.post('/api/monitoring/explain', json={'scenario': {}}).json()
            assert result['source'] == 'rules'
            assert 'test-secret' not in json.dumps(result)


def test_explanation_cannot_escape_scope(client):
    finding = client.get('/api/recommendations?limit=1').json()['items'][0]
    response = client.post('/api/monitoring/explain?team=missing-team', json={'scenario': {}, 'recommendation_id': finding['id']})
    assert response.status_code == 404


def test_overnight_weekday_anchor(settings):
    app = CloudPilot(settings.resolved_database_path)
    # A daily 12-hour window always avoids half the capacity, including local midnight crossings.
    utc = project(app, Filters(), Scenario(timezone='UTC'))
    india = project(app, Filters(), Scenario(timezone='Asia/Kolkata'))
    assert utc['usage']['avoided_vcpu_hours'] == india['usage']['avoided_vcpu_hours']
    weekdays = project(app, Filters(), Scenario(timezone='UTC', weekdays=[0, 1, 2, 3, 4]))
    assert 0 < weekdays['usage']['avoided_vcpu_hours'] < utc['usage']['avoided_vcpu_hours']


def test_month_length_is_not_treated_as_cost_growth(settings):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from app.database import connect

    app = CloudPilot(settings.resolved_database_path)
    resource_id = app.resources()[0].id
    with connect(app.database_path) as connection:
        connection.execute('DELETE FROM billing')
        for month, amount in [('2026-03', '310'), ('2026-04', '300'), ('2026-05', '310')]:
            connection.execute('INSERT INTO billing(month, resource_id, amount) VALUES (?, ?, ?)', (month, resource_id, amount))
    result = project(app, Filters(search=resource_id), Scenario(shutdown=False))
    assert result['baseline_total'] == 300
    assert all(p['baseline'] == 10 for p in result['points'])
    assert not any(a['category'] == 'cost_increase' for a in result['alerts'])
    assert result['points'][0]['date'] > str(datetime.now(ZoneInfo('Asia/Kolkata')).date())
