import { useEffect, useRef, useState } from 'react';
import Execution, { ExecutionSetup } from './Execution';
import Monitoring from './Monitoring';
import type { ReactNode } from 'react';
import { all, exportUrl, get, patch, post } from './lib/api';
import type { Candidate, DataSources, Dataset, Decision, Expenses, Plan, Recommendation, RecommendationDetail, Resource, ResourceDetail, Series, Summary } from './lib/api';
import { Badge, currency, date, Empty, human, Icon, percent, Telemetry } from './components';
import { CostExplorer, ExpenseChart, periodLabel, typeName } from './expenses';
import type { CostScope } from './expenses';
import FindingExplanation from './FindingExplanation';

type View = 'monitoring' | 'execution' | 'home' | 'recommendations' | 'resources' | 'cost-explorer' | 'data-sources';
type Selection = { kind: 'resource' | 'recommendation'; id: string };
interface Bundle { dataset: Dataset; summary: Summary; resources: Resource[]; recommendations: Recommendation[]; plan: Plan; sources: DataSources; expenses: Expenses }
const executionEnabled = import.meta.env.VITE_EXECUTION_ENABLED !== 'false';
const navigation: { id: View; label: string; icon: string; section?: string }[] = [
  { id: 'home', label: 'Home', icon: 'home' },
  { id: 'recommendations', label: 'Recommendations', icon: 'recommendations' },
  { id: 'resources', label: 'Resources', icon: 'resources' },
  { id: 'cost-explorer', label: 'Cost Explorer', icon: 'chart', section: 'FINOPS' },
  { id: 'monitoring', label: 'What-if & alerts', icon: 'chart' },
  ...(executionEnabled ? [{ id: 'execution' as const, label: 'Execution lab', icon: 'shield' }] : []),
  { id: 'data-sources', label: 'Data sources', icon: 'database', section: 'SYSTEM' },
];
const descriptions: Record<View, string> = {
  monitoring: 'Forecast cloud cost and usage, simulate changes, and review alerts and sustainability impact.',
  execution: 'Test queued capacity findings in LocalStack or prepare a reviewed Terraform pull request.',
  home: 'An overview of your organization’s cloud expenses and savings opportunities.',
  recommendations: 'Explore opportunities, review the evidence and manage your next steps.',
  resources: 'Your complete inventory, with costs, utilization and resource details.',
  'cost-explorer': 'Understand your expenses and discover the resources behind every total.',
  'data-sources': 'Explore imported data and classify the resources in your organization.',
};
const emptyFilters = { environment: '', region: '', team: '', resource_type: '', data_source: '', search: '' };

function routeView(): View {
  const value = window.location.hash.split('?')[0].replace('#/', '') as View;
  return navigation.some(item => item.id === value) ? value : 'home';
}
function routeScope(): CostScope | null {
  const params = new URLSearchParams(window.location.hash.split('?')[1] ?? '');
  const start = params.get('start'), end = params.get('end');
  const breakdown = params.get('breakdown');
  return routeView() === 'resources' && start && end && breakdown && ['data_source', 'resource_type', 'environment', 'region', 'team'].includes(breakdown)
    ? { start, end, breakdown: breakdown as CostScope['breakdown'], group: params.get('group') ?? undefined, label: params.get('label') ?? 'All sources' } : null;
}
function findingBadge(item: Recommendation) {
  if (item.decision === 'accepted') return <Badge tone="green">{item.review_only ? 'Queued for review' : 'In cost plan'}</Badge>;
  if (item.decision === 'rejected') return <Badge>Dismissed</Badge>;
  if (item.outcome === 'insufficient_data') return <Badge tone="red">Insufficient data</Badge>;
  if (item.outcome === 'no_action') return <Badge>No change</Badge>;
  if (item.outcome === 'unsupported') return <Badge>Not evaluated</Badge>;
  return <Badge tone={item.ready ? 'green' : 'amber'}>{item.ready ? 'Eligible' : 'Needs verification'}</Badge>;
}

function Stat({ label, value, detail, foot, icon, green = false }: { label: string; value: string; detail: string; foot: string; icon: string; green?: boolean }) {
  return <section className={`stat-card ${green ? 'opportunity-card' : ''}`}><div className="stat-label">{label}<Icon name={icon} size={19}/></div><div className="stat-value">{value}</div><p>{detail}</p><div className="stat-foot">{foot}</div></section>;
}

function Home({ data, query, onView, onSelect, onResources }: { data: Bundle; query: string; onView: (view: View) => void; onSelect: (selection: Selection) => void; onResources: (scope: CostScope) => void }) {
  const { summary, expenses } = data;
  const highest = expenses.resources.filter(item => item.amount !== null).slice(0, 5);
  const maximum = Math.max(1, ...highest.map(item => Number(item.amount)));
  const recentMonths = summary.billing_history.slice(-2);
  const growth = recentMonths.length === 2 && Number(recentMonths[0].amount) ? (Number(recentMonths[1].amount) / Number(recentMonths[0].amount) - 1) * 100 : null;
  return <>
    <div className="home-stats stats-grid">
      <Stat label="Organization expenses" value={currency(expenses.total)} icon="coin" detail={periodLabel(expenses.start, expenses.end)} foot={growth === null ? 'Latest available billing month' : `${growth.toFixed(1)}% increase from previous billing month`}/>
      <Stat label="Possible monthly savings" value={currency(summary.conditional_monthly_savings)} icon="recommendations" detail="Conditional estimate · verification required" foot={`${summary.recommendation_count} findings to investigate`} green/>
      <Stat label="Resources" value={String(summary.resource_count)} icon="resources" detail={`${summary.vm_count} virtual machines · ${summary.resource_count - summary.vm_count} other resources`} foot={`${summary.unknown_price_count} resources have unpriced charges`}/>
      <Stat label="Data sources" value={String(data.sources.items.length)} icon="database" detail="Utho benchmark" foot="Imported local dataset · synthetic billing"/>
    </div>
    <div className="home-columns">
      <section className="panel organization-expenses"><div className="panel-heading"><div><h3>Organization expenses</h3><p>Six months of synthetic billing</p></div><button className="text-button" onClick={() => onView('cost-explorer')}>Cost Explorer<Icon name="arrow" size={15}/></button></div><HomeHistory query={new URLSearchParams({ ...Object.fromEntries(new URLSearchParams(query)), start: expenses.available_start, end: expenses.available_end, granularity: 'month', breakdown: 'resource_type' }).toString()} onResources={onResources}/></section>
      <section className="panel top-resources"><div className="panel-heading"><div><h3>Top resource expenses</h3><p>{new Intl.DateTimeFormat('en-IN', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(expenses.end))}</p></div><Icon name="resources" size={18}/></div>{highest.map((item, index) => { const resource = data.resources.find(value => value.id === item.resource_id); return resource && <div className="top-resource" key={item.resource_id}><span className="rank">{index + 1}</span><div><div><button className="resource-link" onClick={() => onSelect({ kind: 'resource', id: resource.id })}>{resource.name}</button><strong>{currency(item.amount)}</strong></div><small>{resource.region} · {typeName(resource.type)}</small><div className="bar-track"><div style={{ width: `${Number(item.amount) / maximum * 100}%` }}/></div></div></div>; })}{!highest.length && <Empty title="No priced resources" text="Clear the filters to see top resource expenses."/>}<button className="text-button panel-bottom-link" onClick={() => onResources({ start: expenses.start, end: expenses.end, breakdown: 'data_source', label: 'All sources' })}>See all resources<Icon name="arrow" size={15}/></button></section>
    </div>
    <section className="panel home-recommendations"><div className="panel-heading"><div><h3>Recommendations</h3><p>Start with the largest opportunities in your organization.</p></div><button className="text-button" onClick={() => onView('recommendations')}>See all recommendations<Icon name="arrow" size={15}/></button></div><div className="recommendation-cards">{['resize', 'idle_review', 'orphan_review'].map(action => <RecommendationCard key={action} action={action} items={data.recommendations} onOpen={id => onSelect({ kind: 'recommendation', id })} onView={() => onView('recommendations')}/>)}</div></section>
    <div className="data-note"><Icon name="info" size={16}/><p>Synthetic billing · Known charges only. GPU and public IP prices are unavailable.</p><button className="text-button" onClick={() => onView('data-sources')}>View data sources<Icon name="arrow" size={14}/></button></div>
  </>;
}

