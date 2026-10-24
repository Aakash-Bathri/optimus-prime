#!/usr/bin/env python3
"""Exercise the hosted stack locally with disposable data and no AWS credentials."""
import base64
import json
from pathlib import Path
import runpy
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid

helpers = runpy.run_path(str(Path(__file__).with_name('validate-templates.py')))
render = helpers['render']
project = 'cloudpilot-aws-smoke-' + uuid.uuid4().hex[:8]

with tempfile.TemporaryDirectory(prefix='cloudpilot-aws-smoke-') as directory:
    folder = Path(directory)
    for name in ('database', 'caddy-data', 'caddy-config'):
        (folder / name).mkdir(mode=0o777)
        (folder / name).chmod(0o777)
    password = b'temporary-local-smoke-password'
    hashed = subprocess.run(['docker', 'run', '--rm', '-i', 'caddy:2.10.2-alpine', 'caddy', 'hash-password'],
                            input=password + b'\n', capture_output=True, check=True).stdout.decode().strip()
    (folder / 'backend.env').write_text('')
    (folder / 'gateway.env').write_text(f'DEMO_USERNAME=investor\nDEMO_PASSWORD_HASH={hashed}\n')
    compose = render('compose.yaml.tftpl', {
        'backend_image': 'cloudpilot-backend:aws-check', 'frontend_image': 'cloudpilot-frontend:aws-check',
        'domain_name': 'localhost', 'region': 'ap-south-1', 'log_group': '/unused-local-test',
    }, folder)
    for old, new in {
        '/run/cloudpilot/backend.env': str(folder / 'backend.env'),
        '/run/cloudpilot/gateway.env': str(folder / 'gateway.env'),
        '/opt/cloudpilot/Caddyfile': str(folder / 'Caddyfile'),
        '/srv/cloudpilot/database': str(folder / 'database'),
        '/srv/cloudpilot/caddy-data': str(folder / 'caddy-data'),
        '/srv/cloudpilot/caddy-config': str(folder / 'caddy-config'),
        '"80:80"': '"127.0.0.1::80"', '"443:443"': '"127.0.0.1::443"',
    }.items():
        compose = compose.replace(old, new)
    (folder / 'compose.yaml').write_text(compose)
    caddy = render('Caddyfile.tftpl', {'domain_name': 'localhost', 'acme_email': 'local@example.com'}, folder)
    (folder / 'Caddyfile').write_text(caddy.replace('localhost {', 'https://localhost {\n    tls internal'))
    (folder / 'local.yaml').write_text('services:\n' + ''.join(f'  {name}:\n    logging: !override\n      driver: local\n' for name in ('backend', 'frontend', 'gateway')))
    command = ['docker', 'compose', '-p', project, '-f', str(folder / 'compose.yaml'), '-f', str(folder / 'local.yaml')]
    def dc(*args, **kwargs):
        return subprocess.run(command + list(args), check=True, capture_output=True, text=True, **kwargs)
    try:
        dc('up', '-d', '--wait', '--wait-timeout', '300')
        port = dc('port', 'gateway', '443').stdout.strip().rsplit(':', 1)[1]
        root_ca = folder / 'caddy-data/caddy/pki/authorities/local/root.crt'
        for _ in range(30):
            if root_ca.exists():
                break
            time.sleep(1)
        context = ssl.create_default_context(cafile=str(root_ca))
        origin = 'https://localhost:' + port
        authorization = 'Basic ' + base64.b64encode(b'investor:' + password).decode()
        def request(path, body=None, method=None, authenticated=True):
            headers = {'Authorization': authorization} if authenticated else {}
            if body is not None:
                headers['Content-Type'] = 'application/json'
            req = urllib.request.Request(origin + path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
            return urllib.request.urlopen(req, context=context, timeout=30)
        try:
            request('/api/health', authenticated=False)
            raise AssertionError('Gateway allowed an anonymous request')
        except urllib.error.HTTPError as error:
            assert error.code == 401
        assert json.load(request('/api/health'))['status'] == 'ok'
        assert request('/').status == 200
        try:
            request('/api/execution/resources')
            raise AssertionError('Hosted execution API is exposed')
        except urllib.error.HTTPError as error:
            assert error.code == 404
        forecast = json.load(request('/api/monitoring/evaluate', {'days': 30}))
        assert len(forecast['points']) == 30
        assert dc('exec', '-T', 'backend', 'id', '-u').stdout.strip() == '10001'
        finding = json.load(request('/api/recommendations?limit=1'))['items'][0]
        json.load(request('/api/recommendations/' + finding['id'], {'decision': 'accepted', 'version': finding['version'], 'expected_revision': finding['decision_revision']}, method='PATCH'))
        dc('restart', 'backend')
        for _ in range(60):
            try:
                if json.load(request('/api/health'))['status'] == 'ok':
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(1)
        assert json.load(request('/api/recommendations/' + finding['id']))['decision'] == 'accepted'
        dc('exec', '-T', 'backend', 'python', input=(helpers['TEMPLATES'] / 'backup.py').read_text())
        assert list((folder / 'database/backups').glob('*.sqlite3'))
        print('PASS: authenticated HTTPS, anonymous 401, execution 404, frontend, forecast, non-root backend, restart persistence and consistent backup.')
    finally:
        dc('down', '--volumes', '--remove-orphans')
