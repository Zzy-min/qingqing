const SETTINGS_STORAGE_KEY = 'mmx_workbench_settings_v1'

const DEFAULT_SETTINGS = {
  theme: 'light',
  advancedModeEnabled: false,
  credentialPreference: 'platform_first',
  defaults: {
    photoModel: 'image-01',
    ttsModel: 'speech-2.8-hd',
    musicModel: 'music-2.6',
    videoModel: 'MiniMax-Hailuo-2.3'
  },
  defaultParams: {
    musicBpm: 120,
    videoDuration: 6,
    videoResolution: '768P'
  },
  providerApiKeys: {},
  providerBaseUrls: {},
  providerSecrets: {}
}

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function safeObject(value, fallback) {
  return value && typeof value === 'object' ? value : fallback
}

function sanitizeProviderMap(raw, fallback) {
  const input = safeObject(raw, fallback)
  const result = {}
  for (const [key, value] of Object.entries(input)) {
    if (typeof key === 'string' && typeof value === 'string') {
      result[key] = value
    }
  }
  return result
}

function sanitizeSettings(raw) {
  const input = safeObject(raw, {})
  const defaults = safeObject(input.defaults, {})
  const defaultParams = safeObject(input.defaultParams, {})

  return {
    theme: typeof input.theme === 'string' && input.theme.trim() ? input.theme.trim() : DEFAULT_SETTINGS.theme,
    advancedModeEnabled: input.advancedModeEnabled === true,
    credentialPreference: ['platform_first', 'byok_first', 'byok_only'].includes(input.credentialPreference)
      ? input.credentialPreference : DEFAULT_SETTINGS.credentialPreference,
    defaults: {
      photoModel: typeof defaults.photoModel === 'string' && defaults.photoModel.trim()
        ? defaults.photoModel.trim()
        : DEFAULT_SETTINGS.defaults.photoModel,
      ttsModel: typeof defaults.ttsModel === 'string' && defaults.ttsModel.trim()
        ? defaults.ttsModel.trim()
        : DEFAULT_SETTINGS.defaults.ttsModel,
      musicModel: typeof defaults.musicModel === 'string' && defaults.musicModel.trim()
        ? defaults.musicModel.trim()
        : DEFAULT_SETTINGS.defaults.musicModel,
      videoModel: typeof defaults.videoModel === 'string' && defaults.videoModel.trim()
        ? defaults.videoModel.trim()
        : DEFAULT_SETTINGS.defaults.videoModel
    },
    defaultParams: {
      musicBpm: Number.isFinite(Number(defaultParams.musicBpm))
        ? Math.max(40, Math.min(240, Number(defaultParams.musicBpm)))
        : DEFAULT_SETTINGS.defaultParams.musicBpm,
      videoDuration: Number.isFinite(Number(defaultParams.videoDuration))
        ? Math.max(3, Math.min(10, Number(defaultParams.videoDuration)))
        : DEFAULT_SETTINGS.defaultParams.videoDuration,
      videoResolution: typeof defaultParams.videoResolution === 'string' && defaultParams.videoResolution.trim()
        ? defaultParams.videoResolution.trim()
        : DEFAULT_SETTINGS.defaultParams.videoResolution
    },
    providerApiKeys: {},
    providerBaseUrls: {},
    providerSecrets: {}
  }
}

export function getDefaultWorkbenchSettings() {
  return sanitizeSettings(DEFAULT_SETTINGS)
}

export function loadWorkbenchSettings() {
  if (!canUseStorage()) {
    return getDefaultWorkbenchSettings()
  }
  try {
    const raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY)
    if (!raw) return getDefaultWorkbenchSettings()
    const sanitized = sanitizeSettings(JSON.parse(raw))
    // One-way migration: remove all legacy browser-stored credential material.
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(sanitized))
    window.localStorage.removeItem('apiKey')
    window.localStorage.removeItem('minimaxApiKey')
    window.localStorage.removeItem('providerApiKeys')
    window.localStorage.removeItem('providerBaseUrls')
    window.localStorage.removeItem('providerSecrets')
    return sanitized
  } catch {
    return getDefaultWorkbenchSettings()
  }
}

export function saveWorkbenchSettings(nextSettings) {
  const sanitized = sanitizeSettings(nextSettings)
  if (!canUseStorage()) return sanitized
  try {
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(sanitized))
    window.localStorage.removeItem('apiKey')
    window.localStorage.removeItem('minimaxApiKey')
    window.localStorage.removeItem('providerApiKeys')
    window.localStorage.removeItem('providerBaseUrls')
    window.localStorage.removeItem('providerSecrets')
  } catch {
    // Ignore write failure for private mode or storage quota.
  }
  return sanitized
}

export function patchWorkbenchSettings(partial) {
  const current = loadWorkbenchSettings()
  const merged = {
    ...current,
    ...(partial || {}),
    defaults: {
      ...current.defaults,
      ...(partial?.defaults || {})
    },
    defaultParams: {
      ...current.defaultParams,
      ...(partial?.defaultParams || {})
    },
    providerApiKeys: {
      ...(current.providerApiKeys || {}),
      ...(partial?.providerApiKeys || {})
    },
    providerBaseUrls: {
      ...(current.providerBaseUrls || {}),
      ...(partial?.providerBaseUrls || {})
    },
    providerSecrets: {
      ...(current.providerSecrets || {}),
      ...(partial?.providerSecrets || {})
    }
  }
  return saveWorkbenchSettings(merged)
}

export function getApiKeySourceLabel() {
  return '轻青服务端安全托管'
}

export { SETTINGS_STORAGE_KEY }
