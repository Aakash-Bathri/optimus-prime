from decimal import Decimal
import calendar
import csv
from datetime import date, timedelta
from app.config import ROOT


def billing_bounds():
    with (ROOT / "test-data/billing_history.csv").open() as stream:
        months = sorted({row["billing_month"] for row in csv.DictReader(stream)})
    first = date.fromisoformat(months[0] + "-01")
    start = date.fromisoformat(months[-1] + "-01")
    end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    return first, start, end



def test_expense_buckets_reconcile_to_billing_and_contributors(client):
    history = client.get('/api/summary').json()['billing_history']
    _, start, end = billing_bounds()
    expected = next(row['amount'] for row in history if row['month'] == start.strftime('%Y-%m'))
    for granularity, count in [('day', end.day), ('week', len({(start + timedelta(days=i)).isocalendar()[:2] for i in range(end.day)})), ('month', 1)]:
        response = client.get('/api/expenses', params={'granularity': granularity, 'breakdown': 'resource_type'})
        assert response.status_code == 200
        body = response.json()
        assert body['total'] == expected
        assert len(body['points']) == count
        assert sum(Decimal(point['amount']) for point in body['points']) == Decimal(expected)
        assert sum(Decimal(group['amount']) for group in body['groups']) == Decimal(expected)
        assert sum(Decimal(row['amount']) for row in body['resources'] if row['amount'] is not None) == Decimal(expected)
        assert body['unknown_price_count'] == 30
        assert all(sum(Decimal(value) for value in point['groups'].values()) == Decimal(point['amount']) for point in body['points'])


def test_partial_period_drilldown_reconciles_and_keeps_filters(client):
    _, start, end = billing_bounds()
    params = {'start': (start - timedelta(days=3)).isoformat(), 'end': start.replace(day=6).isoformat(), 'granularity': 'week', 'breakdown': 'region', 'environment': 'development', 'team': 'team-01'}
    body = client.get('/api/expenses', params=params).json()
    assert body['points'][0]['start'] == params['start']
    assert body['points'][-1]['end'] == params['end']
    assert sum(Decimal(point['amount']) for point in body['points']) == Decimal(body['total'])
    for group in body['groups']:
        drill = client.get('/api/expenses', params={**params, 'region': group['id']}).json()
        assert drill['total'] == group['amount']
        inventory = client.get('/api/resources', params={'environment': 'development', 'team': 'team-01', 'region': group['id'], 'limit': 200}).json()
        assert {row['resource_id'] for row in drill['resources']} == {row['id'] for row in inventory['items']}
    # Cent allocation must also reconcile across adjacent partial date ranges.
    first = client.get('/api/expenses', params={'start': start.isoformat(), 'end': start.replace(day=13).isoformat()}).json()
    second = client.get('/api/expenses', params={'start': start.replace(day=14).isoformat(), 'end': end.isoformat()}).json()
    whole = client.get('/api/expenses').json()
    assert Decimal(first['total']) + Decimal(second['total']) == Decimal(whole['total'])


def test_sources_classification_and_unknown_costs(client):
    body = client.get('/api/data-sources').json()
    assert body['organization']['name'] == 'CloudPilot demo'
    source = body['items'][0]
    assert source['resource_count'] == 200
    assert sum(row['count'] for row in source['classifications']) == 200
    first, _, end = billing_bounds()
    assert source['billing_start'] == first.isoformat()
    assert source['billing_end'] == end.isoformat()
    assert {row['file'] for row in source['feeds']} >= {'resources.csv', 'metrics.csv', 'billing_history.csv'}
    assert client.get('/api/resources?data_source=utho-benchmark').json()['total'] == 200
    assert client.get('/api/resources?data_source=missing').json()['total'] == 0
    unpriced = client.get('/api/expenses?resource_type=gpu').json()
    assert unpriced['total'] == '0.00'
    assert unpriced['unknown_price_count'] == 10
    assert all(row['amount'] is None for row in unpriced['resources'])


def test_expense_range_validation_and_empty_scope(client):
    first, start, end = billing_bounds()
    for query in [f'start={end}&end={start}', f'start={first - timedelta(days=1)}', f'end={end + timedelta(days=1)}', 'granularity=hour', 'breakdown=missing', 'start=garbage']:
        assert client.get('/api/expenses?' + query).status_code == 422
    body = client.get('/api/expenses?region=missing').json()
    assert body['total'] == '0.00'
    assert body['resource_count'] == 0
    assert body['groups'] == []


def test_unassigned_team_bucket_can_be_drilled(client, settings):
    import json
    from app.database import connect
    with connect(settings.resolved_database_path) as db:
        row = db.execute('SELECT id, payload FROM resources LIMIT 1').fetchone()
        resource = json.loads(row['payload'])
        resource['team'] = None
        db.execute('UPDATE resources SET payload=? WHERE id=?', (json.dumps(resource), row['id']))
    grouped = client.get('/api/expenses?breakdown=team').json()
    bucket = next(g for g in grouped['groups'] if g['id'] == 'Unassigned')
    drill = client.get('/api/expenses?breakdown=team&team=Unassigned').json()
    assert drill['total'] == bucket['amount']
    assert drill['resource_count'] == bucket['resource_count']
    inventory = client.get('/api/resources?team=Unassigned').json()
    assert {r['resource_id'] for r in drill['resources']} == {r['id'] for r in inventory['items']}
