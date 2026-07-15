const SESSION_TOKEN_KEY = 'qingqing_session_token'

const TERMINAL_RUN_STATUSES = new Set(['completed', 'failed', 'cancelled', 'paused'])

export function getSessionToken() {
  if (typeof window === 'undefined') return ''
  return window.sessionStorage.getItem(SESSION_TOKEN_KEY) || ''
}

export function setSessionToken(token) {
  if (typeof window === 'undefined') return
  if (token) window.sessionStorage.setItem(SESSION_TOKEN_KEY, token)
  else window.sessionStorage.removeItem(SESSION_TOKEN_KEY)
  window.dispatchEvent(new Event('qingqing-session-changed'))
}

export function apiFetch(input, init = {}) {
  const token = getSessionToken()
  const headers = new Headers(init.headers || {})
  const target = new URL(input, window.location.href)
  if (token && target.origin === window.location.origin && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return fetch(input, { ...init, headers })
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** Poll GET /api/v1/agent/runs/{id} until a terminal status or max attempts. */
export async function pollAgentRun(runId, { maxAttempts = 45, fetchImpl = apiFetch } = {}) {
  if (!runId) throw new Error('缺少任务 ID')
  let lastError = null
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (attempt > 0) {
      const delay = attempt < 3 ? 400 : attempt < 10 ? 1000 : 2500
      await sleep(delay)
    }
    try {
      const response = await fetchImpl(`/api/v1/agent/runs/${encodeURIComponent(runId)}`)
      if (!response.ok) {
        const failure = await response.json().catch(() => ({}))
        lastError = new Error(failure.detail || `查询任务失败（${response.status}）`)
        if (response.status === 404 || response.status === 401) throw lastError
        continue
      }
      const run = await response.json()
      if (TERMINAL_RUN_STATUSES.has(run.status)) return run
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error))
      if (lastError.message.includes('401') || lastError.message.includes('404')) throw lastError
    }
  }
  throw lastError || new Error('任务仍在执行，请稍后在任务列表查看结果')
}

/** Build a user-visible message from a terminal (or partial) agent run. */
export function formatRunMessage(run) {
  if (!run) return '任务状态未知'
  const status = run.status
  if (status === 'awaiting_approval') {
    return `任务预计消耗 ${run.estimated_cost ?? '—'} 额度，超过你的预算，需要确认后继续。`
  }
  if (status === 'planned' || status === 'running') {
    return `任务进行中（${run.id || '处理中'}）…`
  }
  if (status === 'cancelled') return `任务 ${run.id || ''} 已取消。`.trim()
  if (status === 'paused') {
    return `任务已暂停：${run.pause_reason || run.error_code || '等待处理'}。`
  }
  if (status === 'failed') {
    return `任务失败：${run.error_code || 'provider_execution_failed'}。可稍后重试。`
  }
  if (status === 'completed') {
    const invocations = Array.isArray(run.invocations) ? run.invocations : []
    const chat = invocations.find((item) => item?.capability === 'chat' && item?.output?.content)
      || invocations.find((item) => item?.output?.content)
    if (chat?.output?.content) return String(chat.output.content)
    const media = invocations.find((item) => item?.output && (item.output.url || item.output.artifact_id))
    if (media?.output?.url) return `创作完成。产物链接：${media.output.url}`
    if (media?.output?.artifact_id) return `创作完成。作品 ID：${media.output.artifact_id}`
    if (run.summary) return String(run.summary)
    return `任务已完成（${run.id || ''}）。`.trim()
  }
  return run.message || run.summary || `任务状态：${status}`
}

export { SESSION_TOKEN_KEY, TERMINAL_RUN_STATUSES }