function HomeHistory({ query, onResources }: { query: string; onResources: (scope: CostScope) => void }) {
  const [history, setHistory] = useState<Expenses | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); setError(false); setHistory(null);
    const params = new URLSearchParams(query);
    get<Expenses>(`/expenses?${params}`, controller.signal).then(result => { if (!controller.signal.aborted) setHistory(result); }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [query]);
  if (error) return <Empty title="Unable to load expense history" text="Use the refresh button to try again."/>;
  return history ? <ExpenseChart compact expenses={history} onSelect={(point, group) => onResources({ start: point.start, end: point.end, breakdown: 'resource_type', group, label: group ? typeName(group) : 'All resources' })}/> : <div className="chart-loading"><span className="spinner"/></div>;
}

function RecommendationCard({ action, items, onOpen, onView }: { action: string; items: Recommendation[]; onOpen: (id: string) => void; onView: () => void }) {
  const titles: Record<string, string> = { resize: 'Rightsizing opportunities', capacity_review: 'Capacity review', idle_review: 'Idle resources', orphan_review: 'Orphaned resources' };
  const descriptions: Record<string, string> = { resize: 'Match compute capacity to observed workload demand.', capacity_review: 'Investigate resources that need more capacity.', idle_review: 'Investigate sustained low utilization before changing resources.', orphan_review: 'Review unattached resources and their dependencies.' };
  const matches = items.filter(item => item.action === action && item.decision !== 'rejected');
  const savings = matches.reduce((sum, item) => sum + Number(item.conditional_monthly_savings ?? item.modeled_monthly_savings ?? 0), 0);
  return <article className="recommendation-card"><div className="recommendation-card-heading"><h4>{titles[action]}</h4>{savings > 0 ? <strong>{currency(savings)}<small>/ month · conditional</small></strong> : <span className="count-tag">{matches.length} resources</span>}</div><Badge>{action === 'orphan_review' ? 'Storage / IPs' : 'Virtual machines'}</Badge><p>{descriptions[action]}</p><div className="recommendation-preview">{matches.slice(0, 3).map(item => <button key={item.id} onClick={() => onOpen(item.id)}><span>{item.resource_name}</span><span>{item.conditional_monthly_savings ? currency(item.conditional_monthly_savings) : 'Review'}<Icon name="chevron" size={12}/></span></button>)}</div>{!matches.length && <p className="muted">No findings in this view.</p>}<button className="text-button" onClick={onView}>See all {matches.length} items<Icon name="arrow" size={14}/></button></article>;
}

function ResourceList({ items, expenses, onOpen }: { items: Resource[]; expenses?: Expenses | null; onOpen: (id: string) => void }) {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [sort, setSort] = useState('cost');
  const amounts = new Map(expenses?.resources.map(item => [item.resource_id, item.amount]));
  const cost = (resource: Resource) => expenses ? amounts.get(resource.id) ?? null : resource.monthly_cost;
  const sorted = [...items].sort((a, b) => sort === 'name' ? a.name.localeCompare(b.name) : sort === 'region' ? a.region.localeCompare(b.region) : Number(cost(b) ?? -1) - Number(cost(a) ?? -1));
  const last = Math.max(0, Math.ceil(items.length / pageSize) - 1), current = Math.min(page, last);
  if (!items.length) return <section className="panel"><Empty title="No matching resources" text="Change the filters to explore another part of your organization. Unpriced resources remain in inventory but do not contribute to expense totals."/></section>;
  return <section className="panel resource-inventory"><div className="panel-heading"><div><h3>Resources <span className="count-tag">{items.length}</span></h3><p>{expenses ? `Selected billing period · ${periodLabel(expenses.start, expenses.end)}` : 'Inventory from your imported data source'}</p></div><label className="inline-label">Sort by<select aria-label="Sort resources" value={sort} onChange={event => { setSort(event.target.value); setPage(0); }}><option value="cost">Highest expense</option><option value="name">Resource name</option><option value="region">Region</option></select></label></div><div className="table-scroll"><table><thead><tr><th>Name / ID</th><th>Data source / type</th><th>Region / environment</th><th>Configuration</th><th>CPU / memory p95</th><th>{expenses ? 'Period expenses' : 'Monthly cost equivalent'}</th><th/></tr></thead><tbody>{sorted.slice(current * pageSize, (current + 1) * pageSize).map(resource => <tr key={resource.id}><td><button className="resource-link" onClick={() => onOpen(resource.id)}>{resource.name}</button><small className="mono">{resource.id} · {resource.team ?? 'Unassigned'}</small></td><td>Utho benchmark<small>{typeName(resource.type)}</small></td><td>{resource.region}<small className="capitalize">{resource.environment}</small></td><td>{resource.vcpu ? `${resource.vcpu} vCPU · ${resource.memory_gib} GiB` : resource.disk_gb ? `${resource.disk_gb} GB storage` : human(resource.status)}<small className="mono">{resource.current_plan_id ?? '—'}</small></td><td><span className={(resource.cpu_p95 ?? 0) > 80 ? 'danger-text' : ''}>{resource.cpu_p95 === null ? '—' : percent(resource.cpu_p95)}</span><span className="metric-separator"> / </span><span className={(resource.memory_p95 ?? 0) > 80 ? 'danger-text' : ''}>{resource.memory_p95 === null ? '—' : percent(resource.memory_p95)}</span><small>{resource.coverage !== null ? `${percent(resource.coverage * 100)} coverage` : 'No VM telemetry'}</small></td><td><strong>{currency(cost(resource))}</strong><small>{cost(resource) === null ? 'Pricing unavailable' : expenses ? 'Synthetic billing' : 'Quarterly equivalent + storage'}</small></td><td><button className="icon-button" aria-label={`Open ${resource.name}`} onClick={() => onOpen(resource.id)}><Icon name="chevron" size={16}/></button></td></tr>)}</tbody></table></div><div className="pagination"><label className="inline-label">Rows per page<select aria-label="Resources per page" value={pageSize} onChange={event => { setPageSize(Number(event.target.value)); setPage(0); }}>{[10, 25, 50].map(value => <option key={value}>{value}</option>)}</select></label><span>{current * pageSize + 1}–{Math.min((current + 1) * pageSize, items.length)} of {items.length}</span><div><button className="secondary-button small-button" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous</button><button className="secondary-button small-button" disabled={current === last} onClick={() => setPage(current + 1)}>Next</button></div></div></section>;
}

