import { useCallback, useEffect, useRef, useState } from 'react'
import { musicApi, ttsApi, videoApi } from '../services/api'

const MUSIC_MODELS = [
  { id: 'music-2.6', label: 'Music 2.6', desc: 'Token Plan 推荐模型' }
]

const VIDEO_MODELS = [
  { id: 'MiniMax-Hailuo-2.3', label: 'Hailuo 2.3', desc: '文生视频，质量优先' },
  { id: 'MiniMax-Hailuo-2.3-Fast', label: 'Hailuo 2.3 Fast', desc: '图生视频，速度优先' },
  { id: 'MiniMax-Hailuo-02', label: 'Hailuo 02', desc: '首尾帧插帧' },
  { id: 'S2V-01', label: 'S2V-01', desc: '角色一致性' }
]

const VIDEO_RESOLUTIONS = ['512P', '720P', '768P', '1080P']
const VIDEO_MOTION_PROMPTS = [
  '镜头缓慢推进',
  '镜头环绕主体',
  '低角度仰拍',
  '手持纪录片感',
  '电影级景深',
  '主体轻微转身',
  '背景自然虚化',
  '光线从侧面扫过',
  '慢动作',
  '航拍俯视',
  '平滑横移',
  '雨夜反光',
  '体积光',
  '风吹发丝',
  '定格转场'
]

const LANGUAGES = [
  { id: '', label: '自动检测' },
  { id: 'zh', label: '中文' },
  { id: 'en', label: '英文' },
  { id: 'ja', label: '日文' },
  { id: 'ko', label: '韩文' },
  { id: 'fr', label: '法文' },
  { id: 'de', label: '德文' },
  { id: 'es', label: '西班牙文' }
]

const VIDEO_TASK_HISTORY_STORAGE_KEY = 'video_task_history_v1'
const VIDEO_TASK_HISTORY_MAX_COUNT = 20
const MUSIC_POLL_INTERVAL_MS = 8000
const MUSIC_POLL_MAX_RETRIES = 3
const VIDEO_POLL_MAX_RETRIES = 3

const BUILTIN_TTS_VOICE_LABELS = {
  English_expressive_narrator: 'English Narrator',
  'male-qn-qingse': '中文男声',
  'male-qn-jingying': '中文男声(精英)',
  'male-qn-badao': '中文男声(霸道)',
  'male-qn-daxuesheng': '中文男声(大学生)',
  'female-shaonv': '中文女声(少女)',
  'female-yujie': '中文女声(愉悦)',
  'female-chengshu': '中文女声(成熟)',
  'female-tianmei': '中文女声(甜美)'
}

const BUILTIN_TTS_VOICE_IDS = Object.keys(BUILTIN_TTS_VOICE_LABELS)
const DEFAULT_CN_FAVORITE_VOICES = [
  'male-qn-qingse',
  'male-qn-jingying',
  'female-yujie',
  'female-chengshu',
  'female-tianmei',
  'male-qn-daxuesheng'
]
const CN_FAVORITE_STORAGE_KEY = 'tts_cn_favorite_voices_v1'

function formatVoiceLabel(voiceId, voiceMetaMap = {}) {
  if (!voiceId) return ''
  const officialName = voiceMetaMap?.[voiceId]?.voice_name
  if (officialName) return officialName
  if (BUILTIN_TTS_VOICE_LABELS[voiceId]) return BUILTIN_TTS_VOICE_LABELS[voiceId]
  return voiceId.replaceAll('_', ' ')
}

function getErrorMessage(error, fallback = '请求失败') {
  return error?.response?.data?.detail || error?.message || fallback
}

function makeTimestamp() {
  return new Date().toISOString().replace(/[:.]/g, '-')
}

function extensionFromSource(source, fallback) {
  if (typeof source !== 'string') return fallback
  const dataMatch = source.match(/^data:([^;]+);/)
  if (dataMatch) {
    const subtype = dataMatch[1].split('/')[1]
    return subtype === 'mpeg' ? 'mp3' : subtype || fallback
  }
  const clean = source.split('?')[0].split('#')[0]
  const ext = clean.includes('.') ? clean.split('.').pop().toLowerCase() : ''
  return ext && ext.length <= 5 ? ext : fallback
}

async function downloadGeneratedFile(source, filename, onNotify) {
  if (!source) return
  try {
    const response = await fetch(source)
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    URL.revokeObjectURL(url)
  } catch {
    const anchor = document.createElement('a')
    anchor.href = source
    anchor.download = filename
    anchor.target = '_blank'
    anchor.rel = 'noopener noreferrer'
    anchor.click()
    onNotify?.('warning', '浏览器阻止直接下载，已尝试打开文件链接')
  }
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (event) => resolve(event.target.result)
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
}

function StatusMessage({ type = 'error', text, onRetry }) {
  if (!text) return null

  const toneClass = type === 'error'
    ? 'border-rose-200 bg-rose-50 text-rose-700'
    : 'border-emerald-200 bg-emerald-50 text-emerald-700'

  return (
    <div className={`rounded-xl border px-4 py-3 text-sm ${toneClass}`}>
      <div className="flex items-center justify-between gap-3">
        <span>{text}</span>
        {onRetry && (
          <button
            onClick={onRetry}
            className="rounded-md border border-current/30 px-2 py-1 text-xs text-current hover:bg-white/70"
          >
            重试
          </button>
        )}
      </div>
    </div>
  )
}

