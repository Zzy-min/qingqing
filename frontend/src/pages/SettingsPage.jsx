import { useMemo, useState } from 'react'
import PageShell from '../components/PageShell'
import { useWorkbench } from '../context/WorkbenchContext'

function Field({ label, hint, children }) {
  return (
    <label className="settings-field">
      <span className="settings-field-label">{label}</span>
      {hint ? <span className="settings-field-hint">{hint}</span> : null}
      {children}
    </label>
  )
}

export default function SettingsPage() {
  const {
    settings,
    replaceSettings,
    validateApiKey,
    settingsValidation,
    apiKeySource
  } = useWorkbench()

  const [draft, setDraft] = useState(() => settings)
  const [saving, setSaving] = useState(false)

  const isChanged = useMemo(() => JSON.stringify(draft) !== JSON.stringify(settings), [draft, settings])

  const handleSave = () => {
    setSaving(true)
    replaceSettings(draft)
    window.setTimeout(() => setSaving(false), 180)
  }

  const updateDraft = (patch) => {
    setDraft((prev) => ({
      ...prev,
      ...patch,
      defaults: {
        ...prev.defaults,
        ...(patch.defaults || {})
      },
      defaultParams: {
        ...prev.defaultParams,
        ...(patch.defaultParams || {})
      },
      providerApiKeys: {
        ...(prev.providerApiKeys || {}),
        ...(patch.providerApiKeys || {})
      },
      providerBaseUrls: {
        ...(prev.providerBaseUrls || {}),
        ...(patch.providerBaseUrls || {})
      },
      providerSecrets: {
        ...(prev.providerSecrets || {}),
        ...(patch.providerSecrets || {})
      }
    }))
  }

  const handleValidateApiKey = async () => {
    if (isChanged) {
      replaceSettings(draft)
    }
    await validateApiKey()
  }

  return (
    <PageShell
      title="设置"
      description="管理本地工作台配置，包括 API Key、默认模型和默认参数。"
      extra={(
        <button
          type="button"
          disabled={!isChanged || saving}
          onClick={handleSave}
          className="btn-gradient"
        >
          {saving ? '保存中...' : '保存设置'}
        </button>
      )}
    >
      <section className="settings-grid-main">
        <div className="card-shell settings-card">
          <h3 className="section-title">主题与 API Key</h3>

          <Field label="主题模式">
            <select
              value={draft.theme || 'light'}
              onChange={(e) => updateDraft({ theme: e.target.value })}
              className="field-input"
            >
              <option value="light">亮色模式（推荐）</option>
              <option value="auto">跟随系统</option>
              <option value="dark">深色模式（实验）</option>
            </select>
          </Field>

          <Field
            label="MiniMax API Key"
            hint="保存在当前浏览器本地存储，发送请求时通过 X-MiniMax-API-Key 头覆盖。"
          >
            <input
              type="password"
              value={draft.apiKey}
              onChange={(e) => updateDraft({ apiKey: e.target.value })}
              placeholder="输入后点击保存"
              className="field-input"
            />
          </Field>

          <div className="settings-button-row">
            <button type="button" className="btn-secondary" onClick={() => void handleValidateApiKey()}>
              校验当前 Key
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => updateDraft({ apiKey: '' })}
            >
              清空覆盖 Key
            </button>
          </div>

          <div className="settings-status-card">
            <div>当前来源：{apiKeySource}</div>
            <div className="settings-status-line">
              最近校验：{settingsValidation.checkedAt ? settingsValidation.checkedAt.toLocaleString() : '未校验'}
            </div>
            <div className={`settings-status-message ${settingsValidation.ok ? 'settings-status-message-ok' : ''}`}>
              {settingsValidation.message || '点击"校验当前 Key"执行验证'}
            </div>
          </div>
        </div>

        <div className="card-shell settings-card">
          <h3 className="section-title">多供应商 API Key</h3>
          <p className="text-xs text-gray-500 mb-3">配置各供应商的 API Key，保存在浏览器本地。未配置的供应商在模型列表中显示为不可用。</p>

          {[
            { id: 'openai', name: 'OpenAI', placeholder: 'sk-...', hasBaseUrl: true, baseUrlPlaceholder: 'https://api.openai.com/v1' },
            { id: 'google', name: 'Google Gemini', placeholder: 'AIza...' },
            { id: 'qwen', name: '通义千问', placeholder: 'sk-...', hasBaseUrl: true, baseUrlPlaceholder: 'https://dashscope.aliyuncs.com/api/v1' },
            { id: 'ernie', name: '文心一言', placeholder: 'API Key', hasSecret: true, secretPlaceholder: 'Secret Key' },
            { id: 'zhipu', name: '智谱', placeholder: 'id.secret 格式' },
            { id: 'minimax', name: 'MiniMax', placeholder: '输入 MiniMax API Key' },
          ].map((provider) => (
            <div key={provider.id} className="mb-3 p-3 rounded-lg bg-gray-50 border border-gray-200">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-medium">{provider.name}</span>
                {draft.providerApiKeys?.[provider.id] && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">已配置</span>
                )}
              </div>
              <input
                type="password"
                value={draft.providerApiKeys?.[provider.id] || ''}
                onChange={(e) => updateDraft({
                  providerApiKeys: { ...(draft.providerApiKeys || {}), [provider.id]: e.target.value }
                })}
                placeholder={provider.placeholder}
                className="field-input mb-1"
              />
              {provider.hasBaseUrl && (
                <input
                  type="text"
                  value={draft.providerBaseUrls?.[provider.id] || ''}
                  onChange={(e) => updateDraft({
                    providerBaseUrls: { ...(draft.providerBaseUrls || {}), [provider.id]: e.target.value }
                  })}
                  placeholder={provider.baseUrlPlaceholder}
                  className="field-input mb-1 text-xs"
                />
              )}
              {provider.hasSecret && (
                <input
                  type="password"
                  value={draft.providerSecrets?.ernie || ''}
                  onChange={(e) => updateDraft({
                    providerSecrets: { ...(draft.providerSecrets || {}), ernie: e.target.value }
                  })}
                  placeholder={provider.secretPlaceholder}
                  className="field-input"
                />
              )}
            </div>
          ))}
        </div>

        <div className="card-shell settings-card">
          <h3 className="section-title">默认模型</h3>
          <Field label="照片模型">
            <select
              value={draft.defaults.photoModel}
              onChange={(e) => updateDraft({ defaults: { photoModel: e.target.value } })}
              className="field-input"
            >
              <option value="image-01">image-01</option>
              <option value="image-01-live">image-01-live</option>
            </select>
          </Field>

          <Field label="语音模型">
            <select
              value={draft.defaults.ttsModel}
              onChange={(e) => updateDraft({ defaults: { ttsModel: e.target.value } })}
              className="field-input"
            >
              <option value="speech-2.8-hd">speech-2.8-hd</option>
              <option value="speech-2.6-hd">speech-2.6-hd</option>
              <option value="speech-02-hd">speech-02-hd</option>
            </select>
          </Field>

          <Field label="音乐模型">
            <select
              value={draft.defaults.musicModel}
              onChange={(e) => updateDraft({ defaults: { musicModel: e.target.value } })}
              className="field-input"
            >
              <option value="music-2.6">music-2.6</option>
              <option value="music-2.5">music-2.5</option>
            </select>
          </Field>

          <Field label="视频模型">
            <select
              value={draft.defaults.videoModel}
              onChange={(e) => updateDraft({ defaults: { videoModel: e.target.value } })}
              className="field-input"
            >
              <option value="MiniMax-Hailuo-2.3">MiniMax-Hailuo-2.3</option>
              <option value="MiniMax-Hailuo-2.3-Fast">MiniMax-Hailuo-2.3-Fast</option>
              <option value="MiniMax-Hailuo-02">MiniMax-Hailuo-02</option>
              <option value="S2V-01">S2V-01</option>
            </select>
          </Field>
        </div>
      </section>

      <section className="card-shell settings-block-card">
        <h3 className="section-title">默认生成参数</h3>
        <div className="settings-default-grid">
          <Field label="默认 BPM">
            <input
              type="number"
              min={40}
              max={240}
              value={draft.defaultParams.musicBpm}
              onChange={(e) => updateDraft({ defaultParams: { musicBpm: Number(e.target.value || 0) } })}
              className="field-input"
            />
          </Field>

          <Field label="默认视频时长（秒）">
            <input
              type="number"
              min={3}
              max={10}
              value={draft.defaultParams.videoDuration}
              onChange={(e) => updateDraft({ defaultParams: { videoDuration: Number(e.target.value || 0) } })}
              className="field-input"
            />
          </Field>

          <Field label="默认视频分辨率">
            <select
              value={draft.defaultParams.videoResolution}
              onChange={(e) => updateDraft({ defaultParams: { videoResolution: e.target.value } })}
              className="field-input"
            >
              <option value="512P">512P</option>
              <option value="720P">720P</option>
              <option value="768P">768P</option>
              <option value="1080P">1080P</option>
            </select>
          </Field>
        </div>
      </section>

      <section className="settings-grid-meta">
        <div className="card-shell settings-card settings-card-compact">
          <h3 className="section-title">账号信息</h3>
          <div className="settings-info-grid">
            <div className="settings-info-row">
              <span className="settings-info-label">工作台身份</span>
              <span className="settings-info-value">创意探索者</span>
            </div>
            <div className="settings-info-row">
              <span className="settings-info-label">当前 API 来源</span>
              <span className="settings-info-value">{apiKeySource}</span>
            </div>
            <div className="settings-info-row">
              <span className="settings-info-label">运行模式</span>
              <span className="settings-info-value">本地多模态工作台</span>
            </div>
          </div>
        </div>

        <div className="card-shell settings-card settings-card-compact">
          <h3 className="section-title">本地工作台配置</h3>
          <div className="settings-info-grid">
            <div className="settings-info-row">
              <span className="settings-info-label">前端路由模式</span>
              <span className="settings-info-value">Browser Router</span>
            </div>
            <div className="settings-info-row">
              <span className="settings-info-label">统计存储</span>
              <span className="settings-info-value">浏览器 localStorage</span>
            </div>
            <div className="settings-info-row">
              <span className="settings-info-label">后端回退</span>
              <span className="settings-info-value">MINIMAX_API_KEY (.env)</span>
            </div>
          </div>
        </div>
      </section>
    </PageShell>
  )
}