function DataSourceView({ data, onClassify }: { data: Bundle; onClassify: (source: string, type?: string) => void }) {
  return <>{data.sources.items.map(source => <section key={source.id} className="panel source-panel"><div className="panel-heading"><div className="source-heading"><span className="source-mark">U</span><div><h3>{source.name}</h3><p>{source.kind} · {source.resource_count} resources</p></div></div><Badge tone="green">Imported</Badge></div><div className="source-info"><span><Icon name="calendar" size={15}/>Billing: {periodLabel(source.billing_start, source.billing_end)}</span><span><Icon name="clock" size={15}/>Imported {date(source.imported_at)}</span><button className="text-button" onClick={() => onClassify(source.id)}>View all resources<Icon name="arrow" size={15}/></button></div><h4 className="classification-title">Resource classification</h4><div className="classification-grid">{source.classifications.map(category => <button key={category.type} onClick={() => onClassify(source.id, category.type)}><span className="classification-icon"><Icon name={category.type === 'vm' ? 'resources' : category.type === 'block_volume' ? 'database' : category.type === 'gpu' ? 'overview' : 'cloud'} size={23}/></span><strong>{category.count}</strong><span>{typeName(category.type)}</span><Icon name="arrow" size={16}/></button>)}</div><div className="panel-heading feed-heading"><div><h3>Imported data feeds</h3><p>Each source file is classified by the information it contributes.</p></div></div><div className="table-scroll"><table><thead><tr><th>Data feed</th><th>Source file</th><th>Classification</th><th>Records</th><th>Status</th></tr></thead><tbody>{source.feeds.map(feed => <tr key={feed.file}><td><strong>{feed.name}</strong></td><td className="mono">{feed.file}</td><td>{feed.classification}</td><td>{feed.rows.toLocaleString('en-IN')}</td><td><Badge tone="green">Imported</Badge></td></tr>)}</tbody></table></div></section>)}<div className="data-note"><Icon name="info" size={17}/><p>This prototype uses a local synthetic benchmark. GPU and public IP tariffs are unavailable; daily costs are allocated from monthly billing.</p></div><details className="workspace-assumptions"><summary><Icon name="info" size={16}/>Data quality & assumptions<Icon name="down" size={14}/></summary><div><p>{data.dataset.missing_observation_rows.toLocaleString('en-IN')} missing telemetry rows · {data.dataset.invalid_observation_rows} invalid rows · {data.dataset.duplicate_event_rows} duplicate events deduplicated</p><ul>{data.dataset.assumptions.map(assumption => <li key={assumption}>{assumption}</li>)}</ul><p>Policy: {data.dataset.policy.cpu_limit_pct}% CPU / {data.dataset.policy.memory_limit_pct}% memory limit · {data.dataset.policy.minimum_coverage * 100}% coverage required · {data.dataset.policy.stress_multiplier}× stress replay</p></div></details></>;
}

