// Keep consumed fields aligned with backend/app/models/contracts.py.
export interface Resource {
  id: string;
  name: string;
  type: 'vm' | 'block_volume' | 'public_ip' | 'gpu';
  region: string;
  environment: 'production' | 'staging' | 'development';
  team: string | null;
  owner: string | null;
  current_plan_id: string | null;
  configuration_revision: number;
  provenance: 'synthetic';
  dataset_version: string;
  status: string;
  hardware: string | null;
  instance_family: string | null;
  vcpu: number | null;
  memory_gib: number | null;
  disk_gb: number | null;
  monthly_cost: string | null;
  cpu_p95: number | null;
  memory_p95: number | null;
  coverage: number | null;
  created_at: string;
  attached_to: string | null;
  lifecycle_state: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${baseUrl}/api${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { message?: string; detail?: string | { msg: string }[]; details?: { message: string }[] } | null;
    const detail = typeof body?.detail === 'string' ? body.detail : Array.isArray(body?.detail) ? body.detail.map(item => item.msg).join('; ') : undefined;
    throw new Error((body?.details?.length ? body.details.map(item => item.message).join('; ') : body?.message) ?? detail ?? `API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const get = <T,>(path: string, signal?: AbortSignal) => request<T>(path, { signal });
export const post = <T,>(path: string, body: unknown) => request<T>(path, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
});
export const patch = <T,>(path: string, body: unknown) => request<T>(path, {
  method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
});

export async function all<T>(path: string, signal?: AbortSignal): Promise<T[]> {
  const first = await get<Page<T>>(`${path}${path.includes('?') ? '&' : '?'}limit=200`, signal);
  const items = [...first.items];
  while (items.length < first.total) {
    const next = await get<Page<T>>(`${path}${path.includes('?') ? '&' : '?'}limit=200&offset=${items.length}`, signal);
    if (!next.items.length) throw new Error('Inventory changed during loading. Refresh to reload all results.');
    items.push(...next.items);
  }
  return items;
}

export function exportUrl(format: 'json' | 'csv', query = '') {
  return `${baseUrl}/api/optimization-plan/export?format=${format}${query ? `&${query}` : ''}`;
}

export interface Dataset {
  version: string;
  catalog_version: string;
  engine_version: string;
  analysis_as_of: string;
  window_start: string;
  duration_days: number;
  resource_count: number;
  metric_rows: number;
  gpu_metric_rows: number;
  catalog_count: number;
  duplicate_event_rows: number;
  missing_observation_rows: number;
  invalid_observation_rows: number;
  pricing_snapshot_date: string;
  assumptions: string[];
  cost_basis: string;
  policy: { version: string; cpu_limit_pct: number; memory_limit_pct: number; minimum_coverage: number; stress_multiplier: number };
}

export interface MetricStats {
  count: number; mean: number; p50: number; p95: number; p99: number; maximum: number; ewma: number; unit: string;
}

export interface Analysis {
  quality: {
    expected_samples: number; valid_samples: number; coverage: number; sufficient: boolean;
    latest_sample: string | null; warnings: string[];
  };
  statistics: Record<string, MetricStats>;
}

export interface ResourceDetail extends Resource {
  analysis: Analysis | null;
  relationships: { source_resource_id: string; target_resource_id: string; relationship_type: string; evidence: string }[];
  events: { event_id: string; event_type: string; description: string; start_time: string }[];
  gpu_statistics: { samples: number; mean_utilization: number | null; peak_utilization: number | null; peak_memory_pct: number | null } | null;
}

export interface Check {
  code: string; status: 'passed' | 'failed' | 'unknown'; message: string;
  actual: number | string | null; limit: number | string | null; unit: string | null;
}

export interface ProviderPlan {
  id: string; name: string; hardware: string; instance_family: string;
  vcpu: number; memory_gib: number; disk_gb: number | null; compute_monthly_equivalent: string;
}

export interface Candidate {
  plan: ProviderPlan;
  checks: Check[]; capacity_eligible: boolean; eligible: boolean;
  monthly_cost: string; monthly_savings: string | null;
  projected_cpu_peak: number | null; projected_memory_peak: number | null;
  projected_cpu_p99: number | null; projected_memory_p99: number | null;
  replay: { sample_count: number; missing_samples: number; breached_samples: number; stress_breached_samples: number; stress_multiplier: number } | null;
}

export type Decision = 'pending' | 'accepted' | 'rejected';

export interface Recommendation {
  id: string; version: string; resource_id: string; resource_name: string;
  environment: string; region: string; team: string | null;
  action: 'resize' | 'capacity_review' | 'idle_review' | 'orphan_review' | 'observe';
  outcome: 'recommendation' | 'blocked' | 'insufficient_data' | 'no_action' | 'unsupported';
  title: string; explanation: string; risk: string; ready: boolean; review_only: boolean;
  current_plan_id: string | null; target_plan_id: string | null;
  current_monthly_cost: string | null; target_monthly_cost: string | null;
  modeled_monthly_savings: string | null; conditional_monthly_savings: string | null;
  blockers: string[]; prerequisites: string[];
  decision: Decision; decision_revision: number;
}

export interface RecommendationDetail extends Recommendation {
  analysis: Analysis | null;
  candidates: Candidate[]; checks: Check[];
  provenance: { dataset_version: string; policy_version: string; engine_version: string; analysis_as_of: string; assumptions: string[] };
}

export interface Alert {
  id: string; resource_id: string | null; resource_name: string | null;
  category: string; severity: 'info' | 'warning' | 'critical'; title: string; explanation: string;
  timestamp: string; observed: number; baseline: number; threshold: number; unit: string; source: string;
}

export interface Plan {
  current_monthly_cost: string; projected_monthly_cost: string; accepted_monthly_savings: string;
  verified_savings: null; unknown_price_count: number; review_only_count: number; effective_action_count: number;
  items: Recommendation[]; note: string;
  by_environment: { environment: string; current_cost: string; projected_cost: string; savings: string; unknown_price_count: number }[];
}

export interface Summary {
  resource_count: number; vm_count: number; known_monthly_cost: string; unknown_price_count: number;
  conditional_monthly_savings: string; recommendation_count: number; ready_count: number; insufficient_data_count: number;
  avg_cpu_p95: number | null; avg_memory_p95: number | null; alert_count: number;
  breakdown: Record<'environment' | 'region' | 'team', { name: string; cost: string; count: number; unknown_price_count: number }[]>;
  priority_recommendations: Recommendation[]; alerts: Alert[]; plan: Plan;
  billing_history: { month: string; amount: string; synthetic: true }[];
}

export interface SeriesPoint {
  timestamp: string; samples: number; valid_samples: number; expected_samples: number;
  cpu?: number | null; cpu_peak?: number | null; memory?: number | null; memory_peak?: number | null;
  disk?: number | null; disk_peak?: number | null; iops?: number | null; iops_peak?: number | null;
  network_in?: number | null; network_in_peak?: number | null; network_out?: number | null; network_out_peak?: number | null;
}
export interface Series { points: SeriesPoint[]; resolution: string }

export type Granularity = 'day' | 'week' | 'month';
export type Breakdown = 'data_source' | 'resource_type' | 'environment' | 'region' | 'team';
export interface ExpensePoint { start: string; end: string; amount: string; groups: Record<string, string> }
export interface ExpenseGroup { id: string; name: string; amount: string; resource_count: number; unknown_price_count: number }
export interface Expenses {
  start: string; end: string; available_start: string; available_end: string;
  granularity: Granularity; breakdown: Breakdown; total: string;
  resource_count: number; unknown_price_count: number; allocation_note: string;
  points: ExpensePoint[]; groups: ExpenseGroup[];
  resources: { resource_id: string; amount: string | null }[];
}
export interface DataSource {
  id: string; name: string; provider: string; kind: string;
  resource_count: number; unknown_price_count: number; imported_at: string;
  billing_start: string; billing_end: string;
  classifications: { type: Resource['type']; count: number }[];
  feeds: { name: string; file: string; rows: number; classification: string }[];
}
export interface DataSources {
  organization: { id: string; name: string };
  items: DataSource[];
}

