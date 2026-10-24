import csv
import io
from decimal import Decimal

from fastapi.testclient import TestClient

from app.config import ROOT
from app.main import create_app


def test_delivered_inventory_and_price_integrity(client):
    dataset = client.get('/api/dataset').json()
    assert dataset['resource_count'] == 200
    assert dataset['metric_rows'] == 432000
    assert dataset['gpu_metric_rows'] == 28800
    assert dataset['missing_observation_rows'] == 2880
    assert dataset['duplicate_event_rows'] == 10
    assert dataset['invalid_observation_rows'] == 0
    assert client.get('/api/health').json()['status'] == 'ok'
    page = client.get('/api/resources?limit=200').json()
    assert page['total'] == 200
    assert sum(item['monthly_cost'] is None for item in page['items']) == 30
    assert len(client.get('/api/plans').json()) == 49
    with (ROOT / 'test-data/pricing.csv').open() as stream:
        expected = sum((Decimal(row['monthly_equivalent_inr']) for row in csv.DictReader(stream) if row['monthly_equivalent_inr']), Decimal(0))
    summary = client.get('/api/summary').json()
    assert Decimal(summary['known_monthly_cost']) == expected
    assert summary['unknown_price_count'] == 30
    assert summary['ready_count'] == 0
    assert summary['insufficient_data_count'] == 5
    assert summary['plan']['verified_savings'] is None
    assert all(plan['region_verified'] is False for plan in client.get('/api/plans').json())


def test_combined_filters_reconcile_all_views(client):
    query = 'environment=development&region=Mumbai&team=team-10'
    resources = client.get('/api/resources?' + query).json()
    summary = client.get('/api/summary?' + query).json()
    recommendations = client.get('/api/recommendations?' + query).json()
    ids = {item['id'] for item in resources['items']}
    assert summary['resource_count'] == resources['total'] > 0
    assert all(item['resource_id'] in ids for item in recommendations['items'])
    assert Decimal(summary['known_monthly_cost']) == sum((Decimal(item['monthly_cost']) for item in resources['items'] if item['monthly_cost'] is not None), Decimal(0))
    empty = client.get('/api/summary?region=missing-region').json()
    assert empty['resource_count'] == 0
    assert empty['known_monthly_cost'] == '0.00'
    assert empty['conditional_monthly_savings'] == '0.00'
    assert empty['alert_count'] == 0
    assert len(client.get('/api/metrics?region=missing-region').json()['points']) == 30


def test_review_decision_is_persistent_versioned_and_not_a_saving(client, settings):
    before = client.get('/api/optimization-plan').json()
    finding = next(item for item in client.get('/api/recommendations?limit=200').json()['items'] if item['action'] == 'resize' and item['conditional_monthly_savings'] is not None)
    body = {'decision': 'accepted', 'version': finding['version'], 'expected_revision': 0}
    response = client.patch('/api/recommendations/' + finding['id'], json=body)
    assert response.status_code == 200
    assert response.json()['decision_revision'] == 1
    assert response.json()['review_only'] is True
    plan = client.get('/api/optimization-plan').json()
    assert plan['items'][0]['id'] == finding['id']
    assert plan['current_monthly_cost'] == plan['projected_monthly_cost'] == before['current_monthly_cost']
    assert plan['accepted_monthly_savings'] == '0.00'
    assert plan['review_only_count'] == 1
    assert plan['effective_action_count'] == 0
    assert sum(Decimal(row['projected_cost']) for row in plan['by_environment']) == Decimal(plan['projected_monthly_cost'])
    assert client.patch('/api/recommendations/' + finding['id'], json=body).status_code == 409
    with TestClient(create_app(settings)) as restarted:
        persisted = restarted.get('/api/recommendations/' + finding['id']).json()
        assert persisted['decision'] == 'accepted'
        assert persisted['decision_revision'] == 1
        export = restarted.get('/api/optimization-plan/export').json()
        assert export['evidence'][0]['id'] == finding['id']
        assert export['dataset']['assumptions']
        csv_response = restarted.get('/api/optimization-plan/export?format=csv')
        rows = list(csv.DictReader(io.StringIO(csv_response.text)))
        assert rows[0]['review_only'] == 'True'
        assert rows[0]['modeled_monthly_savings'] == ''
        assert rows[0]['blockers'] and rows[0]['prerequisites'] and rows[0]['assumptions']
        assert rows[0]['dataset_version'] == finding['version']
        assert restarted.get('/api/audit').json()[0]['decision'] == 'accepted'
        reset = restarted.patch('/api/recommendations/' + finding['id'], json={**body, 'decision': 'pending', 'expected_revision': 1})
        assert reset.status_code == 200
        assert reset.json()['decision_revision'] == 2
        assert restarted.get('/api/optimization-plan').json()['items'] == []


