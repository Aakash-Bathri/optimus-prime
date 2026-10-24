import { useEffect, useState } from 'react';
import { Badge, currency, date, Empty, Icon } from './components';
import { get } from './lib/api';
import type { Breakdown, ExpensePoint, Expenses, Granularity } from './lib/api';

export interface CostScope { start: string; end: string; breakdown: Breakdown; group?: string; label: string }
export const typeName = (type: string) => ({ vm: 'Virtual machines', block_volume: 'Block volumes', public_ip: 'Public IPs', gpu: 'GPUs' }[type] ?? type.replaceAll('_', ' '));
const colors = ['#f5a623', '#53a4cf', '#836ac8', '#54b39a', '#d56b77', '#8194aa', '#c59153', '#afbd58'];
const groupName = (value: string) => typeName(value);
export const periodLabel = (start: string, end: string) => `${date(start)} – ${date(end)} ${end.slice(0, 4)}`;

export function ExpenseChart({ expenses, onSelect, compact = false }: { expenses: Expenses; onSelect: (point: ExpensePoint, group?: string) => void; compact?: boolean }) {
  const [hover, setHover] = useState<number | null>(null);
  const points = expenses.points;
  const width = 960, height = compact ? 220 : 290, left = 62, right = 12, top = 15, bottom = height - 36;
  const ceiling = Math.max(1, ...points.map(point => Number(point.amount))) * 1.18;
  const step = (width - left - right) / Math.max(1, points.length);
  const barWidth = Math.min(compact ? 58 : 80, step * .64);
  if (!Number(expenses.total)) return <Empty title="No expenses in this view" text="Try a different period or clear the filters. Resources without pricing are excluded from expense totals."/>;
  const hovered = hover === null ? undefined : points[hover];
  return <div className="expense-chart-wrap">
    <svg className="expense-chart" viewBox={`0 0 ${width} ${height}`} aria-label="Expenses over the selected period. Select a bar to view contributing resources." role="group" onMouseLeave={() => setHover(null)}>
      {[0, .25, .5, .75, 1].map(fraction => <g key={fraction}><line x1={left} x2={width - right} y1={bottom - fraction * (bottom - top)} y2={bottom - fraction * (bottom - top)} stroke="#e9edf1" strokeDasharray="3 4"/><text x={left - 12} y={bottom - fraction * (bottom - top) + 4} textAnchor="end" fill="#78858f" fontSize="11">{currency(ceiling * fraction, true)}</text></g>)}
      {points.map((point, index) => {
        const x = left + step * (index + .5);
        let accumulated = 0;
        return <g key={point.start} onMouseEnter={() => setHover(index)}>
          {hover === index && <rect x={x - step / 2} y={top} width={step} height={bottom - top} fill="#eff3f7"/>}
          {expenses.groups.map((group, groupIndex) => {
            const amount = Number(point.groups[group.id] ?? 0), barHeight = amount / ceiling * (bottom - top);
            accumulated += barHeight;
            if (!amount) return null;
            return <rect key={group.id} x={x - barWidth / 2} y={bottom - accumulated} width={barWidth} height={Math.max(.6, barHeight)} fill={colors[groupIndex % colors.length]} opacity={hover === null || hover === index ? 1 : .65} role="button" tabIndex={0} aria-label={`${groupName(group.name)}, ${periodLabel(point.start, point.end)}, ${currency(amount)}. View contributing resources`} onClick={() => onSelect(point, group.id)} onFocus={() => setHover(index)} onBlur={() => setHover(null)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(point, group.id); } }}><title>{groupName(group.name)} · {periodLabel(point.start, point.end)} · {currency(amount)}</title></rect>;
          })}
          {(index % Math.max(1, Math.ceil(points.length / (compact ? 6 : 10))) === 0 || index === points.length - 1) && <text x={x} y={height - 10} textAnchor="middle" fill="#78858f" fontSize="11">{expenses.granularity === 'month' ? new Intl.DateTimeFormat('en-IN', { month: 'short', timeZone: 'UTC' }).format(new Date(point.start)) : date(point.start)}</text>}
        </g>;
      })}
    </svg>
    {hovered && <div className="expense-tooltip" role="status"><strong>{periodLabel(hovered.start, hovered.end)}</strong><span>{currency(hovered.amount)}</span><small>Select a bar to see resources</small></div>}
    <div className="expense-legend">{expenses.groups.map((group, index) => <button key={group.id} onClick={() => onSelect({ start: expenses.start, end: expenses.end, amount: group.amount, groups: {} }, group.id)}><i style={{ background: colors[index % colors.length] }}/><span>{groupName(group.name)}</span><strong>{group.resource_count > 0 && group.resource_count === group.unknown_price_count ? 'Unpriced' : currency(group.amount)}</strong></button>)}</div>
  </div>;
}

