const BASE = '/api'

export async function createTask(query, maxIterations = 2) {
  const resp = await fetch(`${BASE}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, max_iterations: maxIterations }),
  })
  if (!resp.ok) throw new Error(`Create task failed: ${resp.status}`)
  return resp.json()
}

export async function getTask(taskId) {
  const resp = await fetch(`${BASE}/tasks/${taskId}`)
  if (!resp.ok) throw new Error(`Get task failed: ${resp.status}`)
  return resp.json()
}

export async function listTasks(limit = 20) {
  const resp = await fetch(`${BASE}/tasks?limit=${limit}`)
  if (!resp.ok) throw new Error(`List tasks failed: ${resp.status}`)
  return resp.json()
}

export async function deleteTask(taskId) {
  const resp = await fetch(`${BASE}/tasks/${taskId}`, { method: 'DELETE' })
  if (!resp.ok && resp.status !== 204) throw new Error(`Delete task failed: ${resp.status}`)
}

export function subscribeToTask(taskId, callbacks) {
  const source = new EventSource(`${BASE}/tasks/${taskId}/stream`)

  source.addEventListener('task_started', (e) => {
    if (callbacks.onTaskStarted) callbacks.onTaskStarted(JSON.parse(e.data))
  })

  source.addEventListener('node_start', (e) => {
    if (callbacks.onNodeStart) callbacks.onNodeStart(JSON.parse(e.data))
  })

  source.addEventListener('node_done', (e) => {
    if (callbacks.onNodeDone) callbacks.onNodeDone(JSON.parse(e.data))
  })

  source.addEventListener('review_required', (e) => {
    if (callbacks.onReviewRequired) callbacks.onReviewRequired(JSON.parse(e.data))
  })

  source.addEventListener('done', (e) => {
    if (callbacks.onDone) callbacks.onDone(JSON.parse(e.data))
    source.close()
  })

  source.addEventListener('error', (e) => {
    if (callbacks.onError) callbacks.onError(e)
    source.close()
  })

  return source
}
