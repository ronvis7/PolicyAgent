import { del, get, post, request } from './fetch'

export type Contest = { id: string; title: string; source: string; source_name: string; origin: 'official' | 'web' | 'tenant'; source_url: string; region: string; publish_date: string | null; apply_deadline: string | null; deadline_status: string; body_text?: string; apply_window_text?: string }
export type ContestList = { items: Contest[]; total: number; page: number; page_size: number }
export type ContestSource = { id: string; key: string; name: string; region: string; home_url: string; adapter_type: string; adapter_config: Record<string, string>; enabled: boolean; created_at: string; updated_at: string }
export type ContestSubscription = { id: string; keyword: string; enabled: boolean; last_run_at: string | null; created_at: string; updated_at: string }
export type ContestRun = { id: string; status: 'running' | 'succeeded' | 'failed'; trigger: 'manual' | 'scheduled'; started_at: string; finished_at: string | null; searched_count: number; valid_count: number; stored_count: number; feed_new_count: number; error_message: string }
export type TenantContestSource = { id: string; name: string; region: string; list_url: string; title_keywords: string; link_selector: string; content_selector: string; preset_source_id: string | null; enabled: boolean; preflight_at: string | null; created_at: string; updated_at: string }
export type ContestSourceSuggestion = { name: string; region: string; list_url: string; title_keywords: string; link_selector: string; content_selector: string; reason: string }

export const contestApi = {
  list: (params: Record<string, string | number | boolean> = {}) => get<ContestList>('/contests', params),
  get: (id: string) => get<Contest>(`/contests/${id}`),
  sources: () => get<{ items: ContestSource[] }>('/contest-sources'),
  subscriptions: () => get<{ items: ContestSubscription[] }>('/contest-subscriptions'),
  addSubscription: (keyword: string) => post<ContestSubscription>('/contest-subscriptions', { keyword }),
  setSubscription: (id: string, enabled: boolean) => request<ContestSubscription>(`/contest-subscriptions/${id}`, { method: 'PATCH', body: JSON.stringify({ enabled }) }),
  deleteSubscription: (id: string) => del(`/contest-subscriptions/${id}`),
  discoverSubscription: (id: string) => post<ContestRun>(`/contest-subscriptions/${id}/discover`),
  subscriptionRuns: (id: string) => get<{ items: ContestRun[] }>(`/contest-subscriptions/${id}/runs`),
  createSource: (source: Omit<ContestSource, 'id' | 'created_at' | 'updated_at'>) => post<ContestSource>('/platform/contest-sources', source),
  setSource: (id: string, changes: Partial<ContestSource>) => request<ContestSource>(`/platform/contest-sources/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }),
  preflightSource: (id: string) => post<{ source: string; sample_count: number }>(`/platform/contest-sources/${id}/preflight`),
  ingestSource: (id: string) => post(`/platform/contest-sources/${id}/ingest`),
  tenantSources: () => get<{ items: TenantContestSource[] }>('/tenant/contest-sources'),
  suggestTenantSources: (region: string) => post<{ items: ContestSourceSuggestion[] }>('/tenant/contest-sources/suggestions', { region }),
  createTenantSource: (source: Omit<TenantContestSource, 'id' | 'enabled' | 'preflight_at' | 'created_at' | 'updated_at'>) => post<TenantContestSource>('/tenant/contest-sources', source),
  setTenantSource: (id: string, changes: Partial<TenantContestSource>) => request<TenantContestSource>(`/tenant/contest-sources/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }),
  deleteTenantSource: (id: string) => del(`/tenant/contest-sources/${id}`),
  preflightTenantSource: (id: string) => post<{ source_id: string; sample_count: number; sample_titles: string[] }>(`/tenant/contest-sources/${id}/preflight`),
  ingestTenantSource: (id: string) => post<ContestRun>(`/tenant/contest-sources/${id}/ingest`),
  tenantSourceRuns: (id: string) => get<{ items: ContestRun[] }>(`/tenant/contest-sources/${id}/runs`),
}
