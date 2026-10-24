"""Malformed input must fail before it becomes recommendation evidence."""
import csv
import json
from pathlib import Path

import pytest

from app.adapters.dataset import DatasetSource, SOURCE_FILES, records, amount
from app.config import ROOT


@pytest.fixture
def source_folder(tmp_path):
    folder = tmp_path / 'source'
    folder.mkdir()
    for name in SOURCE_FILES:
        (folder / name).symlink_to(ROOT / 'test-data' / name)
    return folder


def replace_csv(folder, name, mutate):
    path = folder / name
    with path.open() as stream:
        reader = csv.DictReader(stream)
        headers, rows = reader.fieldnames, list(reader)
    mutate(rows)
    path.unlink()
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize('header', ['id,id\na,b\n', ',id\na,b\n', ' \na\n'])
def test_csv_rejects_duplicate_and_blank_column_names(tmp_path, header):
    path = tmp_path / 'input.csv'
    path.write_text(header)
    with pytest.raises(ValueError, match='column name'):
        list(records(path, set()))


@pytest.mark.parametrize('section,key,value', [
    ('metrics', 'interval_minutes', 15.5),
    ('metrics', 'interval_minutes', True),
    ('metrics', 'interval_minutes', 0),
    ('metrics', 'interval_minutes', 60),
    ('metrics', 'metric_rows', 1),
    ('metrics', 'gpu_metric_rows', 1),
    ('metrics', 'vm_count', 149),
    ('metrics', 'points_per_vm', 200),
    ('metrics', 'duration_days', 29),
    ('resource_counts', 'total', 201),
    ('resource_counts', 'vm', -1),
])
def test_manifest_grid_and_counts_are_consistent(source_folder, section, key, value):
    path = source_folder / 'assumptions.json'
    manifest = json.loads(path.read_text())
    manifest[section][key] = value
    path.unlink()
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='assumptions.json'):
        DatasetSource(source_folder)


@pytest.mark.parametrize('field,value', [
    ('resource_id', '  '), ('resource_id', ' vm-001'),
    ('transfer_allowance_gb', '0'), ('attached_to', 'vm-001'),
])
def test_inventory_identity_capacity_and_host_checks(source_folder, field, value):
    replace_csv(source_folder, 'resources.csv', lambda rows: rows[0].update({field: value}))
    source = DatasetSource(source_folder)
    with pytest.raises(ValueError):
        source.load_resources(source.load_catalog())


@pytest.mark.parametrize('case', ['duplicate', 'missing', 'wrong_type', 'wrong_host'])
def test_relationships_match_inventory_exactly(source_folder, case):
    def mutate(rows):
        if case == 'duplicate': rows.append(dict(rows[0]))
        elif case == 'missing': rows.pop(0)
        elif case == 'wrong_type': rows[0]['relationship_type'] = 'attached_gpu'
        else: rows[0]['source_resource_id'] = 'vm-001'
    replace_csv(source_folder, 'resource_relationships.csv', mutate)
    source = DatasetSource(source_folder)
    with pytest.raises(ValueError, match='resource_relationships.csv'):
        source.load_relationships(source.load_resources(source.load_catalog()))


@pytest.mark.parametrize('field,value', [
    ('end_time', '2020-01-01T00:00:00Z'), ('synthetic', 'False'),
    ('severity', 'urgent'), ('event_id', ' '),
])
def test_events_require_valid_provenance_and_time_order(source_folder, field, value):
    replace_csv(source_folder, 'events.csv', lambda rows: rows[0].update({field: value}))
    source = DatasetSource(source_folder)
    with pytest.raises(ValueError, match='events.csv'):
        source.event_rows({r.id for r in source.load_resources(source.load_catalog())})


def test_explicit_invalid_telemetry_cannot_supply_values(tmp_path):
    from datetime import datetime, timedelta, timezone
    source = object.__new__(DatasetSource)
    source.path = tmp_path
    source.start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    source.end, source.interval = source.start + timedelta(days=30), 15
    (tmp_path / 'metrics.csv').write_text('timestamp,resource_id,cpu_utilization_pct,memory_utilization_pct,disk_used_pct,disk_iops,network_in_mbps,network_out_mbps,quality_flag\n2026-08-01T00:00:00Z,vm,1,1,1,1,1,1,invalid_observation\n')
    row = next(source.metric_rows({'vm'}))
    assert row[2:8] == (None,) * 6


def test_gpu_memory_cannot_exceed_declared_capacity(tmp_path):
    from datetime import datetime, timedelta, timezone
    source = object.__new__(DatasetSource)
    source.path = tmp_path
    source.start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    source.end, source.interval = source.start + timedelta(days=30), 15
    (tmp_path / 'gpu_metrics.csv').write_text('timestamp,resource_id,gpu_utilization_pct,gpu_memory_utilization_pct,gpu_memory_used_gb,gpu_power_w\n2026-08-01T00:00:00Z,gpu,20,20,17,100\n')
    with pytest.raises(ValueError, match='capacity'):
        list(source.gpu_rows({'gpu': 16}))


