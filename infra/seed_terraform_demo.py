"""Seed the Terraform fixture in local Docker; retain its state on the app-data volume."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlsplit


def main():
    root = Path(__file__).resolve().parents[1]
    endpoint = os.environ.get('CLOUDPILOT_LOCALSTACK_ENDPOINT', 'http://127.0.0.1:4566')
    if urlsplit(endpoint).hostname not in {'localstack', '127.0.0.1', 'localhost'}:
        raise RuntimeError('Demo seeding requires a local LocalStack endpoint')
    source = root / 'infra/demo-terraform'
    work = root / 'data/local/terraform-demo'
    work.mkdir(parents=True, exist_ok=True)
    for name in ('main.tf', '.terraform.lock.hcl'):
        shutil.copyfile(source / name, work / name)
    # Preserve the last applied size across container restarts.
    variables = work / 'terraform.tfvars.json'
    if not variables.exists():
        shutil.copyfile(source / variables.name, variables)
    (work / 'local_override.tf.json').write_text(json.dumps({
        'provider': {'aws': {'endpoints': [{'ec2': endpoint, 'sts': endpoint}]}}
    }))
    subprocess.run(['terraform', 'init', '-input=false', '-no-color', '-lockfile=readonly',
                    '-plugin-dir=' + str(source / '.terraform/providers')], cwd=work, check=True)
    subprocess.run(['terraform', 'apply', '-auto-approve', '-input=false', '-no-color'], cwd=work, check=True)


if __name__ == '__main__':
    main()
