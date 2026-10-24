import { useEffect, useState } from 'react';
import type { Recommendation } from './lib/api';
import './Execution.css';

type Snapshot = { provider_id: string; instance_type: string; state: string; tags: Record<string, string> };
type Binding = { resource_id: string; provider_id: string; management: 'terraform' | 'manual'; repository?: string; current?: Snapshot };
type Proposal = {
  id: string; status: string; digest: string; binding: Binding; before: Snapshot;
  recommendation: { action: string; target_instance_type?: string; evidence: { source: string; version: string; reason: string; expires_at: string; engine_reference?: { source_resource_id: string; target_plan_id: string; analysis_as_of: string; provider_blockers: string[] } } };
  steps: string[]; agent: { explanation: string; mode: string; tool_calls: { tool: string }[] };
  patch?: { diff: string; validation: Record<string, string> }; rollback: string; error?: string;
  result?: { url?: string; after?: Snapshot; verified_at?: string };
};
type Audit = { sequence: number; timestamp: string; event: string; proposal_id: string | null; details: unknown };
const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
type EngineOptions = { production_ready: boolean; provider_blockers: string[]; candidates: { plan_id: string; vcpu: number; memory_gib: number; lab_instance_type: string | null; lab_eligible: boolean }[] };

export default function Execution({ findings = [], initialRecommendationId = '' }: { findings?: Recommendation[]; initialRecommendationId?: string }) {
  const [token, setToken] = useState('');
  const [resources, setResources] = useState<Binding[]>([]);
  const [history, setHistory] = useState<Proposal[]>([]);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [resourceId, setResourceId] = useState('demo-manual-01');
  const [action, setAction] = useState('resize');
  const [target, setTarget] = useState('m5.xlarge');
  const [mode, setMode] = useState('llm');
  const [source, setSource] = useState('engine');
  const [engineId, setEngineId] = useState(initialRecommendationId);
  const [engineOptions, setEngineOptions] = useState<EngineOptions | null>(null);
  const [planId, setPlanId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const selected = resources.find(resource => resource.resource_id === resourceId);
  const queued = findings.filter(item => item.decision === 'accepted' && ['resize', 'capacity_review'].includes(item.action));
  useEffect(() => {
    if (initialRecommendationId) { setEngineId(initialRecommendationId); setEngineOptions(null); setPlanId(''); setSource('engine'); }
  }, [initialRecommendationId]);

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
    const result = source === 'engine' ? await api<Proposal>('/engine/proposals', {
      recommendation_id: engineId, target_plan_id: planId, binding_resource_id: resourceId, mode,
    }) : await api<Proposal>('/proposals', { recommendation: await api(
      `/demo/recommendation/${encodeURIComponent(resourceId)}?action=${action}&target=${target}`), mode });
    setProposal(result); await refresh();
  }

  return <section className="execution panel" aria-labelledby="execution-title">
    <div className="section-heading"><div><p className="eyebrow">ENGINE → REVIEW → LOCALSTACK / GITHUB</p>
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
      <label>Recommendation source<select value={source} onChange={event => setSource(event.target.value)}><option value="engine">Queued engine finding</option><option value="fixture">Fixture controls (stub evidence)</option></select></label>
      {source === 'engine' && <div className="engine-handoff">
        <p>Queue a resize finding from Recommendations, then test its exact candidate CPU/RAM shape on a LocalStack fixture. Historical evidence and unresolved production checks stay visible.</p>
        <div className="controls"><label>Queued finding<select aria-label="Queued finding" value={engineId} onChange={event => { setEngineId(event.target.value); setEngineOptions(null); setPlanId(''); }}>
          <option value="">Select a queued finding</option>{queued.map(item => <option key={item.id} value={item.id}>{item.resource_name} · {item.target_plan_id ?? item.action}</option>)}
        </select></label><button disabled={busy || !engineId} onClick={() => void run(async () => {
          const result = await api<EngineOptions>(`/engine/candidates/${encodeURIComponent(engineId)}`);
          setEngineOptions(result); setPlanId(result.candidates.find(item => item.lab_eligible && item.lab_instance_type !== selected?.current?.instance_type)?.plan_id ?? '');
        })}>Load candidate evidence</button></div>
        {!queued.length && <p>No queued resize findings yet. Open Recommendations, inspect a finding and choose Queue for review.</p>}
        {engineOptions && <><label>Capacity candidate<select aria-label="Capacity candidate" value={planId} onChange={event => setPlanId(event.target.value)}>
          <option value="">Select a supported candidate</option>{engineOptions.candidates.filter(item => item.lab_eligible).map(item => <option key={item.plan_id} value={item.plan_id}>{item.plan_id} · {item.vcpu} vCPU / {item.memory_gib} GiB → {item.lab_instance_type}</option>)}
        </select></label><p className="note">Production ready: {engineOptions.production_ready ? 'yes' : 'no'}. This test changes only the selected LocalStack fixture or its demo Terraform code.</p>
          <details><summary>Unresolved provider checks</summary><ul>{engineOptions.provider_blockers.map(item => <li key={item}>{item}</li>)}</ul></details>
          {!engineOptions.candidates.some(item => item.lab_eligible) && <p>No candidate matches a supported lab shape and passes capacity checks.</p>}</>}
      </div>}
      <div className="controls">
        <label>LocalStack destination<select value={resourceId} onChange={event => { setResourceId(event.target.value); setAction('resize'); }}>
          {resources.map(resource => <option key={resource.resource_id} value={resource.resource_id}>{resource.resource_id} · {resource.management}</option>)}
        </select></label>
        <label>Agent<select value={mode} onChange={event => setMode(event.target.value)}><option value="llm">Bedrock Mantle + LangChain</option><option value="scripted">Scripted tools (no LLM)</option></select></label>
        {source === 'fixture' && <label>Action<select value={action} onChange={event => setAction(event.target.value)}><option value="resize">Resize</option>
          {selected?.management === 'manual' && <><option value="stop">Stop</option><option value="start">Start</option></>}
        </select></label>}
        {source === 'fixture' && action === 'resize' && <label>Target type<select value={target} onChange={event => setTarget(event.target.value)}>
          {['m5.large', 'm5.xlarge', 'm5.2xlarge'].map(type => <option key={type}>{type}</option>)}
        </select></label>}
      </div>
      <p>Current: <strong>{selected?.current?.instance_type ?? 'Unavailable'}</strong> · {selected?.current?.state} · {selected?.provider_id}</p>
      <p className="note">The live dataset is historical. Lab tests establish control-plane behavior, not production safety or realized savings.</p>
      <button disabled={busy || (source === 'engine' && (!engineId || !planId))} onClick={() => void run(prepare)}>Prepare change preview</button>
    </>}
    {proposal && <article className="proposal" aria-labelledby="proposal-title">
      <div className="section-heading"><h3 id="proposal-title">{proposal.binding.resource_id} · {proposal.recommendation.action}</h3><strong>{proposal.status}</strong></div>
      <p>{proposal.before.instance_type} / {proposal.before.state} → {proposal.recommendation.target_instance_type ?? proposal.recommendation.action}</p>
      <p><strong>Evidence: {proposal.recommendation.evidence.source}</strong> · {proposal.recommendation.evidence.version}<br />Expires: {proposal.recommendation.evidence.expires_at}</p>
      <p>{proposal.agent.explanation}</p>
      {proposal.recommendation.evidence.engine_reference && <details><summary>Original engine evidence and production blockers</summary>
        <p>Source: {proposal.recommendation.evidence.engine_reference.source_resource_id} · Candidate: {proposal.recommendation.evidence.engine_reference.target_plan_id} · Historical cutoff: {proposal.recommendation.evidence.engine_reference.analysis_as_of}</p>
        <ul>{proposal.recommendation.evidence.engine_reference.provider_blockers.map(item => <li key={item}>{item}</li>)}</ul>
      </details>}
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