export default function App() {
  const [view, setView] = useState<View>(routeView);
  const [data, setData] = useState<Bundle | null>(null);
  const [options, setOptions] = useState<Resource[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [labFinding, setLabFinding] = useState('');
  const [operatorToken, setOperatorToken] = useState('');
  const [executionManagement, setExecutionManagement] = useState<'manual' | 'terraform' | null>(() => { const saved = sessionStorage.getItem('cloudpilot-execution-management'); return saved === 'manual' || saved === 'terraform' ? saved : null; });
  const [registrationVersion, setRegistrationVersion] = useState(0);
  useEffect(() => {
    if (!executionEnabled) return;
    const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
    fetch(`${base}/api/local-operator-session`, { cache: 'no-store' })
      .then(response => response.ok ? response.json() : null)
      .then(session => { if (session?.token) setOperatorToken(session.token); }).catch(() => undefined);
  }, []);
  const [menuOpen, setMenuOpen] = useState(false);
  const [filters, setFilters] = useState(emptyFilters);
  const [searchInput, setSearchInput] = useState('');
  const [costScope, setCostScope] = useState<CostScope | null>(routeScope);
  const [resourceExpenses, setResourceExpenses] = useState<Expenses | null>(null);
  const [resourceCostError, setResourceCostError] = useState('');
  const [costLoading, setCostLoading] = useState(false);
  const [recommendationView, setRecommendationView] = useState('all');
  const [recommendationAction, setRecommendationAction] = useState('all');
  useEffect(() => { const timer = window.setTimeout(() => setFilters(previous => ({ ...previous, search: searchInput })), 250); return () => window.clearTimeout(timer); }, [searchInput]);
  useEffect(() => { const listener = () => { setView(routeView()); setCostScope(routeScope()); setMenuOpen(false); setSelection(null); }; window.addEventListener('hashchange', listener); return () => window.removeEventListener('hashchange', listener); }, []);
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === 'Escape') { setMenuOpen(false); } }; document.addEventListener('keydown', close); return () => document.removeEventListener('keydown', close); }, []);
  const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value)).toString();
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError(null);
    const suffix = query ? `?${query}` : '';
    Promise.all([get<Dataset>('/dataset', controller.signal), get<Summary>(`/summary${suffix}`, controller.signal), all<Resource>(`/resources${suffix}`, controller.signal), all<Recommendation>(`/recommendations${suffix}`, controller.signal), get<Plan>(`/optimization-plan${suffix}`, controller.signal), get<DataSources>('/data-sources', controller.signal), get<Expenses>(`/expenses${suffix}`, controller.signal)]).then(([dataset, summary, resources, recommendations, plan, sources, expenses]) => { if (!controller.signal.aborted) { setData({ dataset, summary, resources, recommendations, plan, sources, expenses }); setLoading(false); } }).catch((cause: unknown) => { if (!controller.signal.aborted) { setError(cause instanceof Error ? cause.message : 'Unable to load the workspace'); setLoading(false); } });
    return () => controller.abort();
  }, [query, refresh]);
  useEffect(() => { const controller = new AbortController(); all<Resource>('/resources', controller.signal).then(setOptions).catch(() => undefined); return () => controller.abort(); }, [refresh]);
  useEffect(() => {
    if (!costScope || view !== 'resources') { setResourceExpenses(null); return; }
    const controller = new AbortController(); setCostLoading(true); setResourceCostError(''); setResourceExpenses(null);
    const params = new URLSearchParams(query);
    params.set('start', costScope.start); params.set('end', costScope.end); params.set('breakdown', costScope.breakdown);
    if (costScope.group) params.set(costScope.breakdown, costScope.group);
    get<Expenses>(`/expenses?${params}`, controller.signal).then(result => { if (!controller.signal.aborted) { setResourceExpenses(result); setCostLoading(false); } }).catch((cause: unknown) => { if (!controller.signal.aborted) { setResourceCostError(cause instanceof Error ? cause.message : 'Unable to load resource expenses'); setCostLoading(false); } });
    return () => controller.abort();
  }, [query, refresh, costScope, view]);
  const navigate = (next: View) => { setSelection(null); setView(next); setCostScope(null); setMenuOpen(false); window.location.hash = `/${next}`; window.scrollTo({ top: 0, behavior: 'smooth' }); };
  const showResources = (scope: CostScope) => {
    const params = new URLSearchParams({ start: scope.start, end: scope.end, breakdown: scope.breakdown, label: scope.label });
    if (scope.group) params.set('group', scope.group);
    setCostScope(scope); setView('resources'); window.location.hash = `/resources?${params}`; window.scrollTo({ top: 0, behavior: 'smooth' });
  };
  const current = navigation.find(item => item.id === view)!;
  const resetFilters = () => { setFilters(emptyFilters); setSearchInput(''); };
  const expenseIds = new Set(resourceExpenses?.resources.map(item => item.resource_id));
  const resources = costScope ? data?.resources.filter(resource => expenseIds.has(resource.id)) ?? [] : data?.resources ?? [];
  return <div className="app-shell">
    <aside className={`sidebar ${menuOpen ? 'open' : ''}`}><a className="brand" href="#/home" onClick={event => { event.preventDefault(); navigate('home'); }}><span className="brand-mark"><Icon name="cloud" size={24}/></span>CloudPilot</a><div className="sidebar-organization"><Icon name="building" size={17}/><span>{data?.sources.organization.name ?? 'CloudPilot demo'}</span><Badge>Local</Badge></div><nav aria-label="Main navigation">{navigation.map(item => <div className="nav-entry" key={item.id}>{item.section && <p className="nav-label">{item.section}</p>}<button onClick={() => navigate(item.id)} className={view === item.id ? 'active' : ''} aria-current={view === item.id ? 'page' : undefined}><Icon name={item.icon} size={19}/><span>{item.label}</span>{item.id === 'recommendations' && data && <span className="nav-count">{data.summary.recommendation_count}</span>}</button></div>)}</nav><div className="sidebar-bottom"><div className="sidebar-status"><span className={`connection-dot ${error ? 'disconnected' : ''}`}/>{loading ? 'Loading dataset' : error ? 'API unavailable' : 'Local dataset connected'}</div><span className="sidebar-version">CloudPilot · FinOps workspace</span></div></aside>
    {menuOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setMenuOpen(false)}/>}
    <div className="workspace-main"><header className="topbar"><div className="breadcrumbs"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMenuOpen(true)}><Icon name="menu"/></button><span>{current.section === 'FINOPS' || view === 'cost-explorer' ? 'FinOps' : view === 'data-sources' ? 'System' : 'Organization'}</span><Icon name="chevron" size={12}/><strong>{current.label}</strong></div><div className="topbar-right"><span className="muted">Local dataset</span></div></header>
      <main><div className="page-heading"><div><h1>{current.label}</h1><p className="page-subtitle">{descriptions[view]}</p></div><div className="page-actions">{view === 'home' && data && <span className="billing-period"><Icon name="calendar" size={16}/>{periodLabel(data.expenses.start, data.expenses.end)}</span>}<button className="secondary-button small-button" aria-label="Refresh workspace" disabled={loading} onClick={() => { setSelection(null); setRefresh(value => value + 1); }}><Icon name="clock" size={15}/>Refresh</button></div></div>
      {view !== 'data-sources' && view !== 'execution' && <div className="filter-bar"><span className="filter-label"><Icon name="filter" size={16}/>Filters</span>{(data?.sources.items.length ?? 0) > 1 && <select aria-label="Data source filter" value={filters.data_source} onChange={event => setFilters(previous => ({ ...previous, data_source: event.target.value }))}><option value="">All data sources</option>{data?.sources.items.map(source => <option key={source.id} value={source.id}>{source.name}</option>)}</select>}<select aria-label="Environment filter" value={filters.environment} onChange={event => setFilters(previous => ({ ...previous, environment: event.target.value }))}><option value="">All environments</option>{['production', 'staging', 'development'].map(value => <option key={value} value={value}>{human(value)}</option>)}</select><select aria-label="Region filter" value={filters.region} onChange={event => setFilters(previous => ({ ...previous, region: event.target.value }))}><option value="">All regions</option>{[...new Set(options.map(resource => resource.region))].sort().map(value => <option key={value}>{value}</option>)}</select><select aria-label="Team filter" value={filters.team} onChange={event => setFilters(previous => ({ ...previous, team: event.target.value }))}><option value="">All teams</option>{[...new Set(options.map(resource => resource.team || 'Unassigned'))].sort().map(value => <option key={value}>{value}</option>)}</select><select aria-label="Resource type filter" value={filters.resource_type} onChange={event => setFilters(previous => ({ ...previous, resource_type: event.target.value }))}><option value="">All resource types</option>{['vm', 'block_volume', 'public_ip', 'gpu'].map(value => <option key={value} value={value}>{typeName(value)}</option>)}</select><div className="search-field"><Icon name="search" size={16}/><input aria-label="Search resources" placeholder="Search resources" value={searchInput} onChange={event => setSearchInput(event.target.value)}/></div>{query && <button className="text-button" onClick={resetFilters}>Clear filters</button>}</div>}
      {error && <div className="error-banner" role="alert"><Icon name="info" size={20}/><div><strong>Unable to load the workspace</strong><p>{error}. Check the configured API connection and retry.</p></div><button className="secondary-button" onClick={() => setRefresh(value => value + 1)}>Retry</button></div>}
      {loading && !data && <div className="loading-state"><span className="spinner"/><p>Loading your organization’s data…</p></div>}
      {data && <div className={`view-content ${loading || error ? 'refreshing' : ''}`} aria-busy={loading}>
        {view === 'monitoring' && <Monitoring key={refresh} query={query} findings={data.recommendations}/>}
        {executionEnabled && view === 'execution' && <ExecutionSetup token={operatorToken} onRegistered={management => { sessionStorage.setItem('cloudpilot-execution-management', management); setExecutionManagement(management); setRegistrationVersion(value => value + 1); navigate('execution'); }}/>}
        {view === 'home' && <Home data={data} query={query} onView={navigate} onSelect={setSelection} onResources={showResources}/>}
        {view === 'resources' && <>{costScope && <div className="expense-context"><div><Icon name="chart" size={20}/><div><strong>{costScope.label} · {periodLabel(costScope.start, costScope.end)}</strong><p>{costLoading ? 'Loading expense contributors…' : resourceExpenses ? `${currency(resourceExpenses.total)} known charges · ${resources.length} resources · ${resourceExpenses.unknown_price_count} unpriced · Synthetic billing` : 'Expense drilldown'}</p></div></div><div className="button-row"><button className="text-button" onClick={() => navigate('cost-explorer')}>Back to Cost Explorer</button><button className="icon-button" aria-label="Clear expense drilldown" onClick={() => navigate('resources')}><Icon name="close" size={17}/></button></div></div>}{resourceCostError && <div className="error-banner" role="alert">{resourceCostError}<button className="text-button" onClick={() => setRefresh(value => value + 1)}>Retry</button></div>}{costLoading ? <div className="loading-state"><span className="spinner"/><p>Loading contributing resources…</p></div> : !resourceCostError && <ResourceList key={`${query}-${costScope?.start}-${costScope?.group}`} items={resources} expenses={resourceExpenses} onOpen={id => setSelection({ kind: 'resource', id })}/>}</>}
        {view === 'recommendations' && <><div className="page-tabs"><button className={recommendationView === 'all' ? 'active' : ''} onClick={() => setRecommendationView('all')}>All recommendations</button><button className={recommendationView === 'plan' ? 'active' : ''} onClick={() => setRecommendationView('plan')}>Review queue<span>{data.plan.items.length}</span></button></div>{recommendationView === 'all' ? <><div className="recommendation-overview"><span><Icon name="recommendations" size={22}/><span>Possible monthly savings<strong>{currency(data.summary.conditional_monthly_savings)}</strong></span></span><span>Conditional on provider verification<small>{data.summary.insufficient_data_count} resources need more telemetry</small></span></div><div id="recommendation-table"><Recommendations key={recommendationAction} action={recommendationAction} onAction={setRecommendationAction} items={data.recommendations} onOpen={id => setSelection({ kind: 'recommendation', id })}/></div></> : <OptimizationPlan plan={data.plan} query={query} onView={() => setRecommendationView('all')} onOpen={id => setSelection({ kind: 'recommendation', id })}/>}</>}
        <div hidden={view !== 'cost-explorer'}><CostExplorer key={data.dataset.version} refresh={refresh} query={query} initial={data.expenses} onResources={showResources}/></div>
        {view === 'data-sources' && <DataSourceView data={data} onClassify={(source, type) => { setFilters({ ...emptyFilters, data_source: source, resource_type: type ?? '' }); setSearchInput(''); navigate('resources'); }}/>}
        {executionEnabled && view === 'execution' && <div><Execution token={operatorToken} management={executionManagement} registrationVersion={registrationVersion} findings={data.recommendations} initialRecommendationId={labFinding}/></div>}
        <footer className="main-footer"><span>CloudPilot<span className="footer-separator">·</span>Local demo workspace</span><span>Historical synthetic data · INR · GST excluded</span></footer>
      </div>}
      </main>
    </div>
    {selection && <DetailDrawer key={`${selection.kind}-${selection.id}`} selection={selection} onClose={() => setSelection(null)} onSelect={setSelection} onChanged={() => setRefresh(value => value + 1)} onLab={id => { setLabFinding(id); setSelection(null); navigate('execution'); }}/>}
  </div>;
}

