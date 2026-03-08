const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('access_token')
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function apiFetch(path: string, options?: RequestInit) {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, err.detail ?? 'Request failed')
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  register: (data: { email: string; password: string; full_name: string }) =>
    apiFetch('/auth/register', { method: 'POST', body: JSON.stringify(data) }),

  login: (data: { email: string; password: string }) =>
    apiFetch('/auth/login', { method: 'POST', body: JSON.stringify(data) }),

  getDomains: () => apiFetch('/catalog/domains'),

  getDatasets: () => apiFetch('/catalog'),

  createJob: (data: { domain_id: number; row_count: number }) =>
    apiFetch('/jobs', { method: 'POST', body: JSON.stringify(data) }),

  listJobs: () => apiFetch('/jobs'),

  getJob: (id: number) => apiFetch(`/jobs/${id}`),

  getJobResult: (id: number) => apiFetch(`/jobs/${id}/result`),
}
