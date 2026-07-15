import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { tokenPlanApi } from '../services/api'
import { apiFetch, getSessionToken } from '../services/qingqingApi'
import {
  getApiKeySourceLabel,
  loadWorkbenchSettings,
  patchWorkbenchSettings,
  saveWorkbenchSettings
} from '../utils/workbenchSettings'
import { buildUsageAnalytics, readRecentGenerations, readUsageEvents, UPDATE_EVENT } from '../utils/usageTracker'

const WorkbenchContext = createContext(null)

const MODULES = [
  {
    id: 'photo',
    path: '/photo',
    title: '照片编辑',
    subtitle: 'Photo Editing',
    desc: '图像生成与滤镜',
    icon: '🖼️',
    tone: 'module-photo'
  },
  {
    id: 'voice',
    path: '/voice',
    title: '语音合成',
    subtitle: 'Voice Synthesis',
    desc: '高质量多语种 TTS',
    icon: '🎙️',
    tone: 'module-voice'
  },
  {
    id: 'music',
    path: '/music',
    title: '音乐生成',
    subtitle: 'Music Generation',
    desc: '灵感旋律即时创作',
    icon: '🎵',
    tone: 'module-music'
  },
  {
    id: 'video',
    path: '/video',
    title: '视频生成',
    subtitle: 'Video Generation',
    desc: '文生视频与镜头控制',
    icon: '🎬',
    tone: 'module-video'
  }
]

const NAV_GROUPS = [
  {
    id: 'create',
    title: '创作入口',
    items: [
      { id: 'dashboard', label: '工作台', icon: '🏠', path: '/dashboard' },
      { id: 'chat', label: 'Chat', icon: '💬', path: '/chat' },
      { id: 'photo', label: '照片编辑', icon: '🖼️', path: '/photo' },
      { id: 'voice', label: '语音合成', icon: '🎙️', path: '/voice' },
      { id: 'music', label: '音乐生成', icon: '🎵', path: '/music' },
      { id: 'video', label: '视频生成', icon: '🎬', path: '/video' }
    ]
  },
  {
    id: 'ops',
    title: '运营与文档',
    items: [
      { id: 'token', label: 'Token Plan', icon: '🧾', path: '/token' },
      { id: 'usage', label: '用量分析', icon: '📊', path: '/usage' },
      { id: 'help', label: '帮助文档', icon: '📘', path: '/help' },
      { id: 'api-docs', label: 'API 文档', icon: '🧩', path: '/api-docs' },
      { id: 'settings', label: '设置', icon: '⚙️', path: '/settings' }
    ]
  }
]

function formatNumber(value) {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return '-'
  return numeric.toLocaleString('zh-CN')
}

function parseTokenPlan(data) {
  if (!data) return null

  const textUsage = Number(data.text_window_usage ?? 0)
  const textLimit = Number(data.text_window_limit ?? 0)
  const nonTextUsage = Number(data.non_text_daily_usage ?? 0)
  const nonTextLimit = Number(data.non_text_daily_limit ?? 0)
  const textRatio = textLimit > 0 ? Math.min(100, (textUsage / textLimit) * 100) : 0
  const nonTextRatio = nonTextLimit > 0 ? Math.min(100, (nonTextUsage / nonTextLimit) * 100) : 0

  const itemsByCategory = {}
  const nonTextItems = Array.isArray(data.non_text_daily_items)
    ? data.non_text_daily_items.map((item) => {
      const usage = Number(item.usage ?? 0)
      const limit = Number(item.limit ?? 0)
      const ratio = limit > 0 ? Math.min(100, (usage / limit) * 100) : 0
      const remaining = Number(item.remaining ?? (limit > 0 ? Math.max(limit - usage, 0) : 0))
      const remainingDisplay = Number.isFinite(remaining) ? remaining : '-'
      const rawCategory = typeof item.category === 'string' ? item.category.trim().toLowerCase() : 'other'
      const category = ['tts', 'video', 'music', 'photo'].includes(rawCategory) ? rawCategory : 'other'
      const normalized = { ...item, usage, limit, ratio, remaining, remainingDisplay, category }
      if (!itemsByCategory[category]) itemsByCategory[category] = []
      itemsByCategory[category].push(normalized)
      return normalized
    })
    : []

  return {
    textUsage,
    textLimit,
    nonTextUsage,
    nonTextLimit,
    textRatio,
    nonTextRatio,
    nonTextItems,
    itemsByCategory,
    textUsageDisplay: formatNumber(textUsage),
    textLimitDisplay: formatNumber(textLimit),
    nonTextUsageDisplay: formatNumber(nonTextUsage),
    nonTextLimitDisplay: formatNumber(nonTextLimit)
  }
}

