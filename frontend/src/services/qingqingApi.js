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

function parseSseChunk(buffer) {
  const events = []
  const parts = buffer.split('\n\n')
  const rest = parts.pop() ?? ''
  for (const block of parts) {
    if (!block.trim()) continue
    let eventType = 'message'
    const dataLines = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) eventType = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
    if (!dataLines.length) continue
    try {
      events.push({ type: eventType, data: JSON.parse(dataLines.join('\n')) })
    } catch {
      events.push({ type: eventType, data: { raw: dataLines.join('\n') } })
    }
  }
  return { events, rest }
}

/**
 * Stream AgentRun events via fetch+SSE (supports Authorization header).
 * onEvent({ type, data }) for delta/step/run_*; resolves with final run when terminal.
 */
export async function streamAgentRun(runId, { onEvent, fetchImpl = apiFetch, signal } = {}) {
  if (!runId) throw new Error('缺少任务 ID')
  const response = await fetchImpl(`/api/v1/agent/runs/${encodeURIComponent(runId)}/events`, {
    method: 'GET',
    headers: { Accept: 'text/event-stream' },
    signal,
  })
  if (!response.ok) {
    const failure = await response.json().catch(() => ({}))
    throw new Error(failure.detail || `事件流打开失败（${response.status}）`)
  }
  if (!response.body) throw new Error('浏览器不支持流式响应')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalRun = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parsed = parseSseChunk(buffer)
    buffer = parsed.rest
    for (const event of parsed.events) {
      onEvent?.(event)
      const payload = event.data || {}
      if (payload.run && TERMINAL_RUN_STATUSES.has(payload.run.status)) {
        finalRun = payload.run
      }
      if (['run_completed', 'run_failed', 'run_paused', 'run_cancelled'].includes(event.type) || ['run_completed', 'run_failed', 'run_paused', 'run_cancelled'].includes(payload.type)) {
        if (payload.run) finalRun = payload.run
        try { await reader.cancel() } catch { /* ignore */ }
        if (finalRun) return finalRun
      }
    }
  }
  if (finalRun) return finalRun
  // Stream ended without terminal — fall back to one GET
  const fallback = await fetchImpl(`/api/v1/agent/runs/${encodeURIComponent(runId)}`)
  if (fallback.ok) return fallback.json()
  throw new Error('事件流已结束，但未拿到最终结果')
}

/** Prefer SSE; fall back to polling if stream fails. */
export async function followAgentRun(runId, { onEvent, onDelta, fetchImpl = apiFetch, signal } = {}) {
  try {
    return await streamAgentRun(runId, {
      fetchImpl,
      signal,
      onEvent: (event) => {
        onEvent?.(event)
        if (event.type === 'delta' && event.data?.delta) onDelta?.(event.data.delta, event.data)
      },
    })
  } catch {
    return pollAgentRun(runId, { fetchImpl })
  }
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
    const media = invocations.find((item) => item?.output && (
      item.output.url || item.output.artifact_id || item.output.content_url || item.output.audio_url || item.output.video_url
      || item.output.images
    ))
    if (media?.output?.content_url) return `创作完成。可访问：${media.output.content_url}`
    if (media?.output?.audio_url) return `创作完成。音频：${media.output.audio_url}`
    if (media?.output?.video_url) return `创作完成。视频：${media.output.video_url}`
    if (media?.output?.url) return `创作完成。产物链接：${media.output.url}`
    if (media?.output?.artifact_id) return `创作完成。作品 ID：${media.output.artifact_id}`
    if (Array.isArray(media?.output?.images) && media.output.images[0]?.url) {
      return `创作完成。图片：${media.output.images[0].url}`
    }
    if (run.summary) return String(run.summary)
    return `任务已完成（${run.id || ''}）。`.trim()
  }
  return run.message || run.summary || `任务状态：${status}`
}

/** Lightweight intent → capability for the dashboard composer. */
export function inferCapability(goal = '') {
  const text = String(goal).toLowerCase()
  if (/视频|短片|video|镜头|分镜/.test(text)) return 'video'
  if (/音乐|配乐|bgm|歌曲|music|旋律/.test(text)) return 'music'
  if (/语音|配音|朗读|tts|音色|旁白/.test(text)) return 'tts'
  if (/图|海报|视觉|插画|image|photo|写真|封面/.test(text)) return 'image'
  return 'chat'
}

export { SESSION_TOKEN_KEY, TERMINAL_RUN_STATUSES }
