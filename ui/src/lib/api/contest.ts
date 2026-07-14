import { del, get, post, request } from './fetch'

export type Contest = { id: string; title: string; source: string; source_name: string; origin: 'official' | 'web'; source_url: string; region: string; publish_date: string | null; apply_deadline: string | null; deadline_status: string; body_text?: string; apply_window_text?: string }
export type ContestList = { items: Contest[]; total: number; page: number; page_size: number }
export type ContestSource = { id: string; key: string; name: string; region: string; home_url: string; adapter_type: string; adapter_config: Record<string, string>; enabled: boolean; created_at: string; updated_at: string }
export type ContestSubscription = { id: string; keyword: string; enabled: boolean; last_run_at: string | null; created_at: string; updated_at: string }

export const contestApi = {
  list: (params: Record<string, string | number | boolean> = {}) => get<ContestList>('/contests', params),
  get: (id: string) => get<Contest>(`/contests/${id}`),
  sources: () => get<{ items: ContestSource[] }>('/contest-sources'),
  subscriptions: () => get<{ items: ContestSubscription[] }>('/contest-subscriptions'),
  addSubscription: (keyword: string) => post<ContestSubscription>('/contest-subscriptions', { keyword }),
  setSubscription: (id: string, enabled: boolean) => request<ContestSubscription>(`/contest-subscriptions/${id}`, { method: 'PATCH', body: JSON.stringify({ enabled }) }),
  deleteSubscription: (id: string) => del(`/contest-subscriptions/${id}`),
  createSource: (source: Omit<ContestSource, 'id' | 'created_at' | 'updated_at'>) => post<ContestSource>('/platform/contest-sources', source),
  setSource: (id: string, changes: Partial<ContestSource>) => request<ContestSource>(`/platform/contest-sources/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }),
  preflightSource: (id: string) => post<{ source: string; sample_count: number }>(`/platform/contest-sources/${id}/preflight`),
  ingestSource: (id: string) => post(`/platform/contest-sources/${id}/ingest`),
}