@pytest.mark.parametrize('content', ['[]', '{}', '{"currency":"USD","currency":"INR"}'])
def test_manifest_shape_and_duplicate_fields_are_explicit_errors(source_folder, content):
    path = source_folder / 'assumptions.json'
    path.unlink()
    path.write_text(content)
    with pytest.raises(ValueError, match='assumptions.json'):
        DatasetSource(source_folder)


def test_invalid_money_is_a_source_validation_error():
    with pytest.raises(ValueError, match='monetary'):
        amount('not-a-price')


def test_source_change_is_detected_before_publication(source_folder):
    source = DatasetSource(source_folder)
    path = source_folder / 'pricing.csv'
    content = path.read_text()
    path.unlink()
    path.write_text(content + '\n')
    with pytest.raises(ValueError, match='source changed during import'):
        source.assert_unchanged()


@pytest.mark.parametrize('kind,field,value', [
    ('vm', 'status', 'mystery'), ('vm', 'lifecycle_state', 'unattached'),
    ('block_volume', 'status', 'in_use'), ('block_volume', 'lifecycle_state', 'active'),
    ('public_ip', 'status', 'associated'), ('gpu', 'attached_to', ''),
])
def test_inventory_lifecycle_cannot_contradict_attachment(source_folder, kind, field, value):
    def mutate(rows):
        row = next(r for r in rows if r['resource_type'] == kind)
        row[field] = value
    replace_csv(source_folder, 'resources.csv', mutate)
    source = DatasetSource(source_folder)
    with pytest.raises(ValueError, match='resources.csv'):
        source.load_resources(source.load_catalog())


@pytest.mark.parametrize('case,diagnostic', [
    ('duplicate', 'duplicate resource/month'), ('bad_month', 'canonical YYYY-MM'),
    ('gap', 'missing month'), ('missing_month', 'month count'),
    ('unknown_resource', 'Invalid synthetic billing reference'),
])
def test_invalid_billing_import_preserves_previous_snapshot(source_folder, settings, case, diagnostic):
    from app.database import connect
    from app.repositories.estate import import_dataset
    with connect(settings.resolved_database_path) as db:
        before = db.execute("SELECT payload FROM metadata WHERE key='dataset'").fetchone()[0]
    def mutate(rows):
        if case == 'duplicate': rows.append(dict(rows[0]))
        elif case == 'bad_month': rows[0]['billing_month'] = '2026-3'
        elif case == 'unknown_resource': rows[0]['resource_id'] = 'unknown-resource'
        elif case == 'missing_month': rows[:] = [r for r in rows if r['billing_month'] != '2026-04']
        else:
            for r in rows:
                if r['billing_month'] == '2026-04': r['billing_month'] = '2026-09'
    replace_csv(source_folder, 'billing_history.csv', mutate)
    with pytest.raises(ValueError, match=diagnostic):
        import_dataset(settings.resolved_database_path, source_folder)
    with connect(settings.resolved_database_path) as db:
        assert db.execute("SELECT payload FROM metadata WHERE key='dataset'").fetchone()[0] == before
        assert db.execute('SELECT COUNT(*) FROM resources').fetchone()[0] == 200


def test_mid_import_source_change_rolls_back_publication(source_folder, settings, monkeypatch):
    from app.database import connect
    from app.repositories.estate import import_dataset
    manifest = source_folder / 'assumptions.json'
    data = json.loads(manifest.read_text())
    data['dataset_name'] = 'Changed snapshot under test'
    manifest.unlink()
    manifest.write_text(json.dumps(data))
    with connect(settings.resolved_database_path) as db:
        before = db.execute("SELECT payload FROM metadata WHERE key='dataset'").fetchone()[0]
    original = DatasetSource.event_rows
    def changed_after_read(source, ids):
        rows = original(source, ids)
        events = source.path / 'events.csv'
        content = events.read_text()
        events.unlink()
        events.write_text(content + '\n')
        return rows
    monkeypatch.setattr(DatasetSource, 'event_rows', changed_after_read)
    with pytest.raises(ValueError, match='source changed during import'):
        import_dataset(settings.resolved_database_path, source_folder)
    with connect(settings.resolved_database_path) as db:
        assert db.execute("SELECT payload FROM metadata WHERE key='dataset'").fetchone()[0] == before
        assert db.execute('SELECT COUNT(*) FROM metrics').fetchone()[0] == 432000


def test_presentation_changes_do_not_revoke_analysis_but_optimizer_changes_do(source_folder, monkeypatch):
    baseline = DatasetSource(source_folder).version
    read = Path.read_bytes
    def changed_presentation(path):
        original = read(path)
        if path.parent.name == 'engine' and path.name in {'monitoring.py', 'service.py', 'expenses.py'}:
            return original + b'\n# presentation-only change\n'
        return original
    monkeypatch.setattr(Path, 'read_bytes', changed_presentation)
    assert DatasetSource(source_folder).version == baseline
    def changed_optimizer(path):
        original = read(path)
        return original + b'\n# analysis change\n' if path.parent.name == 'engine' and path.name == 'optimizer.py' else original
    monkeypatch.setattr(Path, 'read_bytes', changed_optimizer)
    assert DatasetSource(source_folder).version != baseline
