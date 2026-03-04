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