function FindingTable({ items, onOpen, compact = false }: { items: Recommendation[]; onOpen: (id: string) => void; compact?: boolean }) {
  if (!items.length) return <Empty title="No findings in this view" text="Try another filter or return to the complete estate."/>;
  return <div className="table-scroll"><table className="finding-table"><thead><tr><th>Resource / proposal</th>{!compact && <th>Configuration</th>}<th>Conditional saving <span className="per-month">/ mo equiv.</span></th><th>Review status</th><th><span className="sr-only">Open evidence</span></th></tr></thead><tbody>{items.map(item => <tr key={item.id}>
    <td><button className="resource-link" onClick={() => onOpen(item.id)}>{item.resource_name}</button><small>{item.title}</small></td>
    {!compact && <td className="mono configuration">{item.current_plan_id ?? human(item.action)}{item.target_plan_id && <><span className="config-arrow">→</span>{item.target_plan_id}</>}</td>}
    <td className={Number(item.conditional_monthly_savings ?? item.modeled_monthly_savings ?? 0) > 0 ? 'saving' : ''}><strong>{currency(item.conditional_monthly_savings ?? item.modeled_monthly_savings)}</strong><small>{item.review_only ? 'Subject to unresolved checks' : 'Modeled estimate'}</small></td>
    <td>{findingBadge(item)}</td><td><button className="icon-button" aria-label={`View evidence for ${item.resource_name}`} onClick={() => onOpen(item.id)}><Icon name="chevron" size={17}/></button></td>
  </tr>)}</tbody></table></div>;
}

