#!/usr/bin/env python3
"""Render and syntax-check cloud-init locally, optionally checking Compose/Caddy with Docker."""
import argparse
import ast
import base64
import gzip
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'demo/templates'


def render(name, values, cwd):
    expression = 'jsonencode(templatefile(' + json.dumps(str(TEMPLATES / name)) + ',' + json.dumps(values) + '))\n'
    result = subprocess.run(['terraform', 'console', '-no-color'], input=expression, text=True,
                            cwd=cwd, capture_output=True, check=True)
    return json.loads(json.loads(result.stdout.strip()))


def encoded(value):
    return base64.b64encode(value.encode()).decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docker', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='cloudpilot-templates-') as folder:
        folder = Path(folder)
        compose = render('compose.yaml.tftpl', {
            'backend_image': '123456789012.dkr.ecr.ap-south-1.amazonaws.com/cloudpilot-demo/backend:test',
            'frontend_image': '123456789012.dkr.ecr.ap-south-1.amazonaws.com/cloudpilot-demo/frontend:test',
            'domain_name': 'demo.example.com', 'region': 'ap-south-1', 'log_group': '/cloudpilot-demo/containers',
        }, folder)
        caddy = render('Caddyfile.tftpl', {'domain_name': 'demo.example.com', 'acme_email': 'founder@example.com'}, folder)
        cloudinit = render('cloud-init.sh.tftpl', {
            'volume_id': 'vol0123456789abcdef0', 'compose': encoded(compose), 'caddyfile': encoded(caddy),
            'configuration': encoded(json.dumps({'region': 'ap-south-1', 'secret_arn': 'test', 'registry': 'test'})),
            'secret_loader': encoded((TEMPLATES / 'load-secrets.py').read_text()),
            'deploy_script': encoded((TEMPLATES / 'deploy.sh').read_text()),
            'backup_script': encoded((TEMPLATES / 'backup.py').read_text()),
        }, folder)
        (folder / 'cloud-init.sh').write_text(cloudinit)
        subprocess.run(['bash', '-n', str(folder / 'cloud-init.sh')], check=True)
        assert len(gzip.compress(cloudinit.encode())) <= 16384, 'EC2 compressed user-data exceeds 16 KiB'
        for source in TEMPLATES.glob('*.py'):
            ast.parse(source.read_text())
        assert 'docker.sock' not in compose and '8001:8001' not in compose
        assert 'CLOUDPILOT_EXECUTION_ENABLED: "false"' in compose
        if args.docker:
            (folder / 'backend.env').write_text('QWEN_API_KEY=placeholder-dollar$literal\n')
            hashed = subprocess.run(['docker', 'run', '--rm', '-i', 'caddy:2.10.2-alpine', 'caddy', 'hash-password'],
                                    input=b'a-test-password-with-20-characters\n', capture_output=True, check=True).stdout.decode().strip()
            (folder / 'gateway.env').write_text(f'DEMO_USERNAME=investor\nDEMO_PASSWORD_HASH={hashed}\n')
            (folder / 'Caddyfile').write_text(caddy)
            patched = compose.replace('/run/cloudpilot/backend.env', str(folder / 'backend.env')).replace('/run/cloudpilot/gateway.env', str(folder / 'gateway.env'))
            (folder / 'compose.yaml').write_text(patched)
            configured = subprocess.run(['docker', 'compose', '-f', str(folder / 'compose.yaml'), 'config', '--format', 'json'], capture_output=True, text=True, check=True)
            services = json.loads(configured.stdout)['services']
            assert services['gateway']['environment']['DEMO_PASSWORD_HASH'].replace('$$', '$') == hashed
            assert services['backend']['environment']['QWEN_API_KEY'].replace('$$', '$') == 'placeholder-dollar$literal'
            assert not services['backend'].get('ports') and not services['frontend'].get('ports')
            subprocess.run(['docker', 'run', '--rm', '--env-file', str(folder / 'gateway.env'),
                            '-v', str(folder / 'Caddyfile') + ':/etc/caddy/Caddyfile:ro',
                            'caddy:2.10.2-alpine', 'caddy', 'validate', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile'], check=True)
        print('Rendered cloud-init, shell/Python syntax and EC2 user-data size checks passed.')
        if args.docker:
            print('Compose secret escaping, internal-only app ports and Caddy authentication validation passed.')


if __name__ == '__main__':
    main()
