import { useId, useState } from 'react';
import type { ReactNode } from 'react';
import type { SeriesPoint } from './lib/api';

export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    cloud: <><path d="M7 17H6a4 4 0 0 1-.3-8A6.5 6.5 0 0 1 18 7.7 4.7 4.7 0 0 1 18 17h-1"/><path d="m9 13 3-3 3 3m-3-3v11"/></>,
    overview: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    resources: <><rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6.5h.01M7 17.5h.01M11 6.5h6m-6 11h6"/></>,
    recommendations: <><path d="m13 2-3 8H4l7 5-2 7 11-13h-7l2-7Z"/></>,
    plan: <><path d="M9 4H5v17h14V4h-4"/><rect x="9" y="2" width="6" height="4" rx="1"/><path d="m8 12 2 2 5-5m-7 9h8"/></>,
    alerts: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8 12a2 2 0 0 0 4 0"/></>,
    arrow: <path d="M4 12h15m-6-6 6 6-6 6"/>,
    chevron: <path d="m9 5 7 7-7 7"/>,
    down: <path d="m6 9 6 6 6-6"/>,
    download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
    filter: <><path d="M4 7h16M7 12h10m-7 5h4"/></>,
    shield: <><path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6l9-4Z"/><path d="m8 12 3 3 5-6"/></>,
    close: <path d="m6 6 12 12M6 18 18 6"/>,
    check: <path d="m5 12 4 4L19 6"/>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    trend: <><path d="m3 17 6-6 4 3 8-10m-6 0h6v6"/></>,
    coin: <><circle cx="12" cy="12" r="9"/><path d="M8 7h8M8 10h8m-7-3c5 0 5 6 0 6l6 5"/></>,
    menu: <path d="M4 6h16M4 12h16M4 18h16"/>,
    home: <><path d="m3 10 9-7 9 7v11h-6v-7H9v7H3Z"/></>,
    chart: <><path d="M4 3v17h17M8 16v-5m5 5V6m5 10V9"/></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/></>,
    building: <><path d="M5 21V3h14v18M3 21h18M9 7h1m4 0h1M9 11h1m4 0h1m-6 10v-5h4v5"/></>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></>,
    logout: <><path d="M9 4H4v16h5m4-8h8m-4-4 4 4-4 4"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18m-13 5h.01m4 0h.01m4 0h.01"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] ?? paths.info}</svg>;
}

export function currency(value: string | number | null | undefined, compact = false) {
  if (value === null || value === undefined) return 'Unknown';
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: compact ? 1 : Number(value) % 1 === 0 ? 0 : 2, notation: compact ? 'compact' : 'standard' }).format(Number(value));
}

export function percent(value: number | null | undefined) {
  return value == null ? 'Unavailable' : `${value.toFixed(1)}%`;
}

export function human(value: string) { return value.replaceAll('_', ' '); }
export function date(value: string, month = 'short') {
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: month as 'short', timeZone: 'UTC' }).format(new Date(value));
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}><span className="badge-dot"/>{children}</span>;
}

export function Empty({ title, text, children }: { title: string; text: string; children?: ReactNode }) {
  return <div className="empty"><div className="empty-icon"><Icon name="search" size={26}/></div><h3>{title}</h3><p>{text}</p>{children}</div>;
}

