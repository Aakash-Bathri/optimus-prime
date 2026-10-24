import { useState } from 'react';
import { post } from './lib/api';

export default function FindingExplanation({ id }: { id: string }) {
  const [text, setText] = useState('');
  const [source, setSource] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function explain() {
    setBusy(true); setError('');
    try {
      const result = await post<{ explanation: string; source: string }>('/monitoring/explain', { scenario: {}, recommendation_id: id });
      setText(result.explanation); setSource(result.source !== 'rules' ? 'LLM explanation' : 'Evidence summary · LLM unavailable');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not explain finding'); }
    finally { setBusy(false); }
  }
  return <section className="notice"><div><h3>Explain this finding</h3><button className="secondary-button" disabled={busy} onClick={() => void explain()}>{busy ? 'Asking the LLM…' : 'Explain in plain language'}</button>{text && <><small>{source}</small><p style={{ whiteSpace: 'pre-line' }}>{text}</p></>}{error && <p role="alert">{error}</p>}</div></section>;
}
