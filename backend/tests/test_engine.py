from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import csv
import sqlite3

import pytest

from app.adapters.dataset import DatasetSource, SOURCE_FILES
from app.config import ROOT
from app.database import connect
from app.engine.costs import monthly_equivalent, stop_savings
from app.engine.optimizer import evaluate_candidate, optimize, replay
from app.engine.policy import POLICY
from app.engine.statistics import analyze, quantile
from app.models.contracts import ProviderPlan, Provenance, Resource
from app.repositories.estate import import_dataset

START = datetime(2026, 9, 1, tzinfo=timezone.utc)
END = START + timedelta(days=7)


def workload(cpu_peak=30, memory_peak=20):
    return [dict(timestamp=(START + timedelta(minutes=15 * index)).isoformat(), cpu=cpu_peak if index == 500 else 10,
                 memory=memory_peak if index == 500 else 10, disk=20, iops=2, network_in=.1, network_out=.1,
                 quality_flag='observed_synthetic') for index in range(672)]


def resource():
    return Resource(id='test-vm', name='Arbitrary name without outcome labels', type='vm', region='Noida', environment='development',
                    owner='engineering', team='engineering', dataset_version='fixture-v1', status='running', current_plan_id='eight',
                    hardware='Regular Intel', instance_family='Basic', vcpu=8, memory_gib=16, disk_gb=160,
                    storage_type='NVMe', transfer_allowance_gb=1000, criticality='standard', created_at=START,
                    lifecycle_state='active', monthly_cost=Decimal('1000.00'))


def plan(id, vcpu, memory=16, price='600'):
    # An independently specified test contract, not invented provider data in the app.
    return ProviderPlan(id=id, name=id, hardware='Regular Intel', instance_family='Basic', region='Noida', vcpu=vcpu,
                        memory_gib=memory, disk_gb=160, storage_type='NVMe', transfer_allowance_gb=1000,
                        compute_hourly_rate=Decimal('1.12345'), compute_quarterly_rate=Decimal(price) * 3,
                        compute_monthly_equivalent=Decimal(price), pricing_source='isolated verification fixture', catalog_version='fixture-v1',
                        region_verified=True, pricing_verified=True, resize_verified=True, storage_verified=True,
                        iops_limit=1000, network_mbps_limit=100)


def evidence():
    return Provenance(dataset_version='fixture-v1', catalog_version='fixture-v1', policy_version=POLICY.version,
                      engine_version='test', analysis_as_of=END, pricing_source='test', assumptions=[])


def test_brief_peak_rejects_cheapest_target_and_preserves_alternatives():
    rows = workload()
    analysis = analyze('test-vm', rows, START, END, 15, vcpu=8, memory_gib=16)
    assert analysis.statistics['cpu'].p99 == 10  # One short peak is absent from p99.
    assert analysis.statistics['cpu'].maximum == 30
    assert analysis.statistics['cpu_demand_cores'].maximum == pytest.approx(2.4)
    assert analysis.statistics['memory_demand_gib'].maximum == pytest.approx(3.2)
    candidates = [plan('two', 2, price='300'), plan('four', 4), plan('eight', 8, price='1000')]
    result = optimize(resource(), candidates, analysis, rows, evidence())[0]
    assert result.target_plan_id == 'four'
    assert result.conditional_monthly_savings == Decimal('400')
    assert result.ready is False  # Historical fixture cannot authorize live changes.
    two = next(candidate for candidate in result.candidates if candidate.plan.id == 'two')
    assert two.projected_cpu_peak == 120
    assert two.replay.breached_samples == 1
    assert any(item.code == 'cpu_peak' and item.status == 'failed' for item in two.checks)


def test_memory_pressure_and_unknown_provider_capabilities_are_hard_gates():
    rows = workload(memory_peak=90)
    analysis = analyze('test-vm', rows, START, END, 15)
    candidate = evaluate_candidate(resource(), plan('small-memory', 4, memory=8), analysis, rows, historical_snapshot=False)
    assert candidate.projected_memory_peak == 180
    assert not candidate.eligible
    assert any(item.code == 'memory_peak' and item.status == 'failed' for item in candidate.checks)
    rows = workload()
    analysis = analyze('test-vm', rows, START, END, 15)
    verified = evaluate_candidate(resource(), plan('four', 4), analysis, rows, historical_snapshot=False)
    assert verified.eligible
    scaled = evaluate_candidate(resource(), plan('four', 4), analysis, rows, multiplier=3, historical_snapshot=False)
    assert next(item.actual for item in scaled.checks if item.code == 'iops_capacity') == 6
    assert next(item.actual for item in scaled.checks if item.code == 'network_capacity') == pytest.approx(.6)
    missing_capacity = plan('unknown', 4).model_copy(update={'iops_limit': None, 'region_verified': False})
    unknown = evaluate_candidate(resource(), missing_capacity, analysis, rows, historical_snapshot=False)
    assert unknown.capacity_eligible and not unknown.eligible
    assert {item.code for item in unknown.checks if item.status == 'unknown'} == {'iops_capacity', 'region_availability'}
    wrong_family = plan('wrong', 4).model_copy(update={'hardware': 'Premium AMD'})
    assert not evaluate_candidate(resource(), wrong_family, analysis, rows).capacity_eligible
    shrunk_disk = plan('shrunk', 4).model_copy(update={'disk_gb': 80})
    assert any(item.code == 'disk_no_shrink' and item.status == 'failed' for item in evaluate_candidate(resource(), shrunk_disk, analysis, rows).checks)


