from decimal import Decimal


def test_expense_buckets_reconcile_to_billing_and_contributors(client):
    history = client.get('/api/summary').json()['billing_history']
    expected = next(row['amount'] for row in history if row['month'] == '2026-09')
    for granularity, count in [('day', 30), ('week', 5), ('month', 1)]:
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
    params = {'start': '2026-08-29', 'end': '2026-09-06', 'granularity': 'week', 'breakdown': 'region', 'environment': 'development', 'team': 'team-01'}
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
    first = client.get('/api/expenses?start=2026-09-01&end=2026-09-13').json()
    second = client.get('/api/expenses?start=2026-09-14&end=2026-09-30').json()
    whole = client.get('/api/expenses').json()
    assert Decimal(first['total']) + Decimal(second['total']) == Decimal(whole['total'])


def test_sources_classification_and_unknown_costs(client):
    body = client.get('/api/data-sources').json()
    assert body['organization']['name'] == 'CloudPilot demo'
    source = body['items'][0]
    assert source['resource_count'] == 200
    assert sum(row['count'] for row in source['classifications']) == 200
    assert source['billing_start'] == '2026-04-01'
    assert source['billing_end'] == '2026-09-30'
    assert {row['file'] for row in source['feeds']} >= {'resources.csv', 'metrics.csv', 'billing_history.csv'}
    assert client.get('/api/resources?data_source=utho-benchmark').json()['total'] == 200
    assert client.get('/api/resources?data_source=missing').json()['total'] == 0
    unpriced = client.get('/api/expenses?resource_type=gpu').json()
    assert unpriced['total'] == '0.00'
    assert unpriced['unknown_price_count'] == 10
    assert all(row['amount'] is None for row in unpriced['resources'])


def test_expense_range_validation_and_empty_scope(client):
    for query in ['start=2026-09-30&end=2026-09-01', 'start=2026-03-01', 'end=2026-10-01', 'granularity=hour', 'breakdown=missing', 'start=garbage']:
        assert client.get('/api/expenses?' + query).status_code == 422
    body = client.get('/api/expenses?region=missing').json()
    assert body['total'] == '0.00'
    assert body['resource_count'] == 0
    assert body['groups'] == []
