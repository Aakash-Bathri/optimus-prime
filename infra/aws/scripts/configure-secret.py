#!/usr/bin/env python3
"""Upload demo gateway/Qwen credentials outside Terraform; never writes a plaintext file."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--secret-arn', required=True)
    parser.add_argument('--env-file', type=Path, help='Optional .env containing Qwen configuration; requires python-dotenv')
    args = parser.parse_args()
    match = re.fullmatch(r'arn:aws:secretsmanager:([a-z0-9-]+):[0-9]{12}:secret:.+', args.secret_arn)
    if not match:
        parser.error('Use runtime_secret_arn from Terraform bootstrap outputs')
    if any(key.startswith('AWS_ENDPOINT_URL') for key in os.environ):
        parser.error('Remove AWS endpoint overrides before deploying to real AWS')
    region = match[1]
    config = dict(os.environ)
    if args.env_file:
        from dotenv import dotenv_values
        config = {**dotenv_values(args.env_file), **config}
    username = input('Investor demo username (3–40 letters/digits/_/-): ').strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{3,40}', username):
        parser.error('Invalid demo username')
    password = getpass.getpass('New demo access password (at least 16 characters): ')
    if len(password) < 16 or len(password.encode()) > 72 or '\n' in password or '\r' in password:
        parser.error('Use a password of at least 16 characters and at most 72 UTF-8 bytes')
    if password != getpass.getpass('Repeat demo access password: '):
        parser.error('Passwords differ')
    result = subprocess.run(['docker', 'run', '--rm', '-i', 'caddy:2.10.2-alpine', 'caddy', 'hash-password'],
                            input=password.encode() + b'\n', capture_output=True, check=True)
    hashed = result.stdout.decode().strip()
    if not re.fullmatch(r'\$2[aby]\$1[0-6]\$[./A-Za-z0-9]{53}', hashed):
        raise RuntimeError('Password hashing failed')
    secret = {'DEMO_USERNAME': username, 'DEMO_PASSWORD_HASH': hashed}
    for target, fallback in [('QWEN_API_KEY', 'OPENAI_API_KEY'), ('QWEN_BASE_URL', 'OPENAI_BASE_URL'), ('QWEN_MODEL', 'CLOUDPILOT_LLM_MODEL')]:
        value = config.get(target) or config.get(fallback)
        if value:
            secret[target] = value
    if len(secret) not in (2, 5):
        parser.error('Provide all three Qwen settings, or omit them all for rule-based explanations')
    subprocess.run(['aws', 'secretsmanager', 'put-secret-value', '--region', region,
                    '--secret-id', args.secret_arn, '--secret-string', 'file:///dev/stdin'],
                   input=json.dumps(secret).encode(), check=True, stdout=subprocess.DEVNULL)
    print('Runtime secret updated. Only demo gateway credentials and Qwen settings were uploaded.')
    print('For a running instance, use SSM and sudo systemctl restart cloudpilot to reload credentials.')


if __name__ == '__main__':
    try:
        main()
    except (subprocess.CalledProcessError, RuntimeError, ImportError):
        print('Secret setup failed. Check Docker, AWS CLI permissions and python-dotenv availability.', file=sys.stderr)
        sys.exit(1)
