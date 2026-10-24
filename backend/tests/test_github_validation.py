import base64
from unittest.mock import Mock

import httpx
import pytest

from app.execution.github import GitHub
from app.execution.contracts import WorkflowError


@pytest.mark.parametrize('payload', ['not json', 'null', '"unexpected text"', '42'])
def test_malformed_success_response_is_a_safe_integration_error(payload):
    response = httpx.Response(200, text=payload, request=httpx.Request('GET', 'https://example.test'))
    with pytest.raises(WorkflowError, match='invalid response') as error:
        GitHub.request(Mock(request=Mock(return_value=response)), 'GET', '/test')
    assert error.value.status == 502


@pytest.mark.parametrize('content', ['@@@@', base64.b64encode(b'\xff').decode(), None])
def test_invalid_source_encoding_has_an_actionable_error(monkeypatch, content):
    github = GitHub({})
    monkeypatch.setattr(github, 'request', lambda *a, **k: {'encoding': 'base64', 'content': content, 'sha': 'a'})
    with pytest.raises(WorkflowError, match='base64 UTF-8'):
        github.file(None, 'owner/repo', 'main.tf', 'main')


def test_invalid_app_key_is_configuration_error(tmp_path):
    path = tmp_path / 'invalid.pem'
    path.write_text('not a private key')
    github = GitHub({'CLOUDPILOT_GITHUB_TEST_REPO': 'owner/repo', 'GITHUB_APP_ID': '123', 'GITHUB_APP_PRIVATE_KEY_PATH': str(path)})
    with pytest.raises(WorkflowError, match='not configured') as error:
        github.client('owner/repo')
    assert error.value.status == 503


def test_closed_pr_is_not_reported_as_new_success(monkeypatch):
    from contextlib import nullcontext
    github = GitHub({})
    monkeypatch.setattr(github, 'client', lambda repo: nullcontext(object()))
    monkeypatch.setattr(github, 'request', lambda *a, **k: [{'state': 'closed', 'number': 99}])
    with pytest.raises(WorkflowError, match='fresh preview') as error:
        github.create_pr({'id': 'fresh-id', 'binding': {'repository': 'owner/repo'}, 'terraform': {}}, lambda *a: None)
    assert error.value.status == 409