export function CostExplorer({ query, initial, onResources }: { query: string; initial: Expenses; onResources: (scope: CostScope) => void }) {
  const [range, setRange] = useState({ start: initial.start, end: initial.end });
  const [period, setPeriod] = useState('latest');
  const [granularity, setGranularity] = useState<Granularity>('day');
  const [breakdown, setBreakdown] = useState<Breakdown>('data_source');
  const [expenses, setExpenses] = useState<Expenses>(initial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const validRange = range.start && range.end && range.start <= range.end;
  useEffect(() => {
    if (!validRange) return;
    const controller = new AbortController();
    setLoading(true); setError('');
    const params = new URLSearchParams(query);
    Object.entries({ ...range, granularity, breakdown }).forEach(([key, value]) => params.set(key, value));
    get<Expenses>(`/expenses?${params}`, controller.signal).then(result => { if (!controller.signal.aborted) { setExpenses(result); setLoading(false); } }).catch((cause: unknown) => { if (!controller.signal.aborted) { setError(cause instanceof Error ? cause.message : 'Unable to load expenses'); setLoading(false); } });
    return () => controller.abort();
  }, [query, range.start, range.end, granularity, breakdown, validRange]);
  const drill = (point: ExpensePoint, group?: string) => onResources({ start: point.start, end: point.end, breakdown, group, label: group ? groupName(expenses.groups.find(item => item.id === group)?.name ?? group) : 'All sources' });
  const choosePeriod = (value: string) => {
    setPeriod(value);
    if (value === 'all') { setRange({ start: initial.available_start, end: initial.available_end }); setGranularity('month'); }
    if (value === 'latest') setRange({ start: `${initial.available_end.slice(0, 7)}-01`, end: initial.available_end });
    if (value === 'previous') {
      const previous = new Date(`${initial.available_end.slice(0, 7)}-01T00:00:00Z`);
      previous.setUTCDate(0);
      setRange({ start: `${previous.toISOString().slice(0, 7)}-01`, end: previous.toISOString().slice(0, 10) });
    }
  };
  return <>
    <section className="panel period-panel"><div className="period-controls"><Icon name="calendar" size={19}/><label>Period<select aria-label="Expense period" value={period} onChange={event => choosePeriod(event.target.value)}><option value="latest">Latest billing month</option><option value="previous">Previous billing month</option><option value="all">All billing history</option><option value="custom">Custom range</option></select></label><label>From<input aria-label="Start date" type="date" min={initial.available_start} max={initial.available_end} value={range.start} onChange={event => { setPeriod('custom'); setRange(previous => ({ ...previous, start: event.target.value })); }}/></label><span className="range-dash">–</span><label>To<input aria-label="End date" type="date" min={initial.available_start} max={initial.available_end} value={range.end} onChange={event => { setPeriod('custom'); setRange(previous => ({ ...previous, end: event.target.value })); }}/></label><span className="period-availability">Available: {periodLabel(initial.available_start, initial.available_end)}</span></div>{!validRange && <p className="danger-text" role="alert">Choose a valid date range with the start on or before the end.</p>}</section>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <div className={`cost-results ${loading || !validRange || error ? 'refreshing' : ''}`} aria-busy={loading}>
      <div className="expense-summary-grid"><div className="expense-total-card"><span>Total expenses</span><strong>{currency(expenses.total)}</strong><small>{periodLabel(expenses.start, expenses.end)} · INR</small></div><div><span>Daily average</span><strong>{currency(Number(expenses.total) / (Math.round((Date.parse(expenses.end) - Date.parse(expenses.start)) / 86400000) + 1))}</strong><small>Allocated from monthly billing</small></div><div><span>Resources</span><strong>{expenses.resource_count - expenses.unknown_price_count}<small> / {expenses.resource_count}</small></strong><small>{expenses.unknown_price_count} resources without pricing</small></div><div><span>Data sources</span><strong>{expenses.resource_count ? 1 : 0}</strong><small>Local Utho benchmark</small></div></div>
      <section className="panel"><div className="panel-heading"><div><h3>Expense history</h3><p>Select a chart segment to explore the resources behind it.</p></div><div className="segmented" aria-label="Expense granularity">{([['day', 'Daily'], ['week', 'Weekly'], ['month', 'Monthly']] as const).map(([value, label]) => <button key={value} aria-pressed={granularity === value} className={granularity === value ? 'active' : ''} onClick={() => setGranularity(value)}>{label}</button>)}</div></div><ExpenseChart expenses={expenses} onSelect={drill}/></section>
      <section className="panel"><div className="panel-heading"><div><h3>Expense breakdown</h3><p>Follow a category to its contributing resources.</p></div><label className="inline-label">Group by<select aria-label="Expense breakdown" value={breakdown} onChange={event => setBreakdown(event.target.value as Breakdown)}><option value="data_source">Data source</option><option value="resource_type">Resource type</option><option value="environment">Environment</option><option value="region">Region</option><option value="team">Team</option></select></label></div><div className="table-scroll"><table><thead><tr><th>{groupName(breakdown)}</th><th>Resources</th><th>Expenses</th><th>Share of expenses</th><th/></tr></thead><tbody>{expenses.groups.map((group, index) => <tr key={group.id}><td><button className="resource-link category-link" onClick={() => drill({ start: expenses.start, end: expenses.end, amount: group.amount, groups: {} }, group.id)}><i style={{ background: colors[index % colors.length] }}/>{groupName(group.name)}</button></td><td>{group.resource_count}<small>{group.unknown_price_count ? `${group.unknown_price_count} unpriced` : 'All resources priced'}</small></td><td><strong>{group.resource_count > 0 && group.resource_count === group.unknown_price_count ? 'Unpriced' : currency(group.amount)}</strong></td><td><div className="share-cell"><span>{Number(expenses.total) ? (Number(group.amount) / Number(expenses.total) * 100).toFixed(1) : '0'}%</span><div className="bar-track"><div style={{ background: colors[index % colors.length], width: `${Number(expenses.total) ? Number(group.amount) / Number(expenses.total) * 100 : 0}%` }}/></div></div></td><td><button className="icon-button" aria-label={`View ${groupName(group.name)} expenses by resource`} onClick={() => drill({ start: expenses.start, end: expenses.end, amount: group.amount, groups: {} }, group.id)}><Icon name="arrow" size={17}/></button></td></tr>)}</tbody></table></div>{!expenses.groups.length && <Empty title="No expense categories" text="Clear the filters to see your organization’s expenses."/>}</section>
    </div>
    <div className="cost-footnote"><Badge>Historical data</Badge><p>{expenses.allocation_note}</p></div>
  </>;
}
