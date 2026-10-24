#!/usr/bin/env python3
"""Fetch only runtime credentials. Never print provider response bodies or secret values."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit


def write_environment(path, values):
    for key, value in values.items():
        if not isinstance(value, str) or any(c in value for c in ('\n', '\r', '\x00')):
            raise ValueError('Runtime secret values must be single-line strings')
    temporary = path.with_suffix('.new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(''.join(f'{key}={value}\n' for key, value in values.items()))
    os.replace(temporary, path)


def main():
    config = json.loads(Path('/opt/cloudpilot/config.json').read_text())
    response = subprocess.run([
        'aws', 'secretsmanager', 'get-secret-value', '--region', config['region'],
        '--secret-id', config['secret_arn'], '--query', 'SecretString', '--output', 'text',
    ], check=True, capture_output=True, text=True)
    secret = json.loads(response.stdout)
    username, password_hash = secret.get('DEMO_USERNAME', ''), secret.get('DEMO_PASSWORD_HASH', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{3,40}', username):
        raise ValueError('DEMO_USERNAME must be 3–40 letters, digits, hyphens or underscores')
    if not re.fullmatch(r'\$2[aby]\$(?:1[0-6])\$[./A-Za-z0-9]{53}', password_hash):
        raise ValueError('DEMO_PASSWORD_HASH must be a bcrypt hash with cost 10–16')
    backend = {}
    for target, fallback in [('QWEN_API_KEY', 'OPENAI_API_KEY'), ('QWEN_BASE_URL', 'OPENAI_BASE_URL'), ('QWEN_MODEL', 'CLOUDPILOT_LLM_MODEL')]:
        value = secret.get(target) or secret.get(fallback)
        if value:
            backend[target] = value
    if backend:
        if not all(backend.get(key) for key in ('QWEN_API_KEY', 'QWEN_BASE_URL', 'QWEN_MODEL')):
            raise ValueError('Configure all three Qwen values, or omit them all for rule-based mode')
        endpoint = urlsplit(backend['QWEN_BASE_URL'])
        if endpoint.scheme != 'https' or not endpoint.hostname or endpoint.username or endpoint.password:
            raise ValueError('Qwen base URL must be HTTPS without embedded credentials')
        if 'qwen' not in backend['QWEN_MODEL'].lower():
            raise ValueError('Select a Qwen model')
    runtime = Path('/run/cloudpilot')
    runtime.mkdir(mode=0o700, exist_ok=True)
    runtime.chmod(0o700)
    write_environment(runtime / 'backend.env', backend)
    write_environment(runtime / 'gateway.env', {'DEMO_USERNAME': username, 'DEMO_PASSWORD_HASH': password_hash})


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Runtime secret could not be loaded or validated. Check its schema and instance IAM permissions.', file=sys.stderr)
        sys.exit(1)
