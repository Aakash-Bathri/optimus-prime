import { useState } from 'react';

type Snapshot = { provider_id: string; instance_type: string; state: string; tags: Record<string, string> };
type Binding = { resource_id: string; provider_id: string; management: 'terraform' | 'manual'; repository?: string; current?: Snapshot };
type Proposal = {
  id: string; status: string; digest: string; binding: Binding; before: Snapshot;
  recommendation: { action: string; target_instance_type?: string; evidence: { source: string; version: string; reason: string; expires_at: string } };
  steps: string[]; agent: { explanation: string; mode: string; tool_calls: { tool: string }[] };
  patch?: { diff: string; validation: Record<string, string> }; rollback: string; error?: string;
  result?: { url?: string; after?: Snapshot; verified_at?: string };
};
type Audit = { sequence: number; timestamp: string; event: string; proposal_id: string | null; details: unknown };
const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export default function Execution() {
  const [token, setToken] = useState('');
  const [resources, setResources] = useState<Binding[]>([]);
  const [history, setHistory] = useState<Proposal[]>([]);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [resourceId, setResourceId] = useState('demo-manual-01');
  const [action, setAction] = useState('resize');
  const [target, setTarget] = useState('m5.xlarge');
  const [mode, setMode] = useState('llm');
  const [engineJson, setEngineJson] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const selected = resources.find(resource => resource.resource_id === resourceId);

  async function api<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${baseUrl}/api/execution${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const value = await response.json();
    if (!response.ok) throw new Error(value.message ?? `Request failed (${response.status})`);
    return value as T;
  }
  async function refresh() {
    const [bindings, proposals, events] = await Promise.all([
      api<Binding[]>('/resources'), api<Proposal[]>('/proposals'), api<Audit[]>('/audit'),
    ]);
    setResources(bindings); setHistory(proposals); setAudit(events);
    setProposal(current => current ? proposals.find(item => item.id === current.id) ?? current : current);
  }
  async function run(work: () => Promise<void>) {
    setBusy(true); setError('');
    try { await work(); } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Request failed');
      try { await refresh(); } catch { /* Preserve the original actionable error. */ }
    } finally { setBusy(false); }
  }
  async function prepare() {
    const recommendation = engineJson.trim() ? JSON.parse(engineJson) : await api(
      `/demo/recommendation/${encodeURIComponent(resourceId)}?action=${action}&target=${target}`,
    );
    const result = await api<Proposal>('/proposals', { recommendation, mode });
    setProposal(result); await refresh();
  }

  return <section className="execution" aria-labelledby="execution-title">
    <div className="section-heading"><div><p className="eyebrow">PERSON 5 · LOCALSTACK DEMO</p>
      <h2 id="execution-title">Review and execute a change</h2></div><span>Preview → approve → execute → verify</span></div>
    <p>Terraform resources receive a GitHub pull request for customer review and apply. Manual resources change directly in LocalStack after your approval.</p>
    <div className="controls">
      <label>Local operator token<input type="password" autoComplete="off" value={token} onChange={event => setToken(event.target.value)} placeholder="CLOUDPILOT_EXECUTION_TOKEN from .env" /></label>
      <button disabled={busy || !token} onClick={() => void run(refresh)}>Connect / refresh</button>
      <button disabled={busy || !token} onClick={() => void run(async () => { await api('/demo/setup', {}); await refresh(); })}>Register demo resources</button>
    </div>
    <p className="note">The token stays in this page's memory. Registration uses the fixtures' explicit terraform/manual tags. Run infra/seed_demo.ps1 if they are missing.</p>
    {error && <p role="alert" className="error">{error}</p>}
    {busy && <p role="status">Working… Live integrations and Terraform validation may take a minute.</p>}
    {resources.length > 0 && <>
      <div className="controls">
        <label>Resource<select value={resourceId} onChange={event => { setResourceId(event.target.value); setAction('resize'); }}>
          {resources.map(resource => <option key={resource.resource_id} value={resource.resource_id}>{resource.resource_id} · {resource.management}</option>)}
        </select></label>
        <label>Agent<select value={mode} onChange={event => setMode(event.target.value)}><option value="llm">Bedrock Mantle + LangChain</option><option value="scripted">Scripted tools (no LLM)</option></select></label>
        <label>Action<select value={action} onChange={event => setAction(event.target.value)}><option value="resize">Resize</option>
          {selected?.management === 'manual' && <><option value="stop">Stop</option><option value="start">Start</option></>}
        </select></label>
        {action === 'resize' && <label>Target type<select value={target} onChange={event => setTarget(event.target.value)}>
          {['m5.large', 'm5.xlarge', 'm5.2xlarge'].map(type => <option key={type}>{type}</option>)}
        </select></label>}
      </div>
      <p>Current: <strong>{selected?.current?.instance_type ?? 'Unavailable'}</strong> · {selected?.current?.state} · {selected?.provider_id}</p>
      <details><summary>Use a recommendation from the engine</summary><p>Paste the versioned Recommendation JSON from the backend contract. Leave empty to use an explicitly labeled demo stub.</p>
        <textarea rows={8} value={engineJson} onChange={event => setEngineJson(event.target.value)} aria-label="Engine recommendation JSON" /></details>
      <p className="note">Demo stubs test the control-plane workflow. They contain no measured capacity or savings evidence.</p>
      <button disabled={busy} onClick={() => void run(prepare)}>Prepare change preview</button>
    </>}
    {proposal && <article className="proposal" aria-labelledby="proposal-title">
      <div className="section-heading"><h3 id="proposal-title">{proposal.binding.resource_id} · {proposal.recommendation.action}</h3><strong>{proposal.status}</strong></div>
      <p>{proposal.before.instance_type} / {proposal.before.state} → {proposal.recommendation.target_instance_type ?? proposal.recommendation.action}</p>
      <p><strong>Evidence: {proposal.recommendation.evidence.source}</strong> · {proposal.recommendation.evidence.version}<br />Expires: {proposal.recommendation.evidence.expires_at}</p>
      <p>{proposal.agent.explanation}</p>
      <p className="note">Agent mode: {proposal.agent.mode}. Tools: {proposal.agent.tool_calls.map(item => item.tool).join(' → ')}</p>
      <ol>{proposal.steps.map(step => <li key={step}>{step}</li>)}</ol>
      {proposal.binding.management === 'manual' && proposal.recommendation.action === 'resize' && proposal.before.state === 'running' && <p><strong>This resize stops and restarts the demo VM.</strong></p>}
      {proposal.patch && <><pre aria-label="Terraform diff">{proposal.patch.diff}</pre><p>Validation: fmt passed · validate passed · candidate plan not run</p></>}
      <details><summary>Exact approval identity</summary><p className="mono">Proposal: {proposal.id}<br />Digest: {proposal.digest}</p></details>
      <div className="controls">
        <button disabled={busy || proposal.status !== 'AWAITING_APPROVAL'} onClick={() => void run(async () => {
          setProposal(await api(`/proposals/${proposal.id}/decision`, { digest: proposal.digest, decision: 'approve' })); await refresh();
        })}>Approve this exact change</button>
        <button disabled={busy || proposal.status !== 'AWAITING_APPROVAL'} onClick={() => void run(async () => {
          setProposal(await api(`/proposals/${proposal.id}/decision`, { digest: proposal.digest, decision: 'reject' })); await refresh();
        })}>Reject</button>
        <button disabled={busy || proposal.status !== 'APPROVED'} onClick={() => void run(async () => {
          setProposal(await api(`/proposals/${proposal.id}/execute`, { digest: proposal.digest })); await refresh();
        })}>{proposal.binding.management === 'terraform' ? 'Create approved pull request' : 'Apply approved LocalStack change'}</button>
      </div>
      {proposal.error && <p role="alert" className="error">{proposal.error}</p>}
      {proposal.result?.url && <p><a href={proposal.result.url} target="_blank" rel="noreferrer">Review GitHub pull request</a> · Infrastructure changes after customer merge and apply.</p>}
      {proposal.result?.after && <p><strong>LocalStack verified:</strong> {proposal.result.after.instance_type} · {proposal.result.after.state}<br />{proposal.result.verified_at}</p>}
      <p className="note">Rollback: {proposal.rollback}</p>
      {proposal.status === 'APPLIED' && <button disabled={busy} onClick={() => void run(async () => {
        setProposal(await api(`/proposals/${proposal.id}/rollback?mode=${mode}`, {})); await refresh();
      })}>Prepare inverse change for review</button>}
      {proposal.status === 'RECOVERY_REQUIRED' && <button disabled={busy} onClick={() => void run(async () => {
        setProposal(await api(`/proposals/${proposal.id}/acknowledge-recovery`, { digest: proposal.digest })); await refresh();
      })}>Read live state and acknowledge failure</button>}
    </article>}
    {history.length > 0 && <details><summary>Saved proposals ({history.length})</summary><ul>{history.map(item => <li key={item.id}>
      <button disabled={busy} onClick={() => setProposal(item)}>{item.binding.resource_id} · {item.status} · {item.id.slice(0, 8)}</button>
    </li>)}</ul></details>}
    {audit.length > 0 && <details><summary>Audit history</summary><ol>{audit.map(item => <li key={item.sequence}>
      <time>{item.timestamp}</time> · {item.event}<pre>{JSON.stringify(item.details, null, 2)}</pre>
    </li>)}</ol></details>}
  </section>;
}