function Recommendations({ items, onOpen, action, onAction }: { items: Recommendation[]; action: string; onAction: (action: string) => void; onOpen: (id: string) => void }) {
  const [tab, setTab] = useState('findings');
  const [page, setPage] = useState(0);
  const scoped = items.filter(item => action === 'all' || item.action === action);
  const filtered = scoped.filter(item => tab === 'all' || (tab === 'findings' ? ['recommendation', 'blocked'].includes(item.outcome) : tab === 'insufficient_data' ? item.outcome === tab : item.decision === tab));
  const current = Math.min(page, Math.max(0, Math.ceil(filtered.length / 12) - 1));
  return <section className="panel"><div className="panel-heading"><div><h3>Recommendation center</h3><p>Queue a finding for review or dismiss it. Neither operation changes infrastructure.</p></div><select aria-label="Recommendation category" value={action} onChange={event => onAction(event.target.value)}><option value="all">All categories</option><option value="resize">Rightsizing</option><option value="capacity_review">Capacity review</option><option value="idle_review">Idle resources</option><option value="orphan_review">Orphaned resources</option><option value="observe">Other outcomes</option></select></div><div className="tabs">{[['findings', 'Review findings'], ['accepted', 'Queued'], ['insufficient_data', 'Data gaps'], ['rejected', 'Dismissed'], ['all', 'All outcomes']].map(([id, label]) => <button className={tab === id ? 'active' : ''} key={id} onClick={() => { setTab(id); setPage(0); }}>{label}<span>{scoped.filter(item => id === 'all' || (id === 'findings' ? ['recommendation', 'blocked'].includes(item.outcome) : id === 'insufficient_data' ? item.outcome === id : item.decision === id)).length}</span></button>)}</div><FindingTable items={filtered.slice(current * 12, current * 12 + 12)} onOpen={onOpen}/>{filtered.length > 12 && <div className="pagination"><span>{current * 12 + 1}–{Math.min((current + 1) * 12, filtered.length)} of {filtered.length} outcomes</span><div><button className="secondary-button small-button" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous</button><button className="secondary-button small-button" disabled={(current + 1) * 12 >= filtered.length} onClick={() => setPage(current + 1)}>Next</button></div></div>}</section>;
}

function OptimizationPlan({ plan, query, onOpen, onView }: { plan: Plan; query: string; onOpen: (id: string) => void; onView: (view: View) => void }) {
  return <><div className="stats-grid plan-stats"><Stat label="Current known cost" value={currency(plan.current_monthly_cost)} icon="coin" detail={`${plan.unknown_price_count} resources have unknown charges`} foot="Quarterly monthly equivalent"/><Stat label="Accepted-plan known cost" value={currency(plan.projected_monthly_cost)} icon="plan" detail={`${plan.effective_action_count} financially effective actions`} foot="Review items do not reduce this amount"/><Stat label="Accepted modeled savings" value={currency(plan.accepted_monthly_savings)} icon="trend" detail="Verified savings are unavailable" foot="No applied change or actual invoice evidence"/></div><div className="notice"><Icon name="info" size={19}/><p>{plan.note}</p></div><section className="panel"><div className="panel-heading"><div><h3>Your review queue <span className="count-tag">{plan.items.length}</span></h3><p>{plan.review_only_count} items need verification before becoming cost-plan actions</p></div><div className="button-row"><a className="secondary-button small-button" href={exportUrl('csv', query)} download><Icon name="download" size={15}/>CSV</a><a className="secondary-button small-button" href={exportUrl('json', query)} download><Icon name="download" size={15}/>JSON + evidence</a></div></div>{plan.items.length ? <FindingTable items={plan.items} onOpen={onOpen}/> : <Empty title="A thoughtful plan starts here" text="Open a recommendation and queue a finding for review. Your decisions are saved locally."><button className="primary-button" onClick={() => onView('recommendations')}>Explore recommendations<Icon name="arrow" size={16}/></button></Empty>}</section><section className="panel"><div className="panel-heading"><div><h3>Cost reconciliation by environment</h3><p>Each resource is charged once, including retained storage</p></div></div><div className="table-scroll"><table><thead><tr><th>Environment</th><th>Current known cost</th><th>Accepted-plan known cost</th><th>Modeled savings</th><th>Unpriced resources</th></tr></thead><tbody>{plan.by_environment.map(row => <tr key={row.environment}><td className="capitalize">{row.environment}</td><td>{currency(row.current_cost)}</td><td>{currency(row.projected_cost)}</td><td className="saving">{currency(row.savings)}</td><td>{row.unknown_price_count}</td></tr>)}</tbody></table></div></section></>;
}