def test_inclusive_capacity_boundary_and_stress_are_separate_checks():
    rows = workload(cpu_peak=40)
    analysis = analyze('test-vm', rows, START, END, 15)
    conservative = evaluate_candidate(resource(), plan('four', 4), analysis, rows, historical_snapshot=False)
    assert next(item for item in conservative.checks if item.code == 'cpu_peak').status == 'passed'
    assert conservative.replay.breached_samples == 0
    assert conservative.replay.stress_breached_samples == 1
    assert not conservative.eligible
    no_stress = evaluate_candidate(resource(), plan('four', 4), analysis, rows, historical_snapshot=False, policy=replace(POLICY, stress_multiplier=1))
    assert no_stress.eligible


def test_replay_counts_overlapping_breaches_once_and_respects_gaps():
    rows = workload()[:4]
    for row in rows[:2]:
        row['cpu'], row['memory'] = 90, 90
    rows[2]['cpu'] = None
    result = replay(rows, 1, 1, 4)
    assert result.cpu_breaches == result.memory_breaches == 2
    assert result.breached_samples == 2
    assert result.longest_breach_samples == 2
    assert result.missing_samples == 1
    assert result.sample_count == 3


def test_quality_never_fills_missing_values_and_checks_cutoff_age():
    rows = workload()
    for row in rows[:100]:
        row['memory'] = None
    result = analyze('test-vm', rows, START, END, 15)
    assert result.quality.valid_samples == 572
    assert result.quality.metric_coverage['cpu'] == 1
    assert not result.quality.sufficient
    assert result.statistics['memory'].count == 572
    stale = analyze('test-vm', workload()[:-8], START, END, 15)
    assert stale.quality.freshness_seconds == 8100
    assert not stale.quality.sufficient


def test_decimal_prices_stop_billing_and_quantile_contract():
    assert monthly_equivalent(Decimal('100.00')) == Decimal('33.33')
    assert stop_savings(Decimal('900')) == Decimal('0.00')
    assert stop_savings(None) is None
    assert quantile([0, 10, 20, 30], .95) == pytest.approx(28.5)


def test_duplicate_telemetry_rolls_back_import_without_damaging_previous_snapshot(settings, tmp_path):
    folder = tmp_path / 'malformed'
    folder.mkdir()
    for filename in SOURCE_FILES:
        if filename != 'metrics.csv':
            (folder / filename).symlink_to(ROOT / 'test-data' / filename)
    with (ROOT / 'test-data/metrics.csv').open() as stream:
        header, first = next(stream), next(stream)
    (folder / 'metrics.csv').write_text(header + first + first)
    with connect(settings.resolved_database_path) as connection:
        original = connection.execute("SELECT payload FROM metadata WHERE key='dataset'").fetchone()[0]
    with pytest.raises(ValueError, match='Duplicate metric'):
        import_dataset(settings.resolved_database_path, folder)
    with connect(settings.resolved_database_path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM resources').fetchone()[0] == 200
        assert connection.execute('SELECT COUNT(*) FROM metrics').fetchone()[0] == 432000
        assert connection.execute("SELECT payload FROM metadata WHERE key='dataset'").fetchone()[0] == original


def test_oracle_files_do_not_enter_version_or_optimizer(tmp_path):
    folder = tmp_path / 'source'
    folder.mkdir()
    for filename in SOURCE_FILES:
        (folder / filename).symlink_to(ROOT / 'test-data' / filename)
    original = DatasetSource(folder).version
    (folder / 'test_oracle.csv').write_text('resource_id,expected_action\nvm-001,delete_everything\n')
    (folder / 'workload_labels.csv').write_text('resource_id,label\nvm-001,force_resize\n')
    assert DatasetSource(folder).version == original


def test_metric_adapter_reports_invalid_values_and_rejects_off_grid(tmp_path):
    source = object.__new__(DatasetSource)
    source.path, source.start, source.end, source.interval = tmp_path, START, END, 15
    header = 'timestamp,resource_id,cpu_utilization_pct,memory_utilization_pct,disk_used_pct,disk_iops,network_in_mbps,network_out_mbps,quality_flag\n'
    path = tmp_path / 'metrics.csv'
    path.write_text(header + '2026-09-01 00:00:00,test-vm,NaN,20,20,2,.1,.1,observed_synthetic\n')
    row = list(source.metric_rows({'test-vm'}))[0]
    assert row[2] is None and row[-1] == 'invalid_observation'
    path.write_text(header + '2026-09-01 00:01:00,test-vm,20,20,20,2,.1,.1,observed_synthetic\n')
    with pytest.raises(ValueError, match='off-grid'):
        list(source.metric_rows({'test-vm'}))