def test_missing_data_abstains_and_cannot_enter_plan(client):
    outcomes = client.get('/api/recommendations?outcome=insufficient_data').json()
    assert outcomes['total'] == 5
    finding = outcomes['items'][0]
    detail = client.get('/api/recommendations/' + finding['id']).json()
    assert not detail['analysis']['quality']['sufficient']
    assert detail['analysis']['quality']['coverage'] == 0.8
    assert detail['candidates'] == []
    assert detail['conditional_monthly_savings'] is None
    assert client.patch('/api/recommendations/' + finding['id'], json={'decision':'accepted', 'version': finding['version'], 'expected_revision': 0}).status_code == 409


def test_peak_charts_and_statistical_alerts(client):
    series = client.get('/api/resources/vm-002/metrics?resolution=hour').json()['points']
    assert len(series) == 720
    assert max(point['iops_peak'] for point in series) > 500
    assert all(point['iops_peak'] >= point['iops'] for point in series if point['iops'] is not None)
    detail = client.get('/api/resources/gpu-001').json()
    assert detail['gpu_statistics']['samples'] == 2880
    assert detail['monthly_cost'] is None
    assert len(detail['events']) == 1  # Identical source duplicates are reported/deduplicated.
    alerts = client.get('/api/alerts?limit=200').json()['items']
    assert {'usage_anomaly', 'capacity_pressure', 'data_quality', 'cost_increase'} <= {item['category'] for item in alerts}
    assert any(item['resource_id'] == 'vm-001' and item['category'] == 'usage_anomaly' for item in alerts)
    # A normal control must not become an incident merely because it has noise.
    assert not any(item['resource_id'] == 'vm-004' and item['category'] == 'usage_anomaly' for item in alerts)


def test_simulation_uses_authoritative_catalog_and_never_changes_plan(client):
    finding = next(item for item in client.get('/api/recommendations?limit=200').json()['items'] if item['action'] == 'resize')
    request = {'resource_id': finding['resource_id'], 'target_plan_id': finding['target_plan_id'], 'demand_multiplier': 3}
    before = client.get('/api/optimization-plan').json()
    response = client.post('/api/simulate', json=request)
    assert response.status_code == 200
    candidate = response.json()['candidate']
    assert candidate['eligible'] is False
    assert response.json()['verified_savings'] is None
    assert client.get('/api/optimization-plan').json() == before
    assert client.post('/api/simulate', json={**request, 'monthly_cost': '0.01'}).status_code == 422
    assert client.post('/api/simulate', json={**request, 'target_plan_id': 'invented-plan'}).status_code == 404
    assert client.post('/api/simulate', json={**request, 'demand_multiplier': 'NaN'}).status_code == 422
    # JSON overflow may decode to infinity; error serialization must remain valid.
    assert client.post('/api/simulate', content='{"resource_id":"vm-001","target_plan_id":"amd-basic-1","demand_multiplier":1e309}', headers={'Content-Type':'application/json'}).status_code == 422


def test_errors_pagination_and_cache_reuse(client, settings):
    imported_at = client.get('/api/dataset').json()['imported_at']
    assert client.get('/api/resources?offset=200').json()['items'] == []
    for path, status, code in [('/api/resources/missing', 404, 'http_404'), ('/api/resources?limit=0', 422, 'validation_error'), ('/api/resources?offset=-1', 422, 'validation_error')]:
        response = client.get(path)
        assert response.status_code == status
        body = response.json()
        assert body['code'] == code
        assert body['request_id'] == response.headers['X-Request-ID']
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get('/api/dataset').json()['imported_at'] == imported_at


def test_csv_export_escapes_all_text_fields_but_keeps_negative_costs(client, settings):
    import json
    from app.database import connect
    finding = next(f for f in client.get('/api/recommendations?limit=200').json()['items'] if f['action'] == 'capacity_review' and f['conditional_monthly_savings'] is not None and Decimal(f['conditional_monthly_savings']) < 0)
    with connect(settings.resolved_database_path) as db:
        row = db.execute('SELECT summary, payload FROM recommendations WHERE id=?', (finding['id'],)).fetchone()
        summary, payload = json.loads(row['summary']), json.loads(row['payload'])
        for record in [summary, payload]:
            record['resource_name'] = ' \t=HYPERLINK("https://example.test")'
            record['current_plan_id'] = '+untrusted-plan'
            record['blockers'] = ['@untrusted']
        db.execute('UPDATE recommendations SET summary=?,payload=? WHERE id=?', (json.dumps(summary), json.dumps(payload), finding['id']))
    response = client.patch('/api/recommendations/' + finding['id'], json={'decision': 'accepted', 'version': finding['version'], 'expected_revision': finding['decision_revision']})
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(client.get('/api/optimization-plan/export?format=csv').text)))
    row = next(r for r in rows if r['resource_id'] == finding['resource_id'])
    assert row['resource_name'].startswith("' \t=")
    assert row['current_plan_id'] == "'+untrusted-plan"
    assert row['blockers'] == "'@untrusted"
    assert Decimal(row['conditional_monthly_savings']) < 0
