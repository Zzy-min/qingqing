import axios from 'axios'
import { getSessionToken } from './qingqingApi'
import { trackRecentGeneration, trackUsageEvent } from '../utils/usageTracker'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000
})

api.interceptors.request.use((config) => {
  const token = getSessionToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

function safeText(value, fallback = '') {
  if (typeof value === 'string' && value.trim()) return value.trim()
  return fallback
}

async function trackedRequest({ module, action, request, onSuccess }) {
  const startedAt = Date.now()
  try {
    const response = await request()
    const data = response.data
    trackUsageEvent({
      module,
      action,
      status: 'success',
      durationMs: Date.now() - startedAt
    })
    if (typeof onSuccess === 'function') {
      onSuccess(data)
    }
    return data
  } catch (error) {
    const status = error?.response?.status
    trackUsageEvent({
      module,
      action,
      status: 'error',
      durationMs: Date.now() - startedAt,
      errorCode: Number.isFinite(Number(status)) ? String(status) : '',
      note: safeText(error?.response?.data?.detail, safeText(error?.message))
    })
    throw error
  }
}

function recordRecent(module, title, payload) {
  trackRecentGeneration({
    module,
    title,
    status: payload?.success === false ? 'error' : 'success',
    summary: safeText(payload?.message),
    taskId: safeText(payload?.task_id)
  })
}

export const imageApi = {
  generate: async (params) => trackedRequest({
    module: 'photo',
    action: 'generate',
    request: () => api.post('/generate', params),
    onSuccess: (data) => {
      if (data?.success) recordRecent('photo', '照片生成', data)
    }
  }),

  process: async (params) => trackedRequest({
    module: 'photo',
    action: 'process',
    request: () => api.post('/process', params),
    onSuccess: (data) => {
      if (data?.success) recordRecent('photo', '照片处理', data)
    }
  })
}

export const ttsApi = {
  synthesize: async (params) => trackedRequest({
    module: 'voice',
    action: 'synthesize',
    request: () => api.post('/tts/synthesize', params),
    onSuccess: (data) => {
      if (data?.success) recordRecent('voice', '语音合成', data)
    }
  }),
  voices: async () => trackedRequest({
    module: 'voice',
    action: 'voices',
    request: () => api.get('/tts/voices')
  })
}

export const musicApi = {
  generate: async (params) => trackedRequest({
    module: 'music',
    action: 'generate',
    request: () => api.post('/music/generate', params, { timeout: 300000 }),
    onSuccess: (data) => {
      if (data?.success) recordRecent('music', '音乐生成', data)
    }
  }),
  cover: async (params) => trackedRequest({
    module: 'music',
    action: 'cover',
    request: () => api.post('/music/cover', params, { timeout: 300000 }),
    onSuccess: (data) => {
      if (data?.success) recordRecent('music', '音乐翻唱', data)
    }
  }),
  task: async (taskId) => trackedRequest({
    module: 'music',
    action: 'task',
    request: () => api.get(`/music/task/${encodeURIComponent(taskId)}`, { timeout: 180000 }),
    onSuccess: (data) => {
      if (data?.success && (data?.audio_data || data?.audio_url)) {
        recordRecent('music', '音乐任务完成', data)
      }
    }
  })
}

export const videoApi = {
  generate: async (params) => trackedRequest({
    module: 'video',
    action: 'generate',
    request: () => api.post('/video/generate', params, { timeout: 660000 }),
    onSuccess: (data) => {
      if (data?.success) recordRecent('video', '视频生成', data)
    }
  }),
  task: async (taskId) => trackedRequest({
    module: 'video',
    action: 'task',
    request: () => api.post('/video/task', { task_id: taskId }, { timeout: 180000 }),
    onSuccess: (data) => {
      if (data?.success && (data?.video_data || data?.video_url)) {
        recordRecent('video', '视频任务完成', data)
      }
    }
  })
}

export const tokenPlanApi = {
  remains: async () => trackedRequest({
    module: 'token',
    action: 'remains',
    request: () => api.get('/token-plan/remains')
  })
}

export default api