export function WorkbenchProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const [settings, setSettings] = useState(() => loadWorkbenchSettings())
  const [settingsValidation, setSettingsValidation] = useState({
    checkedAt: null,
    ok: false,
    message: ''
  })
  const [tokenPlanState, setTokenPlanState] = useState({
    loading: true,
    error: '',
    data: null,
    updatedAt: null
  })
  const [usageVersion, setUsageVersion] = useState(0)

  const pushToast = useCallback((type, message) => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    setToasts((prev) => [...prev, { id, type, message }])
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((item) => item.id !== id))
    }, 3600)
  }, [])

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((item) => item.id !== id))
  }, [])

  const fetchTokenPlanRemains = useCallback(async ({ silent = false } = {}) => {
    setTokenPlanState((prev) => ({ ...prev, loading: true, error: '' }))
    try {
      const data = await tokenPlanApi.remains()
      setTokenPlanState({
        loading: false,
        error: '',
        data,
        updatedAt: new Date()
      })
      if (!silent) {
        pushToast('success', 'Token Plan 配额已刷新')
      }
      return { ok: true, data }
    } catch (error) {
      const detail = error?.response?.data?.detail || error?.message || '加载失败'
      setTokenPlanState({
        loading: false,
        error: detail,
        data: null,
        updatedAt: new Date()
      })
      if (!silent) {
        pushToast('error', `Token Plan 配额加载失败: ${detail}`)
      }
      return { ok: false, message: detail }
    }
  }, [pushToast])

  const validateApiKey = useCallback(async () => {
    const checkedAt = new Date()
    const result = await fetchTokenPlanRemains({ silent: true })
    if (result.ok) {
      setSettingsValidation({
        checkedAt,
        ok: true,
        message: 'API Key 校验通过，可正常读取 Token Plan 配额。'
      })
      pushToast('success', 'API Key 校验通过')
      return true
    }
    const msg = result.message || '校验失败'
    setSettingsValidation({
      checkedAt,
      ok: false,
      message: `API Key 校验失败：${msg}`
    })
    pushToast('error', `API Key 校验失败：${msg}`)
    return false
  }, [fetchTokenPlanRemains, pushToast])

  useEffect(() => {
    let active = true
    const hydrateServerPreferences = async () => {
      if (!getSessionToken()) return
      try {
        const response = await apiFetch('/api/v1/me/preferences')
        if (!response.ok) return
        const preferences = await response.json()
        if (!active) return
        setSettings((current) => saveWorkbenchSettings({
          ...current,
          advancedModeEnabled: preferences.advanced_mode_enabled === true,
          credentialPreference: preferences.credential_preference || 'platform_first'
        }))
      } catch {
        // Keep non-sensitive local display preferences when the account is offline.
      }
    }
    void hydrateServerPreferences()
    window.addEventListener('qingqing-session-changed', hydrateServerPreferences)
    return () => {
      active = false
      window.removeEventListener('qingqing-session-changed', hydrateServerPreferences)
    }
  }, [])

  useEffect(() => {
    void fetchTokenPlanRemains({ silent: true })
    const timer = window.setInterval(() => {
      void fetchTokenPlanRemains({ silent: true })
    }, 5 * 60 * 1000)
    return () => window.clearInterval(timer)
  }, [fetchTokenPlanRemains])

  useEffect(() => {
    const listener = () => setUsageVersion((value) => value + 1)
    window.addEventListener(UPDATE_EVENT, listener)
    return () => window.removeEventListener(UPDATE_EVENT, listener)
  }, [])

  useEffect(() => {
    const root = document.documentElement
    const theme = settings?.theme || 'light'
    const resolvedTheme = theme === 'auto'
      ? (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : theme
    root.setAttribute('data-theme', resolvedTheme)
  }, [settings?.theme])

  const tokenPlanSummary = useMemo(() => parseTokenPlan(tokenPlanState.data), [tokenPlanState.data])
  const usageEvents = useMemo(() => readUsageEvents(), [usageVersion])
  const usageAnalytics = useMemo(() => buildUsageAnalytics(usageEvents), [usageEvents])
  const recentGenerations = useMemo(() => readRecentGenerations(10), [usageVersion])
  const apiKeySource = useMemo(() => getApiKeySourceLabel(settings), [settings])

  const updateSettings = useCallback((partial) => {
    const next = patchWorkbenchSettings(partial)
    setSettings(next)
    return next
  }, [])

  const replaceSettings = useCallback((nextSettings) => {
    const next = saveWorkbenchSettings(nextSettings)
    setSettings(next)
    return next
  }, [])

  const value = useMemo(() => ({
    modules: MODULES,
    navGroups: NAV_GROUPS,
    toasts,
    pushToast,
    dismissToast,
    tokenPlanState,
    tokenPlanSummary,
    fetchTokenPlanRemains,
    settings,
    updateSettings,
    replaceSettings,
    settingsValidation,
    validateApiKey,
    usageEvents,
    usageAnalytics,
    recentGenerations,
    apiKeySource
  }), [
    apiKeySource,
    dismissToast,
    fetchTokenPlanRemains,
    pushToast,
    recentGenerations,
    replaceSettings,
    settings,
    settingsValidation,
    toasts,
    tokenPlanState,
    tokenPlanSummary,
    updateSettings,
    usageAnalytics,
    usageEvents
  ])

  return (
    <WorkbenchContext.Provider value={value}>
      {children}
    </WorkbenchContext.Provider>
  )
}

export function useWorkbench() {
  const context = useContext(WorkbenchContext)
  if (!context) {
    throw new Error('useWorkbench must be used within WorkbenchProvider')
  }
  return context
}
