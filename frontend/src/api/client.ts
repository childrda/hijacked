const API_BASE = '/api';

type RequestOptions = RequestInit & { skipAuthRedirect?: boolean };

async function apiFetch(path: string, options: RequestOptions = {}) {
  const { skipAuthRedirect, ...init } = options;
  const r = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    ...init,
  });
  if (r.status === 401 && !skipAuthRedirect && window.location.pathname !== '/login') {
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  return r;
}

export type DashboardMetrics = {
  critical_alerts_count: number;
  recent_events_count: number;
  trend_points: { date: string; count: number }[];
  agent_status: string;
};

export type FlaggedRow = {
  id: number;
  target_email: string;
  detection_time: string | null;
  event_type: string;
  details: string;
  risk_level: string;
  score: number;
  status: string;
  assigned_to?: string | null;
};

export type AuthUser = { username: string; role: string };

export async function getMetrics(window = '24h'): Promise<DashboardMetrics> {
  const r = await apiFetch(`/dashboard/metrics?window=${window}`);
  if (!r.ok) throw new Error('Failed to fetch metrics');
  return r.json();
}

export async function getAlerts(params: { status?: string; window?: string; search?: string } = {}): Promise<FlaggedRow[]> {
  const sp = new URLSearchParams();
  if (params.status) sp.set('status', params.status);
  if (params.window) sp.set('window', params.window);
  if (params.search) sp.set('search', params.search);
  const r = await apiFetch(`/alerts?${sp}`);
  if (!r.ok) throw new Error('Failed to fetch alerts');
  return r.json();
}

export async function dismissAlert(id: number): Promise<{ ok: boolean }> {
  const r = await apiFetch(`/alerts/${id}/dismiss`, { method: 'POST' });
  if (!r.ok) throw new Error('Failed to dismiss');
  return r.json();
}

export async function bulkDismiss(alertIds: number[]): Promise<{ dismissed: number }> {
  const r = await apiFetch(`/alerts/bulk-dismiss`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alert_ids: alertIds }),
  });
  if (!r.ok) throw new Error('Failed to bulk dismiss');
  return r.json();
}

export async function disableAccount(alertIds: number[], reason = ''): Promise<{ actions: unknown[]; mode: string }> {
  const r = await apiFetch(`/actions/disable-account`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alert_ids: alertIds, reason }),
  });
  if (!r.ok) throw new Error('Failed to disable account');
  return r.json();
}

export async function disableAccountByEmail(userEmail: string, reason = ''): Promise<{ actions: unknown[]; mode: string }> {
  const r = await apiFetch(`/actions/disable-account-by-email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_email: userEmail, reason }),
  });
  if (!r.ok) throw new Error('Failed to disable account');
  return r.json();
}

export async function login(username: string, password: string): Promise<AuthUser> {
  const r = await apiFetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
    skipAuthRedirect: true,
  });
  if (!r.ok) throw new Error('Invalid credentials');
  return r.json();
}

export async function logout(): Promise<void> {
  await apiFetch('/auth/logout', { method: 'POST', skipAuthRedirect: true });
}

export async function me(): Promise<AuthUser> {
  const r = await apiFetch('/auth/me', { skipAuthRedirect: true });
  if (!r.ok) throw new Error('Not authenticated');
  return r.json();
}

export async function getAlertDetail(id: number): Promise<any> {
  const r = await apiFetch(`/alerts/${id}`);
  if (!r.ok) throw new Error('Failed to fetch alert detail');
  return r.json();
}

export async function updateAlertStatus(id: number, status: string): Promise<{ ok: boolean }> {
  const r = await apiFetch(`/alerts/${id}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!r.ok) throw new Error('Failed to update status');
  return r.json();
}