export function SparkChart({ points, metric = 'cpu', height = 205 }: { points: SeriesPoint[]; metric?: 'cpu' | 'memory' | 'disk' | 'iops' | 'network_in' | 'network_out'; height?: number }) {
  const id = useId().replaceAll(':', '');
  const peakKey = `${metric}_peak` as keyof SeriesPoint;
  const isPercent = ['cpu', 'memory', 'disk'].includes(metric);
  const numbers = points.flatMap(point => [point[metric], point[peakKey]]).filter((value): value is number => typeof value === 'number');
  const maximum = isPercent ? Math.max(100, ...numbers) : Math.max(1, ...numbers) * 1.1;
  const width = 660, left = 40, right = 12, top = 10, bottom = height - 28;
  const x = (index: number) => left + index / Math.max(1, points.length - 1) * (width - left - right);
  const y = (value: number) => bottom - value / maximum * (bottom - top);
  const segments = (key: keyof SeriesPoint) => {
    const result: { x: number; y: number; index: number }[][] = [];
    let current: { x: number; y: number; index: number }[] = [];
    points.forEach((point, index) => {
      const value = point[key];
      if (typeof value !== 'number') { if (current.length) result.push(current); current = []; }
      else current.push({ x: x(index), y: y(value), index });
    });
    if (current.length) result.push(current);
    return result;
  };
  if (!numbers.length) return <Empty title="No observations available" text="Missing telemetry is shown as a gap. No values have been substituted."/>;
  return <svg className="timeseries" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${human(metric)} mean and observed maximum. Missing observations are gaps.`}>
    <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#168f78" stopOpacity=".16"/><stop offset="100%" stopColor="#168f78" stopOpacity="0"/></linearGradient></defs>
    {[0, .25, .5, .75, 1].map(fraction => <g key={fraction}><line x1={left} x2={width - right} y1={y(maximum * fraction)} y2={y(maximum * fraction)} stroke="#edf0ee" strokeDasharray="3 4"/><text x={left - 10} y={y(maximum * fraction) + 4} textAnchor="end" fill="#6e7b71" fontSize="10">{Math.round(maximum * fraction)}{isPercent ? '%' : ''}</text></g>)}
    {segments(metric).map((segment, index) => <path key={`area-${index}`} d={`M${segment[0].x},${bottom} L${segment.map(point => `${point.x},${point.y}`).join(' L')} L${segment.at(-1)!.x},${bottom} Z`} fill={`url(#${id})`}/>)}
    {segments(peakKey).map((segment, index) => <polyline key={`peak-${index}`} points={segment.map(point => `${point.x},${point.y}`).join(' ')} fill="none" stroke="#b7c9c2" strokeWidth="1.4" strokeDasharray="4 4"/>)}
    {segments(metric).map((segment, index) => <polyline key={index} points={segment.map(point => `${point.x},${point.y}`).join(' ')} fill="none" stroke="#16876f" strokeWidth="2.2" strokeLinejoin="round"/>)}
    {points.map((point, index) => typeof point[metric] === 'number' ? <circle key={index} cx={x(index)} cy={y(point[metric]!)} r="5" fill="transparent"><title>{date(point.timestamp)} · mean {point[metric]!.toFixed(1)} · peak {typeof point[peakKey] === 'number' ? Number(point[peakKey]).toFixed(1) : 'unknown'} · {point.valid_samples}/{point.expected_samples} samples</title></circle> : null)}
    {points.filter((_, index) => index % Math.max(1, Math.floor(points.length / 5)) === 0).map(point => <text key={point.timestamp} x={x(points.indexOf(point))} y={height - 6} textAnchor="middle" fill="#6e7b71" fontSize="10">{date(point.timestamp)}</text>)}
  </svg>;
}

export function Telemetry({ points, title = 'Workload activity' }: { points: SeriesPoint[]; title?: string }) {
  const [metric, setMetric] = useState<'cpu' | 'memory' | 'disk' | 'iops' | 'network_in' | 'network_out'>('cpu');
  return <><div className="panel-heading"><div><h3>{title}</h3><p>Daily means with observed peaks retained</p></div><select aria-label="Chart metric" value={metric} onChange={event => setMetric(event.target.value as typeof metric)}><option value="cpu">CPU · %</option><option value="memory">Memory · %</option><option value="disk">Disk used · %</option><option value="iops">Disk · IOPS</option><option value="network_in">Network in · Mbps</option><option value="network_out">Network out · Mbps</option></select></div><SparkChart points={points} metric={metric}/><div className="chart-caption"><span><i className="legend-line"/>Daily mean</span><span><i className="legend-line dashed"/>Observed peak</span><span className="push-right">UTC assumed · synthetic telemetry</span></div></>;
}
