"""Server-enforced workspace roles; local persona switching is demo-only."""
import hashlib
import hmac
import secrets
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Literal

Role = Literal['engineer', 'finance', 'leadership']
COOKIE = 'cloudpilot_role'


class RoleChoice(BaseModel):
    role: Role


def install_access(app, config):
    key = secrets.token_bytes(32)

    def signed(role):
        return role + '.' + hmac.new(key, role.encode(), hashlib.sha256).hexdigest()

    def role_for(request):
        value = request.cookies.get(COOKIE, '')
        role = value.split('.')[0]
        if role in ('engineer', 'finance', 'leadership') and hmac.compare_digest(value, signed(role)):
            return role
        return config.workspace_role

    def local(request):
        hosts = {'localhost', '127.0.0.1', '::1', 'testserver'}
        origin = request.headers.get('origin')
        return (request.url.hostname in hosts and request.client and request.client.host in hosts
                and (not origin or urlsplit(origin).hostname in hosts)
                and request.headers.get('sec-fetch-site') != 'cross-site')

    @app.middleware('http')
    async def authorize(request: Request, call_next):
        role = role_for(request)
        request.state.workspace_role = role
        path = request.url.path
        blocked = False
        if path.startswith('/api/') and role != 'engineer':
            blocked = (path.startswith('/api/execution') or path == '/api/local-operator-session'
                       or path == '/api/audit'
                       or (request.method == 'PATCH')
                       or (role == 'leadership' and request.method not in ('GET', 'HEAD', 'OPTIONS')
                           and path != '/api/workspace-role'))
        if blocked:
            return JSONResponse({'code': 'role_forbidden', 'message': f'{role.title()} view cannot perform this action'}, status_code=403)
        response = await call_next(request)
        if path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/workspace-role')
    def current_role(request: Request):
        return {'role': role_for(request), 'can_switch': bool(config.local_token_prefill and local(request)),
                'mode': 'local_demo' if config.local_token_prefill else 'configured_role'}

    @app.post('/api/workspace-role')
    def choose_role(body: RoleChoice, request: Request):
        if not config.local_token_prefill or not local(request):
            return JSONResponse({'message': 'Role switching is available only in the local demo'}, status_code=403)
        response = JSONResponse({'role': body.role})
        response.set_cookie(COOKIE, signed(body.role), httponly=True, samesite='strict',
                            secure=request.url.scheme == 'https', path='/')
        return response
