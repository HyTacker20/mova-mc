import type { ConfigResponse, ModInfo, OverallStatsResponse, ProviderInfo } from '../types'

export interface CatalogResponse { providers: ProviderInfo[] }
export interface JobCreatedResponse { job_id: string; status: string }
export interface JobStatusResponse { job_id: string; status: string; error: string | null; stats: OverallStatsResponse | null }
export interface ScanResponse { mods: ModInfo[]; total: number; selected: number }

import type { JobRequest } from '../types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    let detail = text
    try { detail = (JSON.parse(text) as { detail?: string }).detail ?? text } catch { /* keep */ }
    throw new Error(detail)
  }
  if (res.status === 204) return undefined as unknown as T
  return res.json() as Promise<T>
}

export const api = {
  getProviders: (): Promise<CatalogResponse> =>
    request('/api/catalog/providers'),

  getConfig: (modsPath: string): Promise<ConfigResponse> =>
    request(`/api/config?path=${encodeURIComponent(modsPath)}`),

  saveConfig: (data: {
    provider?: string; model?: string;
    mods_path?: string; output?: string; output_mode?: string;
    workers?: number; no_cache?: boolean; hint_lang?: string;
    qa?: Record<string, unknown>;
    config_path?: string;
  }): Promise<{ status: string; config_path: string }> =>
    request('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  scanMods: (path: string): Promise<ScanResponse> =>
    request(`/api/mods?path=${encodeURIComponent(path)}`),

  createJob: (req: JobRequest): Promise<JobCreatedResponse> =>
    request('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),

  getJob: (jobId: string): Promise<JobStatusResponse> =>
    request(`/api/jobs/${jobId}`),

  cancelJob: (jobId: string): Promise<void> =>
    request(`/api/jobs/${jobId}/cancel`, { method: 'POST' }),
}
