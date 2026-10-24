"""One bounded text call shared by explanations and scenario interpretation."""
import json

import httpx


class LanguageError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def settings(config):
    return (config.get('QWEN_API_KEY') or config.get('OPENAI_API_KEY'),
            config.get('QWEN_BASE_URL') or config.get('OPENAI_BASE_URL'),
            config.get('QWEN_MODEL') or config.get('CLOUDPILOT_LLM_MODEL') or 'qwen.qwen3-coder-480b-a35b-instruct')


async def complete(config, instruction, evidence, *, max_tokens=700):
    key, base, model = settings(config)
    if not key or not base:
        raise LanguageError('Server LLM credentials and base URL are not configured', 503)
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(base.rstrip('/') + '/chat/completions',
                headers={'Authorization': f'Bearer {key}'}, json={
                    'model': model, 'temperature': 0, 'max_tokens': max_tokens,
                    'messages': [{'role': 'system', 'content': instruction},
                                 {'role': 'user', 'content': json.dumps(evidence)}]})
            response.raise_for_status()
            text = response.json()['choices'][0]['message']['content']
            if not isinstance(text, str) or not text.strip() or len(text) > 12000:
                raise ValueError('Invalid model response')
            return text.strip(), model
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError, AttributeError):
        raise LanguageError('The LLM is unavailable or returned an invalid response') from None