export async function updateAlertNotes(id: number, notes: string): Promise<{ ok: boolean }> {
  const r = await apiFetch(`/alerts/${id}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  });
  if (!r.ok) throw new Error('Failed to update notes');
  return r.json();
}

export type MailboxFilterRow = {
  id: number;
  user_email: string;
  gmail_filter_id: string;
  fingerprint: string;
  criteria_json: Record<string, unknown> | null;
  action_json: Record<string, unknown> | null;
  is_risky: boolean;
  risk_reasons_json: string[] | null;
  status: string;
  first_seen_at: string | null;
  last_seen_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  removed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export async function listFilters(params: { user_email?: string; status?: string; risky_only?: boolean } = {}): Promise<MailboxFilterRow[]> {
  const sp = new URLSearchParams();
  if (params.user_email) sp.set('user_email', params.user_email);
  if (params.status) sp.set('status', params.status);
  if (params.risky_only) sp.set('risky_only', 'true');
  const r = await apiFetch(`/filters?${sp}`);
  if (!r.ok) throw new Error('Failed to fetch filters');
  return r.json();
}

export async function getFilter(id: number): Promise<MailboxFilterRow> {
  const r = await apiFetch(`/filters/${id}`);
  if (!r.ok) throw new Error('Failed to fetch filter');
  return r.json();
}

export async function approveFilter(id: number): Promise<MailboxFilterRow> {
  const r = await apiFetch(`/filters/${id}/approve`, { method: 'POST' });
  if (!r.ok) throw new Error('Failed to approve filter');
  return r.json();
}

export async function ignoreFilter(id: number): Promise<MailboxFilterRow> {
  const r = await apiFetch(`/filters/${id}/ignore`, { method: 'POST' });
  if (!r.ok) throw new Error('Failed to ignore filter');
  return r.json();
}

export async function blockFilter(id: number): Promise<MailboxFilterRow> {
  const r = await apiFetch(`/filters/${id}/block`, { method: 'POST' });
  if (!r.ok) throw new Error('Failed to block filter');
  return r.json();
}

export async function resetFilterStatus(id: number): Promise<MailboxFilterRow> {
  const r = await apiFetch(`/filters/${id}/reset-status`, { method: 'POST' });
  if (!r.ok) throw new Error('Failed to reset filter status');
  return r.json();
}

export async function rescanFilters(user_email: string): Promise<{ ok: boolean; filters_seen: number; new_alerts: number }> {
  const r = await apiFetch('/filters/rescan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_email }),
  });
  if (!r.ok) throw new Error('Failed to rescan');
  return r.json();
}

export type IngestLogRow = {
  id: number;
  source: string;
  event_time: string | null;
  actor_email: string | null;
  target_email: string | null;
  ip: string | null;
  user_agent: string | null;
  geo: string | null;
  ip_address: string | null;
  region_code: string | null;
  subdivision_code: string | null;
  ip_asn: string | number | null;
  payload_json: Record<string, unknown> | null;
  created_at: string | null;
};

export async function getIngestLogs(params: {
  source?: string;
  target_email?: string;
  since?: string;
  limit?: number;
} = {}): Promise<IngestLogRow[]> {
  const sp = new URLSearchParams();
  if (params.source) sp.set('source', params.source);
  if (params.target_email) sp.set('target_email', params.target_email);
  if (params.since) sp.set('since', params.since);
  if (params.limit != null) sp.set('limit', String(params.limit));
  const r = await apiFetch(`/logs/ingest?${sp}`);
  if (!r.ok) throw new Error('Failed to fetch ingest logs');
  return r.json();
}

export type FilterScanLogRow = {
  id: number;
  user_email: string;
  scanned_at: string | null;
  filters_count: number;
  success: boolean;
  error_message: string | null;
  created_at: string | null;
};

export async function getFilterScanLog(params: { user_email?: string; limit?: number } = {}): Promise<FilterScanLogRow[]> {
  const sp = new URLSearchParams();
  if (params.user_email) sp.set('user_email', params.user_email);
  if (params.limit != null) sp.set('limit', String(params.limit));
  const r = await apiFetch(`/filters/scan-log?${sp}`);
  if (!r.ok) throw new Error('Failed to fetch filter scan log');
  return r.json();
}
