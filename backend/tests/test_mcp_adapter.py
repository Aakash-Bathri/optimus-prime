import asyncio
import pytest
from app.mcp.localstack import Cloud, extract_json
from app.execution.contracts import WorkflowError


@pytest.mark.parametrize('payload', [None, 1, {}, [{'type': 'text'}], [{'type': 'text', 'text': None}]])
def test_malformed_mcp_content_is_a_controlled_error(payload):
    with pytest.raises(WorkflowError, match='no AWS JSON'):
        extract_json(payload)


@pytest.mark.parametrize('failure,status', [(TimeoutError('provider-secret'), 504), (RuntimeError('provider-secret'), 502)])
def test_provider_failure_has_an_actionable_sanitized_error(failure, status):
    class Tool:
        async def ainvoke(self, args):
            raise failure
    with pytest.raises(WorkflowError) as result:
        asyncio.run(Cloud(Tool()).inventory())
    assert result.value.status == status
    assert 'provider-secret' not in str(result.value)


def test_state_wait_has_one_total_deadline_even_when_inspect_is_slow():
    class Tool:
        async def ainvoke(self, args):
            await asyncio.sleep(5)
    with pytest.raises(WorkflowError, match='state transition timed out') as result:
        asyncio.run(Cloud(Tool()).wait('i-11111111', 'running', timeout_seconds=0.01))
    assert result.value.status == 504
