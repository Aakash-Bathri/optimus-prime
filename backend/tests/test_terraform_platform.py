"""Validation must work when the repository lock was generated on another OS."""
from pathlib import Path
from types import SimpleNamespace

from app.execution.terraform import Terraform


def test_validation_uses_trusted_platform_lock_and_preserves_repository_lock(tmp_path, monkeypatch):
    from app.execution import terraform as module
    source = Path(module.ROOT) / 'infra/demo-terraform'
    root = tmp_path / 'project'
    template = root / 'infra/demo-terraform'
    template.mkdir(parents=True)
    (template / '.terraform/providers').mkdir(parents=True)
    main = (source / 'main.tf').read_text()
    (template / 'main.tf').write_text(main)
    trusted = (source / '.terraform.lock.hcl').read_text()
    (template / '.terraform.lock.hcl').write_text(trusted)
    monkeypatch.setattr(module, 'ROOT', root)
    monkeypatch.setattr(module.shutil, 'which', lambda name: '/terraform')
    calls = []
    def run(args, cwd, **kwargs):
        assert (cwd / '.terraform.lock.hcl').read_text() == trusted
        calls.append(args[1])
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(module.subprocess, 'run', run)
    snapshot = {'files': {'main.tf': main, '.terraform.lock.hcl': 'remote-platform-only',
                         'terraform.tfvars.json': '{"api_instance_type":"m5.2xlarge"}'},
                'mapping': {'candidate_instance_types': ['m5.xlarge']}}
    result = Terraform().prepare(snapshot, {'variables_file': 'terraform.tfvars.json', 'variable': 'api_instance_type'},
                                 'm5.2xlarge', 'm5.xlarge')
    assert calls == ['init', 'fmt', 'validate']
    assert result['validation']['validate'] == 'passed'
    assert snapshot['files']['.terraform.lock.hcl'] == 'remote-platform-only'
