const BASE_URL = 'http://localhost:8000/api/v1'

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const error = new Error(body.detail || `HTTP ${response.status}`)
    error.status = response.status
    throw error
  }

  return response.json()
}

export function get(path) {
  return request(path)
}

export function post(path, data) {
  return request(path, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
