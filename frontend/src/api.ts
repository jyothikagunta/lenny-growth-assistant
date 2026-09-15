const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '')

export type Source = {
  episode_title: string
  guest_name: string | null
  source_url: string | null
}

export type Artifact = {
  artifact_type: 'markdown' | 'html'
  title: string
  content: string
  sources: Source[]
  is_untrusted: boolean
}

export type ChatResponse = {
  session_id: string
  answer: string
  sources: Source[]
  artifact: Artifact | null
}

export type RuntimeInfo = {
  provider: string
  model: string
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail || `Request failed (${response.status})`)
  }

  return response.json() as Promise<T>
}

export function createSession(): Promise<{ id: string }> {
  return request<{ id: string }>('/sessions', {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function sendChat(sessionId: string, query: string): Promise<ChatResponse> {
  return request<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, query, limit: 5 }),
  })
}

export function getRuntimeInfo(): Promise<RuntimeInfo> {
  return request<RuntimeInfo>('/runtime')
}
