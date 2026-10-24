// Keep these starter types aligned with backend/app/models/contracts.py.
export interface Resource {
  id: string;
  name: string;
  type: 'vm' | 'volume' | 'ip';
  region: string;
  environment: 'production' | 'staging' | 'development';
  team: string;
  owner: string | null;
  current_plan_id: string | null;
  configuration_revision: number;
  provenance: 'synthetic' | 'imported' | 'provider';
  dataset_version: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${baseUrl}/api${path}`, { signal });
  if (!response.ok) {
    throw new Error(`API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