function DetailDrawer({ selection, onClose, onChanged, onSelect, onLab }: { onLab: (id: string) => void; selection: Selection; onClose: () => void; onChanged: () => void; onSelect: (selection: Selection) => void }) {
  const [resource, setResource] = useState<ResourceDetail | null>(null);
  const [finding, setFinding] = useState<RecommendationDetail | null>(null);
  const [related, setRelated] = useState<Recommendation[]>([]);
  const [series, setSeries] = useState<Series | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const dialog = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden'; closeButton.current?.focus();
    const listener = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current();
      if (event.key === 'Tab') {
        const nodes = [...(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input, select, [tabindex="0"]') ?? [])];
        const first = nodes[0], last = nodes.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener('keydown', listener);
    return () => { document.body.style.overflow = overflow; document.removeEventListener('keydown', listener); if (previous?.isConnected) previous.focus(); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    const fetchDetail = selection.kind === 'resource'
      ? Promise.all([get<ResourceDetail>(`/resources/${selection.id}`, controller.signal), get<Series>(`/resources/${selection.id}/metrics`, controller.signal), all<Recommendation>(`/recommendations?search=${encodeURIComponent(selection.id)}`, controller.signal)]).then(([detail, metrics, findings]) => { setResource(detail); setSeries(metrics); setRelated(findings.filter(item => item.resource_id === selection.id)); })
      : get<RecommendationDetail>(`/recommendations/${selection.id}`, controller.signal).then(setFinding);
    fetchDetail.catch((cause: unknown) => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Unable to load detail'); });
    return () => controller.abort();
  }, [selection.id, selection.kind, retry]);
  const decide = async (decision: Decision) => {
    if (!finding) return;
    setBusy(true); setError(null);
    try { const updated = await patch<RecommendationDetail>(`/recommendations/${finding.id}`, { decision, version: finding.version, expected_revision: finding.decision_revision }); setFinding(updated); onChanged(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to save decision'); }
    finally { setBusy(false); }
  };
  return <div className="drawer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><div className="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="detail-title" ref={dialog}><header className="drawer-header"><div><p className="eyebrow">{selection.kind === 'resource' ? 'RESOURCE EXPLORER' : 'RECOMMENDATION EVIDENCE'}</p><h2 id="detail-title">{resource?.name ?? finding?.resource_name ?? 'Loading detail…'}</h2><p>{resource ? `${resource.id} · ${resource.region} · ${resource.environment}` : finding ? finding.title : 'Retrieving source evidence'}</p></div><button className="icon-button" aria-label="Close detail" onClick={onClose} ref={closeButton}><Icon name="close" size={22}/></button></header><div className="drawer-body">{error && <div className="error-banner" role="alert"><p>{error}</p><button className="secondary-button small-button" onClick={() => { if (error.includes('dataset version')) { onClose(); onChanged(); } else setRetry(value => value + 1); }}>{error.includes('dataset version') ? 'Refresh workspace' : 'Reload evidence'}</button></div>}
    {!resource && !finding && !error && <div className="loading-state"><span className="spinner"/><p>Loading evidence…</p></div>}
    {resource && <><div className="detail-metrics"><DetailMetric label="Current configuration" value={resource.vcpu ? `${resource.vcpu} vCPU / ${resource.memory_gib} GiB` : human(resource.type)}/><DetailMetric label="Known monthly equivalent" value={currency(resource.monthly_cost)}/><DetailMetric label="Complete observations" value={resource.coverage === null ? 'Not applicable' : percent(resource.coverage * 100)}/></div><div className="notice"><Icon name="info" size={18}/><p>Historical synthetic snapshot. Creation timestamps and attachments describe this fixture, not a connected account.</p></div>{series && resource.type === 'vm' && <section className="panel"><Telemetry points={series.points}/></section>}{resource.analysis && <><h3 className="detail-section-title">Demand summary</h3><div className="table-scroll"><table><thead><tr><th>Metric</th><th>Mean</th><th>p95</th><th>p99</th><th>Observed peak</th></tr></thead><tbody>{Object.entries(resource.analysis.statistics).map(([metric, stats]) => <tr key={metric}><td>{human(metric)} <small>{stats.unit}</small></td><td>{stats.mean.toFixed(2)}</td><td>{stats.p95.toFixed(2)}</td><td>{stats.p99.toFixed(2)}</td><td><strong>{stats.maximum.toFixed(2)}</strong></td></tr>)}</tbody></table></div>{resource.analysis.quality.warnings.map(warning => <p className="warning-text" key={warning}>{warning}</p>)}</>}{resource.gpu_statistics && <section className="panel"><h3>Accelerator observations</h3><div className="detail-metrics"><DetailMetric label="Mean GPU utilization" value={percent(resource.gpu_statistics.mean_utilization)}/><DetailMetric label="Peak GPU utilization" value={percent(resource.gpu_statistics.peak_utilization)}/><DetailMetric label="Peak VRAM utilization" value={percent(resource.gpu_statistics.peak_memory_pct)}/></div><p className="muted">{resource.gpu_statistics.samples.toLocaleString()} GPU observations. Device pricing and resize compatibility are unavailable.</p></section>}<h3 className="detail-section-title">Linked findings</h3>{related.map(item => <button className="linked-finding" key={item.id} onClick={() => onSelect({ kind: 'recommendation', id: item.id })}><span><strong>{item.title}</strong><small>{human(item.outcome)} · {human(item.action)}</small></span><Icon name="arrow" size={17}/></button>)}<h3 className="detail-section-title">Ownership & dependencies</h3><dl className="definition-list"><dt>Owner / team</dt><dd>{resource.owner ?? 'Unknown'} / {resource.team ?? 'Unassigned'}</dd><dt>Created</dt><dd>{date(resource.created_at)} {new Date(resource.created_at).getUTCFullYear()}</dd><dt>Lifecycle</dt><dd>{human(resource.lifecycle_state)}</dd><dt>Attached to</dt><dd>{resource.attached_to ?? 'No attachment recorded'}</dd></dl>{resource.relationships.map((relationship, index) => <p key={index} className="dependency"><span className="mono">{relationship.source_resource_id} → {relationship.target_resource_id}</span><small>{human(relationship.relationship_type)} · {relationship.evidence}</small></p>)}{resource.events.length > 0 && <><h3 className="detail-section-title">Source events</h3>{resource.events.map(event => <p className="dependency" key={event.event_id}><strong>{human(event.event_type)}</strong><small>{event.description}</small></p>)}<p className="muted">Events are source context; detection rules do not consume event labels.</p></>}</>}
    {finding && <><div className="finding-intro">{findingBadge(finding)}<Badge>{finding.risk} review risk</Badge><p>{finding.explanation}</p></div><div className="detail-metrics"><DetailMetric label="Current monthly equivalent" value={currency(finding.current_monthly_cost)}/><DetailMetric label="Candidate monthly equivalent" value={currency(finding.target_monthly_cost)}/><DetailMetric label="Conditional monthly difference" value={currency(finding.conditional_monthly_savings ?? finding.modeled_monthly_savings)}/></div>{finding.blockers.length > 0 && <div className="blocker-box"><h3><Icon name="shield" size={18}/>Unresolved prerequisites</h3><ul>{finding.blockers.map(blocker => <li key={blocker}>{blocker}</li>)}</ul><p>Queuing this finding adds a review task. These amounts do not reduce accepted-plan cost.</p></div>}<FindingExplanation id={finding.id}/>{finding.candidates.length > 0 && <CandidateEvidence finding={finding}/>}{executionEnabled && ['resize', 'capacity_review'].includes(finding.action) && <section className="notice"><div><strong>Test this candidate in LocalStack</strong><p>Queue the finding for review first. Production blockers remain in place; the separate lab preview needs its own approval.</p><button className="secondary-button" disabled={finding.decision !== 'accepted'} onClick={() => onLab(finding.id)}>Open in execution lab</button></div></section>}<h3 className="detail-section-title">Before a change can be proposed</h3>{finding.prerequisites.length ? <ol className="prerequisite-list">{finding.prerequisites.map(item => <li key={item}>{item}</li>)}</ol> : <p className="muted">No financially effective action is available for this outcome.</p>}<details className="source-details"><summary>Source versions & assumptions<Icon name="down" size={15}/></summary><dl className="definition-list"><dt>Dataset</dt><dd className="mono">{finding.provenance.dataset_version.slice(0, 16)}</dd><dt>Policy</dt><dd>{finding.provenance.policy_version}</dd><dt>Evidence cutoff</dt><dd>{finding.provenance.analysis_as_of}</dd></dl><ul>{finding.provenance.assumptions.map(item => <li key={item}>{item}</li>)}</ul></details></>}
    </div>{finding && <footer className="drawer-footer"><div><strong>{finding.decision === 'accepted' ? 'Saved in your review plan' : finding.decision === 'rejected' ? 'Finding dismissed' : 'Your decision is saved locally'}</strong><small>Acceptance does not approve or apply a change</small></div><div className="button-row">{finding.decision !== 'pending' && <button className="secondary-button" disabled={busy} onClick={() => void decide('pending')}>Reset</button>}{finding.decision !== 'rejected' && <button className="secondary-button" disabled={busy} onClick={() => void decide('rejected')}>Dismiss</button>}{!['no_action', 'unsupported', 'insufficient_data'].includes(finding.outcome) && finding.decision !== 'accepted' && <button className="primary-button" disabled={busy} onClick={() => void decide('accepted')}><Icon name="check" size={16}/>{busy ? 'Saving…' : finding.review_only ? 'Queue for review' : 'Add to cost plan'}</button>}</div></footer>}</div></div>;
}

function DetailMetric({ label, value }: { label: string; value: ReactNode }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function CandidateEvidence({ finding }: { finding: RecommendationDetail }) {
  const [selectedId, setSelectedId] = useState(finding.target_plan_id ?? finding.current_plan_id ?? finding.candidates[0]?.plan.id);
  const [showAll, setShowAll] = useState(false);
  const [multiplier, setMultiplier] = useState(1);
  const [simulation, setSimulation] = useState<Candidate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const original = finding.candidates.find(item => item.plan.id === selectedId);
  const current = finding.candidates.find(item => item.plan.id === finding.current_plan_id);
  const candidate = simulation ?? original;
  const compatible = finding.candidates.filter(item => showAll || (item.plan.hardware === current?.plan.hardware && item.plan.instance_family === current?.plan.instance_family));
  const simulate = async () => {
    setBusy(true); setError(null);
    try { const result = await post<{ candidate: Candidate }>('/simulate', { resource_id: finding.resource_id, target_plan_id: selectedId, demand_multiplier: multiplier }); setSimulation(result.candidate); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Simulation failed'); }
    finally { setBusy(false); }
  };
  return <><div className="detail-section-heading"><div><h3>Candidate comparison</h3><p>CPU/RAM fit is one part of eligibility. Unknown gates remain blocking.</p></div><label className="checkbox-label"><input type="checkbox" checked={showAll} onChange={event => setShowAll(event.target.checked)}/>All hardware / families</label></div><details><summary>Compare catalog configurations</summary><div className="candidate-table table-scroll"><table><thead><tr><th>Catalog configuration</th><th>CPU peak</th><th>Memory peak</th><th>Monthly equiv.</th><th>Gate result</th></tr></thead><tbody>{compatible.map(item => <tr key={item.plan.id} className={selectedId === item.plan.id ? 'selected' : ''}><td><button className="resource-link mono" disabled={busy} onClick={() => { setSelectedId(item.plan.id); setSimulation(null); }}>{item.plan.id}</button><small>{item.plan.vcpu} vCPU / {item.plan.memory_gib} GiB{item.plan.id === finding.current_plan_id ? ' · current' : ''}</small></td><td className={(item.projected_cpu_peak ?? 0) > 80 ? 'danger-text' : ''}>{percent(item.projected_cpu_peak)}</td><td className={(item.projected_memory_peak ?? 0) > 80 ? 'danger-text' : ''}>{percent(item.projected_memory_peak)}</td><td>{currency(item.monthly_cost)}</td><td><Badge tone={item.eligible ? 'green' : item.checks.some(check => check.status === 'failed') ? 'red' : 'amber'}>{item.eligible ? 'Passes all gates' : item.checks.some(check => check.status === 'failed') ? 'Rejected' : 'Unknown gates'}</Badge></td></tr>)}</tbody></table></div></details>{candidate && <><div className="simulation-controls"><div><h3>Capacity stress test</h3><p>Model a capacity scenario for <span className="mono">{selectedId}</span></p></div><label>Demand <strong>{multiplier.toFixed(2)}×</strong><input aria-label="Demand multiplier" type="range" min="0.5" max="3" step="0.25" value={multiplier} disabled={busy} onChange={event => { setMultiplier(Number(event.target.value)); setSimulation(null); }}/></label><button className="secondary-button" disabled={busy} onClick={() => void simulate()}>{busy ? 'Modeling…' : 'Run scenario'}</button></div>{error && <p className="danger-text" role="alert">{error}</p>}{candidate.replay && <div className="replay-strip"><span><strong>{candidate.replay.sample_count.toLocaleString()}</strong> observed samples</span><span><strong>{candidate.replay.breached_samples}</strong> historical breaches</span><span><strong>{candidate.replay.stress_breached_samples}</strong> breaches at {candidate.replay.stress_multiplier}× stress</span><Badge>{simulation ? `${multiplier}× modeled scenario` : 'Historical projection'}</Badge></div>}<details><summary>Full provider and replay checks for {selectedId}</summary><div className="check-list">{candidate.checks.map(check => <div className={`check-row ${check.status}`} key={check.code}><span className="check-symbol"><Icon name={check.status === 'passed' ? 'check' : check.status === 'failed' ? 'close' : 'info'} size={14}/></span><div><strong>{human(check.code)}<span>{check.status}</span></strong><p>{check.message}</p>{check.actual !== null && <small>Observed/projected: {typeof check.actual === 'number' ? check.actual.toFixed(2) : check.actual}{check.unit && ` ${check.unit}`}{check.limit !== null && ` · Limit: ${check.limit}`}</small>}</div></div>)}</div></details></>}</>;
}
