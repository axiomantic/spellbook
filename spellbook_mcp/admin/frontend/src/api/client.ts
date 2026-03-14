interface FetchOptions {
  method?: string
  body?: unknown
  params?: Record<string, string | number | undefined>
}

export async function fetchApi<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { method = 'GET', body, params } = options

  let url = `/admin${path}`
  if (params) {
    const searchParams = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        searchParams.set(key, String(value))
      }
    }
    const qs = searchParams.toString()
    if (qs) url += `?${qs}`
  }

  const headers: Record<string, string> = {}
  if (body) headers['Content-Type'] = 'application/json'

  const response = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'same-origin',
  })

  if (!response.ok) {
    const respBody = await response.json().catch(() => ({ error: { code: 'UNKNOWN', message: response.statusText } }))
    const err = new Error(respBody.error?.message || `HTTP ${response.status}`) as Error & { code: string; details: unknown }
    err.code = respBody.error?.code || 'UNKNOWN'
    err.details = respBody.error?.details
    throw err
  }

  return response.json()
}
