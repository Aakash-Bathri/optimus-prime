import { useEffect, useRef, useState } from 'react';
import { currency, Badge, human } from './components';
import { post } from './lib/api';
import type { Recommendation } from './lib/api';
import './Monitoring.css';

interface Scenario {
  billing_mode: string;
  days: number; shutdown: boolean; shutdown_environment: string; stop_hour: number; start_hour: number;
  weekdays: number[]; timezone: string; demand_growth_pct: number; budget: number | null;
  cost_increase_pct: number; capacity_pct: number; watts_per_vcpu: number; pue: number; carbon_kg_per_kwh: number;
}
interface Projection {
  as_of: string; baseline_total: number; scenario_total: number; conditional_savings: number;
  resource_count: number; unknown_price_count: number; selected_resources: { id: string; name: string; vcpu: number }[];
  points: { date: string; baseline: number; scenario: number; lower: number; upper: number }[];
  usage: { allocated_vcpu_hours: number; avoided_vcpu_hours: number; estimated_busy_vcpu_hours: number };
  sustainability: { baseline_kwh: number; avoided_kwh: number; avoided_kg_co2e: number };
  alerts: { id: string; category: string; title: string; severity: string; explanation: string; timestamp: string; resource_name?: string }[];
  assumptions: string[];
}
const defaults: Scenario = { billing_mode: 'commitment', days: 30, shutdown: true, shutdown_environment: 'development', stop_hour: 20, start_hour: 8, weekdays: [0, 1, 2, 3, 4, 5, 6], timezone: 'Asia/Kolkata', demand_growth_pct: 0, budget: null, cost_increase_pct: 5, capacity_pct: 80, watts_per_vcpu: 12, pue: 1.4, carbon_kg_per_kwh: 0.7 };
const apiBase = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export default function Monitoring({ query, findings }: { query: string; findings: Recommendation[] }) {
  const [draft, setDraft] = useState<Scenario>(defaults);
  const [applied, setApplied] = useState<Scenario>(defaults);
  const [question, setQuestion] = useState('');
  const [interpreting, setInterpreting] = useState(false);
  const [data, setData] = useState<Projection | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [evaluated, setEvaluated] = useState('');
  const [category, setCategory] = useState('all');
  const [showAllAlerts, setShowAllAlerts] = useState(false);
  const [finding, setFinding] = useState('');
  const [explanation, setExplanation] = useState<{ explanation: string; source: string; model?: string; reason?: string } | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [exporting, setExporting] = useState(false);
  const context = useRef('');
  const draftContext = useRef('');
  draftContext.current = `${query}:${JSON.stringify(draft)}:${question}`;
  context.current = `${query}:${JSON.stringify(applied)}:${finding}`;
  const update = <K extends keyof Scenario>(key: K, value: Scenario[K]) => setDraft(previous => ({ ...previous, [key]: value }));

  useEffect(() => { setExplanation(null); setFinding(''); }, [query, applied]);
  useEffect(() => {
    const controller = new AbortController(); setBusy(true); setError(''); setData(null);
    fetch(`${apiBase}/api/monitoring/evaluate?${query}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(applied), signal: controller.signal })
      .then(async response => { const payload = await response.json(); if (!response.ok) throw new Error(payload.message ?? (typeof payload.detail === 'string' ? payload.detail : 'Check scenario inputs and try again')); return payload as Projection; })
      .then(result => { if (!controller.signal.aborted) { setData(result); setEvaluated(new Date().toLocaleTimeString()); } })
      .catch((cause: unknown) => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Evaluation failed'); })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [query, applied, refresh]);
  useEffect(() => { const interval = window.setInterval(() => setRefresh(value => value + 1), 60000); return () => window.clearInterval(interval); }, []);
  const explain = async () => {
    const requestedContext = context.current;
    setExplaining(true); setExplanation(null); setError('');
    try {
      const result = await post<{ explanation: string; source: string; model?: string; reason?: string }>(`/monitoring/explain?${query}`, { scenario: applied, recommendation_id: finding || null });
      if (context.current === requestedContext) setExplanation(result);
    }
    catch (cause) { if (context.current === requestedContext) setError(cause instanceof Error ? cause.message : 'Explanation failed'); }
    finally { setExplaining(false); }
  };
  const download = async (format: string) => {
    setExporting(true); setError('');
    try {
      const response = await fetch(`${apiBase}/api/monitoring/export?${query}&format=${format}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(applied) });
      if (!response.ok) throw new Error('Unable to export report');
      const url = URL.createObjectURL(await response.blob()); const anchor = document.createElement('a'); anchor.href = url;
      anchor.download = `cloudpilot-optimization.${format === 'markdown' ? 'md' : format === 'terraform' ? 'tf' : 'json'}`;
      anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Export failed'); }
    finally { setExporting(false); }
  };
  const dirty = JSON.stringify(draft) !== JSON.stringify(applied);
  return <div className="monitoring-workspace">
    <form className="panel" onSubmit={async event => {
      event.preventDefault(); const requestedContext = draftContext.current; setInterpreting(true); setError('');
      try {
        const result = await post<{ scenario: Scenario }>(`/monitoring/what-if?${query}`, { question, scenario: draft });
        if (draftContext.current === requestedContext) { setDraft(result.scenario); setExplanation(null); }
      } catch (cause) { if (draftContext.current === requestedContext) setError(cause instanceof Error ? cause.message : 'Could not interpret question'); }
      finally { setInterpreting(false); }
    }}><div className="panel-heading"><div><h3>Ask a what-if question</h3><p>The LLM fills the inputs below. Review them, then run the scenario.</p></div><button className="primary-button" disabled={interpreting || busy}>{interpreting ? 'Interpreting…' : 'Fill scenario with AI'}</button></div><label className="what-if-question">Your question<input required minLength={5} maxLength={2000} value={question} onChange={event => setQuestion(event.target.value)} placeholder="What if staging VMs shut down from 8 PM to 8 AM on weekdays?"/></label></form>
    <form className="panel" onSubmit={event => { event.preventDefault(); setApplied({ ...draft }); }}>
      <div className="panel-heading"><div><h3>Scenario inputs</h3><p>Compare a baseline with a shutdown schedule and demand growth. {evaluated && `Last evaluated ${evaluated}`}</p></div><button className="primary-button" disabled={busy}>Run scenario</button></div>
      <div className="scenario-fields">
        <label>Billing assumption<select value={draft.billing_mode} onChange={e => update('billing_mode', e.target.value)}><option value="commitment">Dataset: quarterly commitment (no stop savings)</option><option value="hourly">Hypothetical: hourly prorated compute</option></select></label>
        <label>Forecast horizon<select value={draft.days} onChange={e => update('days', Number(e.target.value))}>{[30, 60, 90].map(days => <option key={days} value={days}>{days} days</option>)}</select></label>
        <label>Schedule environment<select value={draft.shutdown_environment} onChange={e => update('shutdown_environment', e.target.value)}>{['development', 'staging', 'production'].map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Stop at (local hour)<input type="number" min="0" max="23" required value={draft.stop_hour} onChange={e => update('stop_hour', Number(e.target.value))}/></label>
        <label>Restart at (local hour)<input type="number" min="0" max="23" required value={draft.start_hour} onChange={e => update('start_hour', Number(e.target.value))}/></label>
        <label>Timezone<input required value={draft.timezone} onChange={e => update('timezone', e.target.value)}/></label>
        <label>Demand growth by horizon (%)<input type="number" min="-50" max="100" required value={draft.demand_growth_pct} onChange={e => update('demand_growth_pct', Number(e.target.value))}/></label>
        <label>Budget for entire horizon (INR)<input type="number" min="1" max="1000000000000" placeholder="Optional" value={draft.budget ?? ''} onChange={e => update('budget', e.target.value ? Number(e.target.value) : null)}/></label>
        <label className="checkbox-label"><input type="checkbox" checked={draft.shutdown} onChange={e => update('shutdown', e.target.checked)}/>Enable shutdown scenario</label>
      </div><fieldset className="schedule-days"><legend>Shutdown starts on</legend>{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, index) => <label key={day}><input type="checkbox" checked={draft.weekdays.includes(index)} onChange={e => update('weekdays', e.target.checked ? [...draft.weekdays, index].sort() : draft.weekdays.filter(value => value !== index))}/>{day}</label>)}</fieldset>
      <details className="monitoring-settings"><summary>Alert thresholds & sustainability assumptions</summary><div className="scenario-fields">{([
        ['cost_increase_pct', 'Cost increase alert (%)', 0, 1000, 1], ['capacity_pct', 'Capacity p95 threshold (%)', 1, 100, 1],
        ['watts_per_vcpu', 'Assumed watts / vCPU', 0.1, 1000, 0.1], ['pue', 'Power usage effectiveness', 1, 3, 0.1], ['carbon_kg_per_kwh', 'Assumed kg CO2e / kWh', 0, 2, 0.01],
      ] as const).map(([key, title, min, max, step]) => <label key={key}>{title}<input required type="number" min={min} max={max} step={step} value={draft[key]} onChange={e => update(key, Number(e.target.value))}/></label>)}</div></details>
      {dirty && <p className="warning-text">Inputs changed. Run the scenario to update results, explanations and exports.</p>}
    </form>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {busy && <p role="status">Evaluating historical evidence…</p>}
    {data && <>
      <div className="notice"><p>Evidence cutoff: <strong>{data.as_of}</strong> · Forecast: {data.points[0]?.date} to {data.points.at(-1)?.date} · {data.resource_count} scoped resources · {data.unknown_price_count} unpriced. Historical synthetic data; forecasts do not represent current invoices.</p></div>
      <div className="monitoring-stats">
        <Metric label={`${applied.days}-day baseline`} value={currency(data.baseline_total)} detail="Trend extrapolation · known charges"/>
        <Metric label="Scenario cost" value={currency(data.scenario_total)} detail={`${data.selected_resources.length} running VMs selected`}/>
        <Metric label="Conditional cost avoidance" value={currency(data.conditional_savings)} detail={applied.billing_mode === 'hourly' ? 'Hypothetical hourly billing' : 'Commitments remain charged'}/>
        <Metric label="Alerts to review" value={String(data.alerts.length)} detail="Usage · cost · capacity · budget"/>
      </div>
      <section className="panel"><div className="panel-heading"><div><h3>Cost forecast & scenario</h3><p>Baseline, shutdown scenario and sensitivity range · INR per day</p></div><Badge>{applied.days} days</Badge></div><ForecastChart points={data.points}/></section>
      {<section className="panel"><div className="panel-heading"><div><h3>Usage & capacity outlook</h3><p>Allocated capacity and a demand-scaled estimate from historical mean CPU.</p></div></div><div className="monitoring-stats"><Metric label="Allocated vCPU-hours" value={data.usage.allocated_vcpu_hours.toLocaleString()} detail="Running VM capacity × horizon"/><Metric label="Estimated busy vCPU-hours" value={data.usage.estimated_busy_vcpu_hours.toLocaleString()} detail="Historical average · demand scaled"/><Metric label="Avoided vCPU-hours" value={data.usage.avoided_vcpu_hours.toLocaleString()} detail="Shutdown schedule capacity avoidance"/></div></section>}
      <section className="panel"><div className="panel-heading"><div><h3>Sustainability impact</h3><p>Scenario estimates using the wattage, PUE and grid intensity above.</p></div></div><div className="monitoring-stats"><Metric label="Baseline energy" value={`${data.sustainability.baseline_kwh.toLocaleString()} kWh`} detail="Allocated compute energy model"/><Metric label="Potential energy reduction" value={`${data.sustainability.avoided_kwh.toLocaleString()} kWh`} detail="Avoided capacity × assumed power"/><Metric label="Potential carbon reduction" value={`${data.sustainability.avoided_kg_co2e.toLocaleString()} kg CO2e`} detail="Assumed intensity · unverified"/></div></section>
      <section className="panel"><div className="panel-heading"><div><h3>Monitoring & alerts</h3><p>Findings from imported evidence, evaluated against scenario thresholds.</p></div><select aria-label="Alert category" value={category} onChange={e => { setCategory(e.target.value); setShowAllAlerts(false); }}><option value="all">All alerts</option>{['usage_anomaly', 'cost_increase', 'capacity_pressure', 'budget_overrun', 'data_quality'].map(value => <option key={value} value={value}>{human(value)}</option>)}</select></div><div className="monitoring-alerts">{data.alerts.filter(alert => category === 'all' || alert.category === category).slice(0, showAllAlerts ? undefined : 8).map(alert => <article key={alert.id}><div><Badge tone={alert.severity === 'critical' ? 'red' : 'amber'}>{alert.severity}</Badge><span>{human(alert.category)}</span></div><h4>{alert.title}</h4>{alert.resource_name && <small>{alert.resource_name}</small>}<p>{alert.explanation}</p><small>Evidence timestamp: {alert.timestamp}</small></article>)}{!data.alerts.some(alert => category === 'all' || alert.category === category) && <p className="muted">No alerts match this category and scope.</p>}</div>{data.alerts.filter(alert => category === 'all' || alert.category === category).length > 8 && <button className="text-button" onClick={() => setShowAllAlerts(value => !value)}>{showAllAlerts ? 'Show fewer alerts' : 'Show all matching alerts'}</button>}</section>
      <section className="panel"><div className="panel-heading"><div><h3>Explain the recommendation</h3><p>The LLM uses evidence and assumptions only. An evidence summary is shown if the LLM is unavailable.</p></div><button className="secondary-button" disabled={explaining || dirty || busy} onClick={() => void explain()}>{explaining ? 'Asking the LLM…' : 'Explain with AI'}</button></div><label className="explanation-select">Evidence to explain<select value={finding} onChange={e => { setFinding(e.target.value); setExplanation(null); }}><option value="">Current shutdown scenario</option>{findings.filter(item => ['recommendation', 'blocked'].includes(item.outcome)).map(item => <option key={item.id} value={item.id}>{item.resource_name} · {item.title}</option>)}</select></label>{explanation && <div className="plain-explanation"><Badge>{explanation.source !== 'rules' ? `LLM · ${explanation.model}` : 'Rule-based explanation'}</Badge><p>{explanation.explanation}</p>{explanation.reason && <small>{explanation.reason}</small>}</div>}</section>
      <section className="panel"><div className="panel-heading"><div><h3>Export recommendations</h3><p>Includes scoped findings, estimates, blockers and assumptions.</p></div><div className="button-row">{['markdown', 'json'].map(format => <button key={format} className="secondary-button" disabled={exporting || dirty || busy} onClick={() => void download(format)}>{format === 'markdown' ? 'Report (.md)' : format === 'terraform' ? 'IaC handoff (.tf)' : 'JSON'}</button>)}</div></div></section>
      <details className="panel monitoring-assumptions"><summary>Methodology & limitations</summary><ul>{data.assumptions.map(item => <li key={item}>{item}</li>)}</ul></details>
    </>}
  </div>;
}
function Metric({ label, value, detail }: { label: string; value: string; detail: string }) { return <div className="monitoring-metric"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>; }
function ForecastChart({ points }: { points: Projection['points'] }) {
  const max = Math.max(1, ...points.map(p => p.upper));
  const x = (i: number) => 70 + i / Math.max(1, points.length - 1) * 810;
  const y = (value: number) => 230 - value / max * 200;
  const line = (key: 'baseline' | 'scenario') => points.map((p, i) => `${x(i)},${y(p[key])}`).join(' ');
  const area = [...points.map((p, i) => `${x(i)},${y(p.upper)}`), ...points.map((p, i) => `${x(i)},${y(p.lower)}`).reverse()].join(' ');
  return <><svg className="forecast-chart" viewBox="0 0 920 280" role="img" aria-label="Daily cost forecast: baseline in blue, shutdown scenario in green, sensitivity range shaded">{[0, .25, .5, .75, 1].map(tick => <g key={tick}><line x1="70" x2="880" y1={y(max * tick)} y2={y(max * tick)} stroke="#e5e9f0"/><text x="60" y={y(max * tick) + 4} textAnchor="end">{Math.round(max * tick).toLocaleString()}</text></g>)}<polygon points={area} fill="#e4eaff"/><polyline points={line('baseline')} fill="none" stroke="#5267db" strokeWidth="3"/><polyline points={line('scenario')} fill="none" stroke="#079875" strokeWidth="3"/><text x="70" y="265">{points[0]?.date}</text><text x="880" y="265" textAnchor="end">{points.at(-1)?.date}</text></svg><div className="forecast-legend"><span>🔵 Baseline</span><span>🟢 Shutdown scenario</span><span>Shaded: sensitivity range</span></div><details><summary>View daily forecast table</summary><div className="table-scroll"><table><thead><tr><th>Date</th><th>Baseline</th><th>Scenario</th><th>Lower</th><th>Upper</th></tr></thead><tbody>{points.map(p => <tr key={p.date}><td>{p.date}</td><td>{currency(p.baseline)}</td><td>{currency(p.scenario)}</td><td>{currency(p.lower)}</td><td>{currency(p.upper)}</td></tr>)}</tbody></table></div></details></>;
}