function QuotaPanel({ items, emptyMessage = '当前模块暂无独立日配额' }) {
  const normalizedItems = Array.isArray(items)
    ? items.map((item) => {
      const usage = Number(item.usage ?? 0)
      const limit = Number(item.limit ?? 0)
      const ratio = Number.isFinite(item.ratio) ? item.ratio : (limit > 0 ? Math.min(100, (usage / limit) * 100) : 0)
      const remaining = Number(item.remaining ?? (limit > 0 ? Math.max(limit - usage, 0) : 0))
      const remainingDisplay = Number.isFinite(remaining) ? remaining : '-'
      return { ...item, usage, limit, ratio, remainingDisplay }
    })
    : []

  return (
    <div className="rounded-2xl border border-violet-100 bg-white/85 p-4 text-xs shadow-[0_8px_22px_rgba(103,102,208,0.12)]">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-violet-500/90">今日额度（每日重置）</div>
      {normalizedItems.length === 0 ? (
        <div className="rounded-xl border border-dashed border-violet-200 bg-violet-50/60 px-3 py-2 text-[11px] text-slate-500">
          {emptyMessage}
        </div>
      ) : (
        <div className="space-y-2">
          {normalizedItems.map((item) => (
            <div key={item.model_name}>
              <div className="mb-0.5 flex min-w-0 flex-col gap-0.5 text-slate-700 sm:flex-row sm:justify-between sm:gap-2">
                <span className="truncate">{item.display_name || item.model_name}</span>
                <span className="shrink-0">{item.usage} / {item.limit || '-'}</span>
              </div>
              <div className="mb-1 text-[11px] text-slate-500">
                剩余：{item.remainingDisplay}
              </div>
              <div className="h-1.5 rounded bg-violet-100/80">
                <div
                  className={`h-1.5 rounded transition-all ${item.ratio >= 90 ? 'bg-rose-400' : item.ratio >= 70 ? 'bg-amber-400' : 'bg-emerald-400'}`}
                  style={{ width: `${item.ratio}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function MusicQuotaShowcase({ items }) {
  const normalizedItems = Array.isArray(items) ? items : []

  return (
    <div className="overflow-hidden rounded-2xl border border-violet-100 bg-gradient-to-br from-white via-violet-50/80 to-fuchsia-50/70 p-4 shadow-[0_10px_28px_rgba(110,104,214,0.15)]">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-center">
        <div>
          <div className="mb-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-violet-500/90">今日额度（每日重置）</div>
            <div className="mt-1 text-sm text-slate-600">Music / Cover 各模型独立日配额</div>
          </div>
          {normalizedItems.length === 0 ? (
            <div className="rounded-xl border border-dashed border-violet-200 bg-white/75 px-3 py-2 text-[11px] text-slate-500">
              当前模块暂无独立日配额
            </div>
          ) : (
            <div className="space-y-2.5">
              {normalizedItems.map((item) => (
                <div key={item.model_name}>
                  <div className="mb-0.5 flex min-w-0 flex-col gap-0.5 text-slate-700 sm:flex-row sm:justify-between sm:gap-2">
                    <span className="truncate">{item.display_name || item.model_name}</span>
                    <span className="shrink-0">{item.usage} / {item.limit || '-'}</span>
                  </div>
                  <div className="mb-1 text-[11px] text-slate-500">剩余：{item.remainingDisplay}</div>
                  <div className="h-1.5 rounded bg-white/75">
                    <div
                      className={`h-1.5 rounded transition-all ${item.ratio >= 90 ? 'bg-rose-400' : item.ratio >= 70 ? 'bg-amber-400' : 'bg-emerald-400'}`}
                      style={{ width: `${item.ratio}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="pointer-events-none hidden justify-center lg:flex">
          <svg viewBox="0 0 320 220" className="h-[180px] w-[260px]" aria-hidden="true">
            <defs>
              <linearGradient id="musicGradA" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#7d7bff" />
                <stop offset="52%" stopColor="#b26bff" />
                <stop offset="100%" stopColor="#ff87cb" />
              </linearGradient>
              <linearGradient id="musicGradB" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#57a1ff" />
                <stop offset="100%" stopColor="#8b5dff" />
              </linearGradient>
              <filter id="musicGlow">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            <ellipse cx="162" cy="188" rx="86" ry="18" fill="#d8cfff" opacity="0.36" />
            <circle cx="246" cy="58" r="18" fill="url(#musicGradA)" opacity="0.45" />
            <circle cx="270" cy="156" r="14" fill="url(#musicGradB)" opacity="0.42" />
            <path d="M120 38 L212 18 L212 134 C212 154 196 170 176 170 C156 170 140 154 140 134 C140 114 156 98 176 98 C184 98 191 100 198 104 L198 52 L134 66 L134 152 C134 172 118 188 98 188 C78 188 62 172 62 152 C62 132 78 116 98 116 C106 116 113 118 120 122 Z" fill="url(#musicGradA)" filter="url(#musicGlow)" />
            <path d="M35 126 C68 146 104 146 137 126 M146 126 C179 106 214 106 247 126 M255 126 C276 138 296 138 316 126" stroke="#c8b8ff" strokeWidth="4" strokeLinecap="round" fill="none" opacity="0.8" />
          </svg>
        </div>
      </div>
    </div>
  )
}

export function TTSSection({ onNotify, quotaItems, defaults = {} }) {
  const [text, setText] = useState('')
  const [model, setModel] = useState(defaults?.ttsModel || 'speech-2.8-hd')
  const [voice, setVoice] = useState('English_expressive_narrator')
  const [speed, setSpeed] = useState(1.0)
  const [volume, setVolume] = useState(1.0)
  const [pitch, setPitch] = useState(0)
  const [langBoost, setLangBoost] = useState('')
  const [audioFormat, setAudioFormat] = useState('mp3')
  const [sampleRate, setSampleRate] = useState(32000)
  const [bitrate, setBitrate] = useState(128000)
  const [channels, setChannels] = useState(1)
  const [subtitles, setSubtitles] = useState(false)
  const [pronunciation, setPronunciation] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [voiceOptions, setVoiceOptions] = useState(BUILTIN_TTS_VOICE_IDS)
  const [voiceMetaMap, setVoiceMetaMap] = useState({})
  const [voiceKeyword, setVoiceKeyword] = useState('')
  const [voiceLoading, setVoiceLoading] = useState(false)
  const [voiceLoadError, setVoiceLoadError] = useState('')
  const [cnFavoriteVoices, setCnFavoriteVoices] = useState(DEFAULT_CN_FAVORITE_VOICES)
  const audioRef = useRef(null)

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(CN_FAVORITE_STORAGE_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        const cleaned = parsed
          .map((item) => (typeof item === 'string' ? item.trim() : ''))
          .filter(Boolean)
        if (cleaned.length > 0) {
          setCnFavoriteVoices(Array.from(new Set(cleaned)).slice(0, 12))
        }
      }
    } catch {
      // Ignore localStorage parse failures and keep defaults.
    }
  }, [])

  useEffect(() => {
    try {
      window.localStorage.setItem(CN_FAVORITE_STORAGE_KEY, JSON.stringify(cnFavoriteVoices))
    } catch {
      // Ignore storage write failures.
    }
  }, [cnFavoriteVoices])

  const loadVoices = useCallback(async ({ silent = false } = {}) => {
    setVoiceLoading(true)
    setVoiceLoadError('')
    try {
      const res = await ttsApi.voices()
      const apiVoiceItems = Array.isArray(res?.items) ? res.items : []
      const metaMap = {}
      for (const item of apiVoiceItems) {
        const voiceId = typeof item?.voice_id === 'string' ? item.voice_id.trim() : ''
        if (!voiceId) continue
        const voiceName = typeof item?.voice_name === 'string' ? item.voice_name.trim() : ''
        const source = typeof item?.source === 'string' ? item.source.trim() : ''
        metaMap[voiceId] = {
          voice_name: voiceName || metaMap[voiceId]?.voice_name || '',
          source: source || metaMap[voiceId]?.source || ''
        }
      }

      const apiVoicesById = Array.isArray(res?.voices)
        ? res.voices.filter((voiceId) => typeof voiceId === 'string' && voiceId.trim()).map((voiceId) => voiceId.trim())
        : []
      const apiVoicesFromItems = Object.keys(metaMap)
      const merged = Array.from(new Set([...BUILTIN_TTS_VOICE_IDS, ...apiVoicesById, ...apiVoicesFromItems]))
      setVoiceOptions((prev) => Array.from(new Set([...prev, ...merged])))
      setVoiceMetaMap((prev) => ({ ...prev, ...metaMap }))

      if (!silent) {
        const sourceLabel = res?.source === 'fallback' ? '回退列表' : '官方列表'
        onNotify?.('success', `音色列表已更新（${merged.length}，${sourceLabel}）`)
      }
    } catch (err) {
      const msg = getErrorMessage(err, '加载音色列表失败')
      setVoiceLoadError(msg)
      onNotify?.('warning', `加载音色列表失败，仍可手动输入 voice_id：${msg}`)
      // Keep builtins and current value usable.
      setVoiceOptions((prev) => Array.from(new Set([...BUILTIN_TTS_VOICE_IDS, ...prev])))
      setVoiceMetaMap({})
    } finally {
      setVoiceLoading(false)
    }
  }, [onNotify])

  useEffect(() => {
    loadVoices({ silent: true })
  }, [loadVoices])

  useEffect(() => {
    if (defaults?.ttsModel) {
      setModel(defaults.ttsModel)
    }
  }, [defaults?.ttsModel])

  const toggleFavoriteVoice = useCallback(() => {
    const currentVoice = voice.trim()
    if (!currentVoice) {
      onNotify?.('warning', '请先选择一个音色再收藏')
      return
    }
    setCnFavoriteVoices((prev) => {
      if (prev.includes(currentVoice)) {
        const next = prev.filter((item) => item !== currentVoice)
        onNotify?.('success', `已从收藏移除：${currentVoice}`)
        return next.length > 0 ? next : DEFAULT_CN_FAVORITE_VOICES
      }
      const next = Array.from(new Set([currentVoice, ...prev])).slice(0, 12)
      onNotify?.('success', `已收藏音色：${currentVoice}`)
      return next
    })
  }, [onNotify, voice])

  const removeFavoriteVoice = useCallback((targetVoice) => {
    setCnFavoriteVoices((prev) => {
      const next = prev.filter((item) => item !== targetVoice)
      return next.length > 0 ? next : DEFAULT_CN_FAVORITE_VOICES
    })
  }, [])

  const normalizedVoiceKeyword = voiceKeyword.trim().toLowerCase()
  const filteredVoiceOptions = voiceOptions.filter((voiceId) => {
    if (!normalizedVoiceKeyword) return true
    const friendlyName = formatVoiceLabel(voiceId, voiceMetaMap).toLowerCase()
    return (
      voiceId.toLowerCase().includes(normalizedVoiceKeyword) ||
      friendlyName.includes(normalizedVoiceKeyword)
    )
  })
  const displayedVoiceOptions = (
    voice.trim() && !filteredVoiceOptions.includes(voice.trim())
      ? [voice.trim(), ...filteredVoiceOptions]
      : filteredVoiceOptions
  )

  const handleSynthesize = async () => {
    if (!text.trim()) {
      const msg = '请输入文本后再合成语音'
      setError(msg)
      onNotify?.('warning', msg)
      return
    }
    if (!voice.trim()) {
      const msg = '请先选择或输入有效的音色 ID'
      setError(msg)
      onNotify?.('warning', msg)
      return
    }

    setIsProcessing(true)
    setError('')
    setResult(null)

    try {
      const res = await ttsApi.synthesize({
        text: text.trim(),
        model,
        voice: voice.trim(),
        speed,
        volume,
        pitch,
        language_boost: langBoost || undefined,
        format: audioFormat,
        sample_rate: sampleRate,
        bitrate,
        channels,
        subtitles,
        pronunciation: pronunciation
          .split('\n')
          .map((item) => item.trim())
          .filter(Boolean)
      })

      if (res.success) {
        setResult(res)
        onNotify?.('success', '语音合成完成')
      } else {
        const msg = res.detail || '语音合成失败'
        setError(msg)
        onNotify?.('error', msg)
      }
    } catch (err) {
      const msg = getErrorMessage(err, '语音合成失败')
      setError(msg)
      onNotify?.('error', msg)
    } finally {
      setIsProcessing(false)
    }
  }

  const downloadAudio = (audioSource) => {
    const ext = extensionFromSource(audioSource, audioFormat || 'mp3')
    void downloadGeneratedFile(audioSource, `tts-${makeTimestamp()}.${ext}`, onNotify)
  }

  return (
    <div className="module-stack">
      <QuotaPanel items={quotaItems} />
      <div className="card-shell module-form-card">
        <h2 className="module-form-title">文字转语音</h2>

        <div className="rounded-xl border border-violet-100 bg-violet-50/50 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-slate-700">常用中文音色收藏栏</span>
            <button
              type="button"
              onClick={toggleFavoriteVoice}
              className="text-xs text-primary hover:text-primary/80"
            >
              {cnFavoriteVoices.includes(voice.trim()) ? '取消收藏当前音色' : '收藏当前音色'}
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {cnFavoriteVoices.map((voiceId) => (
              <div
                key={`fav-${voiceId}`}
                className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs ${
                  voice === voiceId
                    ? 'border-violet-300 bg-violet-100/80 text-violet-700'
                    : 'border-violet-100 bg-white/85 text-slate-700'
                }`}
              >
                <button
                  type="button"
                  onClick={() => setVoice(voiceId)}
                  className="hover:text-violet-700"
                >
                  {formatVoiceLabel(voiceId, voiceMetaMap)}
                </button>
                <button
                  type="button"
                  onClick={() => removeFavoriteVoice(voiceId)}
                  className="text-slate-400 hover:text-rose-600"
                  aria-label={`移除收藏音色 ${voiceId}`}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>

        <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">输入文本</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="输入你想转换为语音的内容..."
            className="field-input h-36 w-full resize-none"
            maxLength={10000}
          />
          <div className="mt-1 text-right text-xs text-slate-500">{text.length} / 10000</div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">模型</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="field-input w-full"
            >
              <option value="speech-2.8-hd">speech-2.8-hd (高清)</option>
              <option value="speech-2.6-hd">speech-2.6-hd (标准)</option>
              <option value="speech-02-hd">speech-02-hd (轻量)</option>
            </select>
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between">
              <label className="block text-sm font-medium text-slate-700">
                音色
                <span className="ml-1 text-xs text-slate-500">({filteredVoiceOptions.length}/{voiceOptions.length})</span>
              </label>
              <button
                type="button"
                onClick={() => loadVoices({ silent: false })}
                disabled={voiceLoading}
                className="text-xs text-slate-500 hover:text-violet-700 disabled:opacity-50"
              >
                {voiceLoading ? '刷新中...' : '刷新音色'}
              </button>
            </div>
            <input
              value={voiceKeyword}
              onChange={(e) => setVoiceKeyword(e.target.value)}
              placeholder="搜索官方音色（名称或 voice_id）"
              className="field-input mb-2 w-full text-xs"
            />
            <select
              value={voice}
              onChange={(e) => setVoice(e.target.value)}
              className="field-input w-full"
            >
              {displayedVoiceOptions.map((voiceId) => (
                <option key={voiceId} value={voiceId}>
                  {formatVoiceLabel(voiceId, voiceMetaMap)} ({voiceId})
                </option>
              ))}
            </select>
            <input
              value={voice}
              onChange={(e) => setVoice(e.target.value.trim())}
              placeholder="或手动输入 voice_id"
              className="field-input mt-2 w-full text-xs"
            />
            <div className="mt-1 text-xs text-slate-500">
              已接入官方音色清单，可搜索下拉选择，也可手动输入 voice_id。
            </div>
            {voiceLoadError && (
              <div className="mt-1 text-xs text-amber-300">
                音色列表加载失败：{voiceLoadError}
              </div>
            )}
          </div>
        </div>

        <button
          onClick={() => setShowAdvanced((s) => !s)}
          className="text-xs text-slate-500 hover:text-violet-700"
        >
          {showAdvanced ? '收起高级设置' : '展开高级设置'}
        </button>

        {showAdvanced && (
          <div className="grid gap-4 rounded-xl border border-violet-100 bg-white/70 p-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <div className="mb-1 flex justify-between text-xs text-slate-400">
                <span>语速</span>
                <span>{speed.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="2"
                step="0.1"
                value={speed}
                onChange={(e) => setSpeed(parseFloat(e.target.value))}
                className="slider w-full"
              />
            </div>
            <div>
              <div className="mb-1 flex justify-between text-xs text-slate-400">
                <span>音量</span>
                <span>{volume.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="10"
                step="0.1"
                value={volume}
                onChange={(e) => setVolume(parseFloat(e.target.value))}
                className="slider w-full"
              />
            </div>
            <div>
              <div className="mb-1 flex justify-between text-xs text-slate-400">
                <span>音调</span>
                <span>{pitch > 0 ? '+' : ''}{pitch}</span>
              </div>
              <input
                type="range"
                min="-12"
                max="12"
                step="1"
                value={pitch}
                onChange={(e) => setPitch(parseInt(e.target.value, 10))}
                className="slider w-full"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">语言增强</label>
              <select
                value={langBoost}
                onChange={(e) => setLangBoost(e.target.value)}
                className="field-input w-full text-xs"
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang.id} value={lang.id}>{lang.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">格式</label>
              <select value={audioFormat} onChange={(e) => setAudioFormat(e.target.value)} className="field-input w-full text-xs">
                <option value="mp3">MP3</option>
                <option value="wav">WAV</option>
                <option value="pcm">PCM</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">采样率</label>
              <select value={sampleRate} onChange={(e) => setSampleRate(parseInt(e.target.value, 10))} className="field-input w-full text-xs">
                <option value={16000}>16000</option>
                <option value={24000}>24000</option>
                <option value={32000}>32000</option>
                <option value={44100}>44100</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">码率</label>
              <select value={bitrate} onChange={(e) => setBitrate(parseInt(e.target.value, 10))} className="field-input w-full text-xs">
                <option value={64000}>64 kbps</option>
                <option value={128000}>128 kbps</option>
                <option value={256000}>256 kbps</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">声道</label>
              <select value={channels} onChange={(e) => setChannels(parseInt(e.target.value, 10))} className="field-input w-full text-xs">
                <option value={1}>单声道</option>
                <option value={2}>双声道</option>
              </select>
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-700">
              <input type="checkbox" checked={subtitles} onChange={(e) => setSubtitles(e.target.checked)} />
              返回字幕时间轴
            </label>
            <div className="sm:col-span-2 lg:col-span-4">
              <label className="mb-1 block text-xs text-slate-400">发音字典</label>
              <textarea
                value={pronunciation}
                onChange={(e) => setPronunciation(e.target.value)}
                placeholder="每行一个：原词/替换读音"
                className="field-input h-20 w-full resize-none text-xs"
              />
            </div>
          </div>
        )}

        <StatusMessage type="error" text={error} onRetry={handleSynthesize} />

        {result && (result.audio_data || result.audio_url) && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <div className="mb-2 text-sm text-emerald-700">
              合成成功
              {result.duration_ms ? ` · ${(result.duration_ms / 1000).toFixed(1)} 秒` : ''}
            </div>
            <audio
              ref={audioRef}
              src={result.audio_data || result.audio_url}
              controls
              className="w-full"
            />
            <div className="mt-3 flex gap-2">
              <button
                onClick={() => downloadAudio(result.audio_data || result.audio_url)}
                className="btn-secondary text-sm"
              >
                下载音频
              </button>
              {result.audio_url && (
                <a
                  href={result.audio_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary text-sm"
                >
                  新窗口播放
                </a>
              )}
            </div>
          </div>
        )}

        <button
          onClick={handleSynthesize}
          disabled={isProcessing || !text.trim()}
          className="btn-primary w-full py-3"
        >
          {isProcessing ? '合成中...' : '开始合成语音'}
        </button>
      </div>
    </div>
  )
}

export function MusicSection({ onNotify, quotaItems, defaults = {} }) {
  const [tab, setTab] = useState('generate')
  const [prompt, setPrompt] = useState('')
  const [lyrics, setLyrics] = useState('')
  const [instrumental, setInstrumental] = useState(false)
  const [lyricsOptimizer, setLyricsOptimizer] = useState(false)
  const [model, setModel] = useState(defaults?.musicModel || 'music-2.6')
  const [genre, setGenre] = useState('')
  const [mood, setMood] = useState('')
  const [bpm, setBpm] = useState(
    Number.isFinite(Number(defaults?.musicBpm)) ? String(Number(defaults.musicBpm)) : ''
  )
  const [isProcessing, setIsProcessing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [coverPrompt, setCoverPrompt] = useState('')
  const [coverUrl, setCoverUrl] = useState('')
  const [coverFile, setCoverFile] = useState(null)
  const [coverFileName, setCoverFileName] = useState('')
  const [musicTaskId, setMusicTaskId] = useState('')
  const [taskQueryId, setTaskQueryId] = useState('')
  const [musicTaskStatus, setMusicTaskStatus] = useState('')
  const [isMusicPolling, setIsMusicPolling] = useState(false)
  const musicPollTimerRef = useRef(null)
  const musicPollFailureCountRef = useRef(0)
  const coverFileInputRef = useRef(null)

  const stopMusicPolling = useCallback(() => {
    if (musicPollTimerRef.current) {
      clearInterval(musicPollTimerRef.current)
      musicPollTimerRef.current = null
    }
    musicPollFailureCountRef.current = 0
    setIsMusicPolling(false)
  }, [])

  useEffect(() => () => stopMusicPolling(), [stopMusicPolling])

  useEffect(() => {
    if (defaults?.musicModel) {
      setModel(defaults.musicModel)
    }
    if (Number.isFinite(Number(defaults?.musicBpm))) {
      setBpm(String(Number(defaults.musicBpm)))
    }
  }, [defaults?.musicBpm, defaults?.musicModel])

  const pollMusicTaskById = useCallback(async (rawTaskId, { manual = false } = {}) => {
    const activeTaskId = typeof rawTaskId === 'string' ? rawTaskId.trim() : ''
    if (!activeTaskId) {
      if (manual) {
        const msg = '请输入有效的任务ID'
        setError(msg)
        onNotify?.('warning', msg)
      }
      return
    }

    setIsMusicPolling(true)
    if (manual) {
      setError('')
    }

    try {
      const res = await musicApi.task(activeTaskId)
      musicPollFailureCountRef.current = 0

      if (res.success && (res.audio_data || res.audio_url)) {
        setResult(res)
        setMusicTaskStatus('任务完成，已返回音频')
        setMusicTaskId('')
        setTaskQueryId(activeTaskId)
        setError('')
        stopMusicPolling()
        onNotify?.('success', '音乐生成完成')
        return
      }

      if (!res.success) {
        const msg = res.message || '音乐任务失败'
        setError(msg)
        setMusicTaskStatus(msg)
        setMusicTaskId('')
        setTaskQueryId(activeTaskId)
        stopMusicPolling()
        onNotify?.('error', msg)
        return
      }

      const pendingMsg = res.message || '音乐任务处理中'
      setMusicTaskStatus(pendingMsg)
      setTaskQueryId(activeTaskId)
      if (manual) {
        // Manual query should also enter auto-poll flow for better continuity.
        setMusicTaskId(activeTaskId)
      }
      setError('')
    } catch (err) {
      const msg = getErrorMessage(err, '音乐任务轮询失败')
      const nextFailures = musicPollFailureCountRef.current + 1
      musicPollFailureCountRef.current = nextFailures

      if (nextFailures < MUSIC_POLL_MAX_RETRIES) {
        const retryMsg = `音乐任务轮询网络波动，自动重试中（${nextFailures}/${MUSIC_POLL_MAX_RETRIES}）`
        setMusicTaskStatus(retryMsg)
        setError(retryMsg)
        if (nextFailures === 1) {
          onNotify?.('warning', `${retryMsg}：${msg}`)
        }
        return
      }

      setError(msg)
      setMusicTaskStatus(msg)
      setMusicTaskId('')
      stopMusicPolling()
      onNotify?.('error', msg)
    }
  }, [onNotify, stopMusicPolling])

  useEffect(() => {
    if (!musicTaskId) return undefined
    setIsMusicPolling(true)
    musicPollTimerRef.current = setInterval(() => {
      void pollMusicTaskById(musicTaskId)
    }, MUSIC_POLL_INTERVAL_MS)
    return () => stopMusicPolling()
  }, [musicTaskId, pollMusicTaskById, stopMusicPolling])

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      const msg = '请输入音乐描述'
      setError(msg)
      onNotify?.('warning', msg)
      return
    }
    if (!instrumental && !lyricsOptimizer && !lyrics.trim()) {
      const msg = '请输入歌词，或勾选自动生成歌词'
      setError(msg)
      onNotify?.('warning', msg)
      return
    }

    setIsProcessing(true)
    setError('')
    setResult(null)
    setMusicTaskStatus('')
    stopMusicPolling()
    setMusicTaskId('')

    try {
      const res = await musicApi.generate({
        prompt: prompt.trim(),
        lyrics: instrumental ? undefined : (lyricsOptimizer ? undefined : lyrics.trim()),
        instrumental,
        lyrics_optimizer: lyricsOptimizer,
        model,
        genre: genre || undefined,
        mood: mood || undefined,
        bpm: bpm ? parseInt(bpm, 10) : undefined
      })
      if (res.success) {
        if (res.audio_data || res.audio_url) {
          setResult(res)
          setMusicTaskStatus('任务完成，已返回音频')
          onNotify?.('success', '音乐生成完成')
        } else {
          const submittedTaskId = typeof res.task_id === 'string' ? res.task_id.trim() : ''
          if (!submittedTaskId) {
            const msg = '任务提交成功但未返回任务ID，请重试'
            setError(msg)
            onNotify?.('error', msg)
          } else {
            setMusicTaskId(submittedTaskId)
            setTaskQueryId(submittedTaskId)
            setMusicTaskStatus('任务已提交，系统将自动轮询')
            onNotify?.('success', `音乐任务已提交: ${submittedTaskId}`)
            void pollMusicTaskById(submittedTaskId)
          }
        }
      } else {
        const msg = res.detail || '音乐生成失败'
        setError(msg)
        onNotify?.('error', msg)
      }
    } catch (err) {
      const msg = getErrorMessage(err, '音乐生成失败')
      setError(msg)
      onNotify?.('error', msg)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleCover = async () => {
    if (!coverPrompt.trim()) {
      const msg = '请输入翻唱描述'
      setError(msg)
      onNotify?.('warning', msg)
      return
    }
    if (!coverUrl && !coverFile) {
      const msg = '请提供参考音频（URL 或上传文件）'
      setError(msg)
      onNotify?.('warning', msg)
      return
    }

    setIsProcessing(true)
    setError('')
    setResult(null)
    setMusicTaskStatus('')
    stopMusicPolling()
    setMusicTaskId('')

    try {
      const payload = { prompt: coverPrompt.trim(), model: 'music-cover' }
      if (coverUrl) payload.audio_url = coverUrl
      if (coverFile) payload.audio_data = coverFile

      const res = await musicApi.cover(payload)
      if (res.success) {
        if (res.audio_data || res.audio_url) {
          setResult(res)
          setMusicTaskStatus('任务完成，已返回音频')
          onNotify?.('success', '翻唱生成完成')
        } else {
          const submittedTaskId = typeof res.task_id === 'string' ? res.task_id.trim() : ''
          if (!submittedTaskId) {
            const msg = '任务提交成功但未返回任务ID，请重试'
            setError(msg)
            onNotify?.('error', msg)
          } else {
            setMusicTaskId(submittedTaskId)
            setTaskQueryId(submittedTaskId)
            setMusicTaskStatus('任务已提交，系统将自动轮询')
            onNotify?.('success', `翻唱任务已提交: ${submittedTaskId}`)
            void pollMusicTaskById(submittedTaskId)
          }
        }
      } else {
        const msg = res.detail || '音乐翻唱失败'
        setError(msg)
        onNotify?.('error', msg)
      }
    } catch (err) {
      const msg = getErrorMessage(err, '音乐翻唱失败')
      setError(msg)
      onNotify?.('error', msg)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleCoverFileSelected = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    try {
      const dataUrl = await readFileAsDataUrl(file)
      setCoverFile(dataUrl)
      setCoverFileName(file.name)
    } catch (err) {
      const msg = getErrorMessage(err, '参考音频读取失败')
      setError(msg)
      onNotify?.('error', msg)
    } finally {
      event.target.value = ''
    }
  }

  const clearCoverFile = () => {
    setCoverFile(null)
    setCoverFileName('')
    if (coverFileInputRef.current) {
      coverFileInputRef.current.value = ''
    }
  }

  const downloadMusic = (audioSource) => {
    const ext = extensionFromSource(audioSource, 'mp3')
    void downloadGeneratedFile(audioSource, `music-${makeTimestamp()}.${ext}`, onNotify)
  }

  return (
    <div className="module-stack">
      <MusicQuotaShowcase items={quotaItems} />
      <div className="card-shell module-form-card module-form-card-compact overflow-hidden">
        <div className="grid grid-cols-2 border-b border-violet-100">
          <button
            onClick={() => {
              setTab('generate')
              setError('')
              setResult(null)
              setMusicTaskStatus('')
              setMusicTaskId('')
              stopMusicPolling()
            }}
            className={`py-3 text-sm font-medium transition ${tab === 'generate' ? 'bg-violet-100/90 text-violet-700' : 'text-slate-500 hover:bg-violet-50 hover:text-violet-600'}`}
          >
            生成音乐
          </button>
          <button
            onClick={() => {
              setTab('cover')
              setError('')
              setResult(null)
              setMusicTaskStatus('')
              setMusicTaskId('')
              stopMusicPolling()
            }}
            className={`py-3 text-sm font-medium transition ${tab === 'cover' ? 'bg-violet-100/90 text-violet-700' : 'text-slate-500 hover:bg-violet-50 hover:text-violet-600'}`}
          >
            音乐翻唱
          </button>
        </div>

        <div className="module-form-body">
          {tab === 'generate' && (
            <>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">音乐描述</label>
                <input
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="例如：明亮、偏电子、适合产品发布会开场"
                  className="field-input w-full"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label className="mb-1 block text-xs text-slate-500">模型</label>
                  <select
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="field-input w-full text-xs"
                  >
                    {MUSIC_MODELS.map((item) => (
                      <option key={item.id} value={item.id}>{item.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-500">流派</label>
                  <input
                    value={genre}
                    onChange={(e) => setGenre(e.target.value)}
                    placeholder="pop / cinematic / jazz"
                    className="field-input w-full text-xs"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-500">BPM</label>
                  <input
                    value={bpm}
                    onChange={(e) => setBpm(e.target.value)}
                    type="number"
                    placeholder="120"
                    className="field-input w-full text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">情绪与歌词</label>
                <input
                  value={mood}
                  onChange={(e) => setMood(e.target.value)}
                  placeholder="情绪关键词，例如 uplifting / chill"
                  className="field-input mb-2 w-full text-sm"
                />
                <textarea
                  value={lyrics}
                  onChange={(e) => setLyrics(e.target.value)}
                  placeholder="可选：歌词内容，支持 [Verse] [Chorus] 结构"
                  className="field-input h-24 w-full resize-none text-xs"
                />
              </div>

              <div className="flex flex-wrap gap-4 text-xs text-slate-600">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={instrumental}
                    onChange={(e) => setInstrumental(e.target.checked)}
                  />
                  纯音乐
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={lyricsOptimizer}
                    onChange={(e) => setLyricsOptimizer(e.target.checked)}
                  />
                  自动生成歌词
                </label>
              </div>
            </>
          )}

          {tab === 'cover' && (
            <>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">翻唱风格描述</label>
                <input
                  value={coverPrompt}
                  onChange={(e) => setCoverPrompt(e.target.value)}
                  placeholder="例如：女声、抒情、钢琴伴奏"
                  className="field-input w-full"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-500">参考音频 URL</label>
                <input
                  value={coverUrl}
                  onChange={(e) => setCoverUrl(e.target.value)}
                  placeholder="https://..."
                  className="field-input w-full text-xs"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-500">或上传参考音频文件</label>
                <input
                  ref={coverFileInputRef}
                  type="file"
                  accept="audio/*"
                  onChange={handleCoverFileSelected}
                  className="block text-xs text-slate-500"
                />
                {coverFile && (
                  <div className="mt-2 flex items-center justify-between gap-2 rounded-lg border border-violet-100 bg-violet-50/60 px-3 py-2 text-xs text-slate-600">
                    <span className="truncate">{coverFileName || '已选择参考音频'}</span>
                    <button type="button" onClick={clearCoverFile} className="text-rose-600 hover:text-rose-700">
                      移除
                    </button>
                  </div>
                )}
              </div>
            </>
          )}

          <StatusMessage
            type="error"
            text={error}
            onRetry={tab === 'generate' ? handleGenerate : handleCover}
          />

          {(musicTaskId || musicTaskStatus) && (
            <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-700">
              {musicTaskId && <div>任务已提交：{musicTaskId}</div>}
              <div className="mt-1 text-xs text-slate-500">
                {musicTaskStatus || (isMusicPolling ? '任务处理中，系统自动轮询中...' : '等待任务状态更新')}
              </div>
              {musicTaskId && (
                <button
                  onClick={() => { void pollMusicTaskById(musicTaskId, { manual: true }) }}
                  className="btn-secondary mt-2 text-xs"
                >
                  立即轮询
                </button>
              )}
            </div>
          )}

            <div className="rounded-xl border border-violet-100 bg-violet-50/45 p-4">
              <div className="mb-2 text-sm font-medium text-slate-700">任务ID查询</div>
            <div className="flex gap-2">
              <input
                value={taskQueryId}
                onChange={(e) => setTaskQueryId(e.target.value)}
                placeholder="输入 task_id 查询音乐任务"
                className="field-input flex-1 text-xs"
              />
              <button
                onClick={() => { void pollMusicTaskById(taskQueryId, { manual: true }) }}
                className="btn-secondary text-xs"
              >
                查询
              </button>
            </div>
          </div>

          {result && (result.audio_data || result.audio_url) && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
              <div className="mb-2 text-sm text-emerald-700">任务完成，已返回音频</div>
              <audio src={result.audio_data || result.audio_url} controls className="w-full" />
              <button
                onClick={() => downloadMusic(result.audio_data || result.audio_url)}
                className="btn-secondary mt-3 text-sm"
              >
                下载音频
              </button>
            </div>
          )}

          <button
            onClick={tab === 'generate' ? handleGenerate : handleCover}
            disabled={isProcessing}
            className="btn-primary w-full py-3"
          >
            {isProcessing ? '处理中...' : tab === 'generate' ? '开始生成音乐' : '开始生成翻唱'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function VideoSection({ onNotify, quotaItems, defaults = {} }) {
  const [prompt, setPrompt] = useState('')
  const [model, setModel] = useState(defaults?.videoModel || 'MiniMax-Hailuo-2.3')
  const [firstFrame, setFirstFrame] = useState(null)
  const [lastFrame, setLastFrame] = useState(null)
  const [subjectImage, setSubjectImage] = useState(null)
  const [firstFrameName, setFirstFrameName] = useState('')
  const [lastFrameName, setLastFrameName] = useState('')
  const [subjectImageName, setSubjectImageName] = useState('')
  const [duration, setDuration] = useState(
    Number.isFinite(Number(defaults?.videoDuration)) ? Number(defaults.videoDuration) : 6
  )
  const [resolution, setResolution] = useState(defaults?.videoResolution || '768P')
  const [promptOptimizer, setPromptOptimizer] = useState(true)
  const [fastPretreatment, setFastPretreatment] = useState(false)
  const [aigcWatermark, setAigcWatermark] = useState(false)
  const [noWait, setNoWait] = useState(true)
  const [isProcessing, setIsProcessing] = useState(false)
  const [result, setResult] = useState(null)
  const [taskId, setTaskId] = useState(null)
  const [taskHistory, setTaskHistory] = useState([])
  const [historyFilter, setHistoryFilter] = useState('active')
  const [error, setError] = useState('')
  const pollTimerRef = useRef(null)
  const videoPollFailureCountRef = useRef(0)
  const firstFrameInputRef = useRef(null)
  const lastFrameInputRef = useRef(null)
  const subjectImageInputRef = useRef(null)

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
    videoPollFailureCountRef.current = 0
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      const raw = window.localStorage.getItem(VIDEO_TASK_HISTORY_STORAGE_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw)
      if (!Array.isArray(parsed)) return
      const normalized = parsed
        .map((item) => {
          if (!item || typeof item !== 'object') return null
          const id = typeof item.task_id === 'string' ? item.task_id.trim() : ''
          if (!id) return null
          return {
            task_id: id,
            prompt: typeof item.prompt === 'string' ? item.prompt : '',
            model: typeof item.model === 'string' ? item.model : '',
            status: typeof item.status === 'string' ? item.status : 'Pending',
            message: typeof item.message === 'string' ? item.message : '',
            created_at: typeof item.created_at === 'string' ? item.created_at : '',
            updated_at: typeof item.updated_at === 'string' ? item.updated_at : ''
          }
        })
        .filter(Boolean)
        .slice(0, VIDEO_TASK_HISTORY_MAX_COUNT)
      setTaskHistory(normalized)
    } catch {
      // Ignore localStorage parse errors.
    }
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(VIDEO_TASK_HISTORY_STORAGE_KEY, JSON.stringify(taskHistory))
    } catch {
      // Ignore localStorage write failures.
    }
  }, [taskHistory])

  const upsertTaskHistory = useCallback((nextTaskId, patch = {}) => {
    const normalizedTaskId = typeof nextTaskId === 'string' ? nextTaskId.trim() : ''
    if (!normalizedTaskId) return
    setTaskHistory((prev) => {
      const nowIso = new Date().toISOString()
      const next = [...prev]
      const index = next.findIndex((item) => item.task_id === normalizedTaskId)
      const base = index >= 0 ? next[index] : { task_id: normalizedTaskId, created_at: nowIso }
      const merged = {
        ...base,
        ...patch,
        task_id: normalizedTaskId,
        updated_at: nowIso
      }
      if (!merged.created_at) merged.created_at = nowIso
      if (index >= 0) {
        next[index] = merged
      } else {
        next.unshift(merged)
      }
      return next.slice(0, VIDEO_TASK_HISTORY_MAX_COUNT)
    })
  }, [])

  const removeTaskHistory = useCallback((targetTaskId) => {
    const normalizedTaskId = typeof targetTaskId === 'string' ? targetTaskId.trim() : ''
    if (!normalizedTaskId) return
    setTaskHistory((prev) => prev.filter((item) => item.task_id !== normalizedTaskId))
  }, [])

  const clearTaskHistory = useCallback(() => {
    setTaskHistory([])
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(VIDEO_TASK_HISTORY_STORAGE_KEY)
    }
  }, [])

  const handleFileUpload = async (event, setter, setName) => {
    const file = event.target.files?.[0]
    if (!file) return
    try {
      const dataUrl = await readFileAsDataUrl(file)
      setter(dataUrl)
      setName(file.name)
    } catch (err) {
      const msg = getErrorMessage(err, '图片读取失败')
      setError(msg)
      onNotify?.('error', msg)
    } finally {
      event.target.value = ''
    }
  }

  const clearVideoFile = (setter, setName, ref) => {
    setter(null)
    setName('')
    if (ref.current) {
      ref.current.value = ''
    }
  }

  const pollTaskById = useCallback(async (rawTaskId) => {
    const activeTaskId = typeof rawTaskId === 'string' ? rawTaskId.trim() : ''
    if (!activeTaskId) return
    try {
      const res = await videoApi.task(activeTaskId)
      videoPollFailureCountRef.current = 0
      if (res.success && (res.video_data || res.video_url)) {
        setResult(res)
        setTaskId((current) => (current === activeTaskId ? null : current))
        setError('')
        stopPolling()
        upsertTaskHistory(activeTaskId, {
          status: res.status || 'Success',
          message: res.message || '视频已生成'
        })
        onNotify?.('success', '视频生成完成')
        return
      }
      if (res.status === 'Failed' || !res.success) {
        const msg = res.detail || res.message || '视频生成失败'
        setError(msg)
        setTaskId((current) => (current === activeTaskId ? null : current))
        stopPolling()
        upsertTaskHistory(activeTaskId, {
          status: 'Failed',
          message: msg
        })
        onNotify?.('error', msg)
        return
      }
      upsertTaskHistory(activeTaskId, {
        status: res.status || 'Processing',
        message: res.message || '任务处理中'
      })
    } catch (err) {
      const msg = getErrorMessage(err, '视频轮询失败')
      const nextFailures = videoPollFailureCountRef.current + 1
      videoPollFailureCountRef.current = nextFailures

      if (nextFailures < VIDEO_POLL_MAX_RETRIES) {
        const retryMsg = `视频轮询网络波动，自动重试中（${nextFailures}/${VIDEO_POLL_MAX_RETRIES}）`
        setError(retryMsg)
        upsertTaskHistory(activeTaskId, {
          status: 'Processing',
          message: retryMsg
        })
        if (nextFailures === 1) {
          onNotify?.('warning', `${retryMsg}：${msg}`)
        }
        return
      }

      setError(msg)
      setTaskId((current) => (current === activeTaskId ? null : current))
      stopPolling()
      upsertTaskHistory(activeTaskId, {
        status: 'Error',
        message: msg
      })
      onNotify?.('error', msg)
    }
  }, [onNotify, stopPolling, upsertTaskHistory])

  const pollTask = useCallback(async () => {
    if (!taskId) return
    await pollTaskById(taskId)
  }, [pollTaskById, taskId])

  useEffect(() => {
    if (!taskId) return undefined
    pollTimerRef.current = setInterval(() => {
      void pollTaskById(taskId)
    }, 10000)
    return () => stopPolling()
  }, [taskId, pollTaskById, stopPolling])

  useEffect(() => {
    if (defaults?.videoModel) {
      setModel(defaults.videoModel)
    }
    if (Number.isFinite(Number(defaults?.videoDuration))) {
      setDuration(Number(defaults.videoDuration))
    }
    if (defaults?.videoResolution) {
      setResolution(defaults.videoResolution)
    }
  }, [defaults?.videoDuration, defaults?.videoModel, defaults?.videoResolution])

  const formatTaskTime = (rawValue) => {
    if (!rawValue) return ''
    const date = new Date(rawValue)
    if (Number.isNaN(date.getTime())) return ''
    return date.toLocaleString()
  }

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      const msg = '请输入视频描述'
      setError(msg)
      onNotify?.('warning', msg)
      return
    }
    if (lastFrame && !firstFrame) {
      const msg = '尾帧模式需要同时提供首帧'
      setError(msg)
      onNotify?.('warning', msg)
      return
    }

    let effectiveModel = model
    if (lastFrame && model !== 'MiniMax-Hailuo-02') {
      effectiveModel = 'MiniMax-Hailuo-02'
      setModel(effectiveModel)
      onNotify?.('warning', '检测到首尾帧模式，已自动切换到 MiniMax-Hailuo-02')
    }

    let effectiveSubjectImage = subjectImage
    if (lastFrame && subjectImage) {
      effectiveSubjectImage = null
      setSubjectImage(null)
      onNotify?.('warning', '首尾帧模式与角色参考图不兼容，已自动关闭角色参考图')
    }

    setIsProcessing(true)
    setError('')
    setResult(null)
    setTaskId(null)
    stopPolling()

    try {
      const payload = {
        prompt: prompt.trim(),
        model: effectiveModel,
        no_wait: noWait,
        prompt_optimizer: promptOptimizer,
        fast_pretreatment: fastPretreatment,
        aigc_watermark: aigcWatermark
      }
      if (effectiveModel !== 'S2V-01') {
        payload.duration = duration
        payload.resolution = resolution
      }
      if (firstFrame) payload.first_frame = firstFrame
      if (lastFrame) payload.last_frame = lastFrame
      if (effectiveSubjectImage) payload.subject_image = effectiveSubjectImage

      const res = await videoApi.generate(payload)
      if (res.success) {
        if (noWait || res.status === 'Pending') {
          const submittedTaskId = typeof res.task_id === 'string' ? res.task_id.trim() : ''
          if (!submittedTaskId) {
            const msg = '任务提交成功但未返回任务ID，请重试'
            setError(msg)
            onNotify?.('error', msg)
          } else {
            setTaskId(submittedTaskId)
            upsertTaskHistory(submittedTaskId, {
              prompt: payload.prompt,
              model: effectiveModel,
              status: res.status || 'Pending',
              message: res.message || '任务已提交'
            })
            onNotify?.('success', `视频任务已提交: ${submittedTaskId}`)
          }
        } else if (res.video_data || res.video_url) {
          setResult(res)
          if (typeof res.task_id === 'string' && res.task_id.trim()) {
            upsertTaskHistory(res.task_id, {
              prompt: payload.prompt,
              model: effectiveModel,
              status: res.status || 'Success',
              message: res.message || '视频已生成'
            })
          }
          onNotify?.('success', '视频生成完成')
        } else {
          setError(res.message || '视频任务已完成，但未返回可播放地址')
        }
      } else {
        const msg = res.detail || '视频生成失败'
        setError(msg)
        onNotify?.('error', msg)
      }
    } catch (err) {
      let msg = getErrorMessage(err, '视频生成失败')
      if (typeof msg === 'string' && msg.includes('timeout of 120000ms exceeded')) {
        msg = '请求等待超时：建议保持“快速返回”开启，系统将自动轮询任务结果。'
      }
      setError(msg)
      onNotify?.('error', msg)
    } finally {
      setIsProcessing(false)
    }
  }

  const getStatusBadgeClass = (status) => {
    const normalized = String(status || '').toLowerCase()
    if (normalized.includes('success')) return 'border-emerald-300 bg-emerald-50 text-emerald-700'
    if (normalized.includes('fail') || normalized.includes('error')) return 'border-rose-300 bg-rose-50 text-rose-700'
    if (normalized.includes('pending') || normalized.includes('process')) return 'border-sky-300 bg-sky-50 text-sky-700'
    return 'border-slate-300/60 bg-slate-100 text-slate-600'
  }

  const getNormalizedStatus = (status) => String(status || '').toLowerCase()

  const isSuccessStatus = (status) => getNormalizedStatus(status).includes('success')
  const isFailedStatus = (status) => {
    const normalized = getNormalizedStatus(status)
    return normalized.includes('fail') || normalized.includes('error')
  }
  const isActiveStatus = (status) => {
    if (isSuccessStatus(status) || isFailedStatus(status)) return false
    return true
  }

  const filteredTaskHistory = taskHistory.filter((item) => {
    if (historyFilter === 'all') return true
    if (historyFilter === 'success') return isSuccessStatus(item.status)
    if (historyFilter === 'failed') return isFailedStatus(item.status)
    return isActiveStatus(item.status)
  })

  const copyTaskId = useCallback(async (rawTaskId) => {
    const value = typeof rawTaskId === 'string' ? rawTaskId.trim() : ''
    if (!value) {
      onNotify?.('warning', '任务ID为空，无法复制')
      return
    }
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value)
      } else {
        const input = document.createElement('input')
        input.value = value
        document.body.appendChild(input)
        input.select()
        document.execCommand('copy')
        document.body.removeChild(input)
      }
      onNotify?.('success', `已复制任务ID: ${value}`)
    } catch {
      onNotify?.('error', '复制任务ID失败，请手动复制')
    }
  }, [onNotify])

  const resolutionOptions = VIDEO_RESOLUTIONS.filter((item) => {
    if (model === 'S2V-01') return false
    if (lastFrame && item === '512P') return false
    if (duration === 10) return item === '768P'
    return true
  })

  useEffect(() => {
    if (model === 'S2V-01') return
    if (!resolutionOptions.includes(resolution)) {
      setResolution(resolutionOptions[0] || '768P')
    }
  }, [model, resolution, resolutionOptions])

  useEffect(() => {
    if (resolution === '1080P' && duration !== 6) {
      setDuration(6)
    }
  }, [duration, resolution])

  const appendMotionPrompt = (motion) => {
    setPrompt((prev) => {
      const trimmed = prev.trim()
      if (!trimmed) return motion
      if (trimmed.includes(motion)) return trimmed
      return `${trimmed}，${motion}`
    })
  }

  const downloadVideo = (videoSource) => {
    const ext = extensionFromSource(videoSource, 'mp4')
    void downloadGeneratedFile(videoSource, `video-${makeTimestamp()}.${ext}`, onNotify)
  }

  return (
    <div className="module-stack">
      <QuotaPanel items={quotaItems} />
      <div className="card-shell module-form-card">
        <h2 className="module-form-title">视频生成</h2>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">视频描述 / 分镜</label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="描述镜头、运动、风格，例如：城市雨夜、镜头推进、电影感灯光"
            className="field-input h-24 w-full resize-none"
          />
          <div className="mt-2 flex flex-wrap gap-2">
            {VIDEO_MOTION_PROMPTS.map((motion) => (
              <button
                key={motion}
                type="button"
                onClick={() => appendMotionPrompt(motion)}
                className="rounded-md border border-violet-200 bg-violet-50/55 px-2 py-1 text-[11px] text-violet-700 hover:border-violet-300 hover:bg-violet-100"
              >
                {motion}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">模型</label>
          <div className="grid gap-2 sm:grid-cols-2">
            {VIDEO_MODELS.map((item) => (
              <button
                key={item.id}
                onClick={() => setModel(item.id)}
                className={`rounded-lg border p-3 text-left transition ${
                  model === item.id
                    ? 'border-violet-300 bg-violet-100/80 text-violet-700'
                    : 'border-violet-100 bg-white/85 text-slate-700 hover:border-violet-200'
                }`}
              >
                <div className="text-sm font-medium">{item.label}</div>
                <div className="mt-0.5 text-xs text-slate-400">{item.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {model !== 'S2V-01' && (
          <div className="grid gap-4 rounded-xl border border-violet-100 bg-white/70 p-4 sm:grid-cols-2 lg:grid-cols-5">
            <div>
              <label className="mb-1 block text-xs text-slate-400">时长</label>
              <select
                value={duration}
                onChange={(e) => setDuration(parseInt(e.target.value, 10))}
                className="field-input w-full text-xs"
              >
                <option value={6}>6 秒</option>
                <option value={10} disabled={resolution === '1080P'}>10 秒</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">分辨率</label>
              <select
                value={resolution}
                onChange={(e) => setResolution(e.target.value)}
                className="field-input w-full text-xs"
              >
                {resolutionOptions.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-700">
              <input type="checkbox" checked={promptOptimizer} onChange={(e) => setPromptOptimizer(e.target.checked)} />
              提示词优化
            </label>
            <label className="flex items-center gap-2 text-xs text-slate-700">
              <input type="checkbox" checked={fastPretreatment} onChange={(e) => setFastPretreatment(e.target.checked)} />
              快速预处理
            </label>
            <label className="flex items-center gap-2 text-xs text-slate-700">
              <input type="checkbox" checked={aigcWatermark} onChange={(e) => setAigcWatermark(e.target.checked)} />
              AIGC 水印
            </label>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs text-slate-400">首帧图（可选）</label>
            <input ref={firstFrameInputRef} type="file" accept="image/*" onChange={(e) => handleFileUpload(e, setFirstFrame, setFirstFrameName)} className="block text-xs text-slate-600" />
            {firstFrame && <img src={firstFrame} alt="first frame" className="mt-2 h-16 w-full rounded object-cover" />}
            {firstFrame && (
              <button type="button" onClick={() => clearVideoFile(setFirstFrame, setFirstFrameName, firstFrameInputRef)} className="mt-2 text-xs text-rose-600 hover:text-rose-700">
                移除{firstFrameName ? `：${firstFrameName}` : ''}
              </button>
            )}
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">尾帧图（可选）</label>
            <input ref={lastFrameInputRef} type="file" accept="image/*" onChange={(e) => handleFileUpload(e, setLastFrame, setLastFrameName)} className="block text-xs text-slate-600" />
            {lastFrame && <img src={lastFrame} alt="last frame" className="mt-2 h-16 w-full rounded object-cover" />}
            {lastFrame && (
              <button type="button" onClick={() => clearVideoFile(setLastFrame, setLastFrameName, lastFrameInputRef)} className="mt-2 text-xs text-rose-600 hover:text-rose-700">
                移除{lastFrameName ? `：${lastFrameName}` : ''}
              </button>
            )}
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">角色参考图（可选）</label>
            <input ref={subjectImageInputRef} type="file" accept="image/*" onChange={(e) => handleFileUpload(e, setSubjectImage, setSubjectImageName)} className="block text-xs text-slate-600" />
            {subjectImage && <img src={subjectImage} alt="subject image" className="mt-2 h-16 w-full rounded object-cover" />}
            {subjectImage && (
              <button type="button" onClick={() => clearVideoFile(setSubjectImage, setSubjectImageName, subjectImageInputRef)} className="mt-2 text-xs text-rose-600 hover:text-rose-700">
                移除{subjectImageName ? `：${subjectImageName}` : ''}
              </button>
            )}
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={noWait}
            onChange={(e) => setNoWait(e.target.checked)}
          />
          快速返回（仅提交任务，稍后轮询结果）
        </label>

        <StatusMessage type="error" text={error} onRetry={handleGenerate} />

        {taskId && (
          <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-700">
            <div>任务已提交：{taskId}</div>
            <div className="mt-1 text-xs text-slate-600">每 10 秒自动轮询，可随时手动重试。</div>
            <button onClick={() => { void pollTask() }} className="btn-secondary mt-2 text-xs">立即轮询</button>
          </div>
        )}

        <div className="rounded-xl border border-violet-100 bg-violet-50/45 p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-sm font-medium text-slate-700">最近任务记录</div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-slate-400">
                {filteredTaskHistory.length}/{taskHistory.length}
              </span>
              <button
                onClick={clearTaskHistory}
                        className="rounded-md border border-violet-200 px-2 py-1 text-xs text-slate-600 hover:text-violet-700"
              >
                清空
              </button>
            </div>
          </div>
          <div className="mb-3 flex flex-wrap gap-2">
            <button
              onClick={() => setHistoryFilter('active')}
              className={`rounded-md border px-2 py-1 text-[11px] ${
                historyFilter === 'active'
                  ? 'border-sky-300 bg-sky-50 text-sky-700'
                  : 'border-violet-200 text-slate-600 hover:text-violet-700'
              }`}
            >
              进行中
            </button>
            <button
              onClick={() => setHistoryFilter('all')}
              className={`rounded-md border px-2 py-1 text-[11px] ${
                historyFilter === 'all'
                  ? 'border-sky-300 bg-sky-50 text-sky-700'
                  : 'border-violet-200 text-slate-600 hover:text-violet-700'
              }`}
            >
              全部
            </button>
            <button
              onClick={() => setHistoryFilter('success')}
              className={`rounded-md border px-2 py-1 text-[11px] ${
                historyFilter === 'success'
                  ? 'border-sky-300 bg-sky-50 text-sky-700'
                  : 'border-violet-200 text-slate-600 hover:text-violet-700'
              }`}
            >
              已完成
            </button>
            <button
              onClick={() => setHistoryFilter('failed')}
              className={`rounded-md border px-2 py-1 text-[11px] ${
                historyFilter === 'failed'
                  ? 'border-sky-300 bg-sky-50 text-sky-700'
                  : 'border-violet-200 text-slate-600 hover:text-violet-700'
              }`}
            >
              失败
            </button>
          </div>
          {taskHistory.length === 0 && (
            <div className="text-xs text-slate-400">暂无任务记录。开启“快速返回”提交后会自动记录。</div>
          )}
          {taskHistory.length > 0 && filteredTaskHistory.length === 0 && (
            <div className="text-xs text-slate-400">当前筛选条件下暂无任务。</div>
          )}
          {filteredTaskHistory.length > 0 && (
            <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
              {filteredTaskHistory.map((item) => (
                <div key={item.task_id} className="rounded-lg border border-violet-100 bg-white/75 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <button
                        onClick={() => {
                          const selectedTaskId = item.task_id
                          setTaskId(selectedTaskId)
                          setError('')
                          setResult(null)
                          stopPolling()
                          void pollTaskById(selectedTaskId)
                        }}
                        className="truncate text-xs text-sky-700 underline decoration-dotted underline-offset-2 hover:text-sky-800"
                      >
                        {item.task_id}
                      </button>
                      <button
                        onClick={() => { void copyTaskId(item.task_id) }}
                        className="rounded-md border border-violet-200 px-2 py-0.5 text-[11px] text-slate-600 hover:text-violet-700"
                      >
                        复制ID
                      </button>
                    </div>
                    <span className={`shrink-0 rounded-md border px-2 py-0.5 text-[11px] ${getStatusBadgeClass(item.status)}`}>
                      {item.status || 'Unknown'}
                    </span>
                  </div>
                  {item.model && (
                    <div className="mt-1 text-[11px] text-slate-600">模型：{item.model}</div>
                  )}
                  {item.prompt && (
                    <div className="mt-1 text-[11px] text-slate-400">
                      提示词：{item.prompt.length > 90 ? `${item.prompt.slice(0, 90)}...` : item.prompt}
                    </div>
                  )}
                  {item.message && (
                    <div className="mt-1 text-[11px] text-slate-400">状态：{item.message}</div>
                  )}
                  <div className="mt-1 text-[11px] text-slate-500">
                    更新时间：{formatTaskTime(item.updated_at || item.created_at) || '-'}
                  </div>
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={() => {
                        const selectedTaskId = item.task_id
                        setTaskId(selectedTaskId)
                        setError('')
                        setResult(null)
                        stopPolling()
                        void pollTaskById(selectedTaskId)
                      }}
                      className="rounded-md border border-violet-200 px-2 py-1 text-[11px] text-slate-600 hover:text-violet-700"
                    >
                      继续轮询
                    </button>
                    <button
                      onClick={() => removeTaskHistory(item.task_id)}
                      className="rounded-md border border-rose-300 px-2 py-1 text-[11px] text-rose-600 hover:text-rose-700"
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {result && (result.video_data || result.video_url) && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <div className="mb-2 text-sm text-emerald-700">
              视频生成成功
              {result.video_width ? ` · ${result.video_width}x${result.video_height}` : ''}
            </div>
            <video src={result.video_data || result.video_url} controls className="w-full rounded" />
            <button onClick={() => downloadVideo(result.video_data || result.video_url)} className="btn-secondary mt-3 text-sm">
              下载视频
            </button>
          </div>
        )}

        <button
          onClick={handleGenerate}
          disabled={isProcessing || !prompt.trim()}
          className="btn-primary w-full py-3"
        >
          {isProcessing ? '生成中...' : '开始生成视频'}
        </button>
      </div>
    </div>
  )
}

export default function Multimodal({ section = 'tts', onNotify, quotaItems, defaults = {} }) {
  if (section === 'music') return <MusicSection onNotify={onNotify} quotaItems={quotaItems} defaults={defaults} />
  if (section === 'video') return <VideoSection onNotify={onNotify} quotaItems={quotaItems} defaults={defaults} />
  return <TTSSection onNotify={onNotify} quotaItems={quotaItems} defaults={defaults} />
}
