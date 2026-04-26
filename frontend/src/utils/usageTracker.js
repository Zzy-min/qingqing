const USAGE_EVENTS_KEY = 'mmx_usage_events_v1'
const RECENT_GENERATIONS_KEY = 'mmx_recent_generations_v1'
const MAX_EVENTS = 1200
const MAX_RECENTS = 120
const UPDATE_EVENT = 'mmx-usage-updated'

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function safeReadArray(key) {
  if (!canUseStorage()) return []
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function safeWriteArray(key, value) {
  if (!canUseStorage()) return
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Ignore storage failures.
  }
}

function publishUpdate() {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(UPDATE_EVENT))
}

function normalizeTimestamp(value) {
  const date = value ? new Date(value) : new Date()
  return Number.isNaN(date.getTime()) ? new Date().toISOString() : date.toISOString()
}

export function trackUsageEvent(event) {
  const payload = {
    module: typeof event?.module === 'string' ? event.module : 'other',
    action: typeof event?.action === 'string' ? event.action : 'unknown',
    status: event?.status === 'error' ? 'error' : 'success',
    durationMs: Number.isFinite(Number(event?.durationMs)) ? Number(event.durationMs) : 0,
    timestamp: normalizeTimestamp(event?.timestamp),
    errorCode: event?.errorCode || '',
    note: typeof event?.note === 'string' ? event.note : ''
  }
  const next = [...safeReadArray(USAGE_EVENTS_KEY), payload].slice(-MAX_EVENTS)
  safeWriteArray(USAGE_EVENTS_KEY, next)
  publishUpdate()
  return payload
}

export function trackRecentGeneration(item) {
  const payload = {
    module: typeof item?.module === 'string' ? item.module : 'other',
    title: typeof item?.title === 'string' && item.title.trim() ? item.title.trim() : '新任务',
    status: item?.status === 'error' ? 'error' : 'success',
    timestamp: normalizeTimestamp(item?.timestamp),
    summary: typeof item?.summary === 'string' ? item.summary : '',
    taskId: typeof item?.taskId === 'string' ? item.taskId : ''
  }
  const next = [payload, ...safeReadArray(RECENT_GENERATIONS_KEY)].slice(0, MAX_RECENTS)
  safeWriteArray(RECENT_GENERATIONS_KEY, next)
  publishUpdate()
  return payload
}

export function readUsageEvents() {
  return safeReadArray(USAGE_EVENTS_KEY)
}

export function readRecentGenerations(limit = 8) {
  const normalizedLimit = Math.max(1, Math.min(50, Number(limit) || 8))
  return safeReadArray(RECENT_GENERATIONS_KEY).slice(0, normalizedLimit)
}

function startOfDay(date) {
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  return d
}

function formatDayLabel(date) {
  return `${date.getMonth() + 1}/${date.getDate()}`
}

export function buildUsageAnalytics(events) {
  const list = Array.isArray(events) ? events : []
  const now = new Date()
  const todayStart = startOfDay(now).getTime()
  const weekStart = todayStart - 6 * 24 * 60 * 60 * 1000

  const dailyBuckets = []
  for (let i = 6; i >= 0; i -= 1) {
    const d = new Date(todayStart - i * 24 * 60 * 60 * 1000)
    dailyBuckets.push({
      dateKey: startOfDay(d).toISOString(),
      label: formatDayLabel(d),
      count: 0
    })
  }
  const bucketMap = Object.fromEntries(dailyBuckets.map((b) => [b.dateKey, b]))

  const moduleCounts = {}
  let todayCount = 0
  let weekCount = 0
  let errorCount = 0

  for (const item of list) {
    const ts = new Date(item?.timestamp || '').getTime()
    if (Number.isNaN(ts)) continue
    const moduleName = typeof item?.module === 'string' ? item.module : 'other'
    moduleCounts[moduleName] = (moduleCounts[moduleName] || 0) + 1

    const dayKey = startOfDay(ts).toISOString()
    if (bucketMap[dayKey]) bucketMap[dayKey].count += 1

    if (ts >= todayStart) todayCount += 1
    if (ts >= weekStart) weekCount += 1
    if (item?.status === 'error') errorCount += 1
  }

  const moduleDistribution = Object.entries(moduleCounts)
    .map(([module, count]) => ({ module, count }))
    .sort((a, b) => b.count - a.count)

  return {
    todayCount,
    weekCount,
    errorCount,
    dailyTrend: dailyBuckets,
    moduleDistribution
  }
}

export { UPDATE_EVENT, USAGE_EVENTS_KEY, RECENT_GENERATIONS_KEY }
