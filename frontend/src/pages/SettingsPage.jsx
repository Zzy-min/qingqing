import { useEffect, useState } from 'react'
import PageShell from '../components/PageShell'
import { useWorkbench } from '../context/WorkbenchContext'
import { apiFetch } from '../services/qingqingApi'

const EMPTY_CREDENTIAL = { provider: 'openai', api_key: '', base_url: '', name: '', model_id: '', capabilities: ['chat'] }

export default function SettingsPage() {
  const { settings, replaceSettings, pushToast = () => {} } = useWorkbench()
  const [advanced, setAdvanced] = useState(settings.advancedModeEnabled === true)
  const [showWarning, setShowWarning] = useState(false)
  const [credentials, setCredentials] = useState([])
  const [form, setForm] = useState(EMPTY_CREDENTIAL)
  const [customModels, setCustomModels] = useState([])
  const [memoryEnabled, setMemoryEnabled] = useState(true)
  const [styleNotes, setStyleNotes] = useState('')
  const [avoidNotes, setAvoidNotes] = useState('')
  const [preferredTone, setPreferredTone] = useState('')
  const [memoryItems, setMemoryItems] = useState([])
  const [memoryNote, setMemoryNote] = useState('')
  const [tools, setTools] = useState([])

  const reloadMemory = () => {
    apiFetch('/api/v1/memory?limit=20')
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((data) => setMemoryItems(data.items || []))
      .catch(() => {})
  }

  useEffect(() => {
    let activeRequest = true
    apiFetch('/api/v1/me/preferences')
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('偏好加载失败')))
      .then((preferences) => {
        if (!activeRequest) return
        const advancedModeEnabled = preferences.advanced_mode_enabled === true
        const credentialPreference = preferences.credential_preference || 'platform_first'
        setAdvanced(advancedModeEnabled)
        setMemoryEnabled(preferences.memory_enabled !== false)
        setStyleNotes(preferences.style_notes || '')
        setAvoidNotes(preferences.avoid_notes || '')
        setPreferredTone(preferences.preferred_tone || '')
        replaceSettings({ ...settings, advancedModeEnabled, credentialPreference })
      })
      .catch(() => {})
    reloadMemory()
    apiFetch('/api/v1/tools')
      .then((r) => (r.ok ? r.json() : { tools: [] }))
      .then((data) => setTools(data.tools || []))
      .catch(() => {})
    return () => { activeRequest = false }
  }, [])

  useEffect(() => {
    if (!advanced) return
    Promise.all([apiFetch('/api/v1/credentials').then((r) => r.ok ? r.json() : []), apiFetch('/api/v1/custom-models').then((r) => r.ok ? r.json() : [])]).then(([credentialsPayload, modelsPayload]) => {
      setCredentials(Array.isArray(credentialsPayload) ? credentialsPayload : (credentialsPayload.data || []))
      setCustomModels(Array.isArray(modelsPayload) ? modelsPayload : (modelsPayload.data || []))
    }).catch(() => {})
  }, [advanced])

  const persistAdvanced = async (enabled) => {
    const response = await apiFetch('/api/v1/me/preferences', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ advanced_mode_enabled: enabled }) })
    if (!response.ok) return pushToast('error', '高阶模式设置保存失败')
    setAdvanced(enabled)
    replaceSettings({ ...settings, advancedModeEnabled: enabled })
  }

  const onToggle = (event) => {
    if (event.target.checked && !advanced) setShowWarning(true)
    else void persistAdvanced(false)
  }

  const saveCredential = async (event) => {
    event.preventDefault()
    const compatible = form.provider === 'openai_compatible'
    const endpoint = compatible ? '/api/v1/custom-models' : '/api/v1/credentials'
    const body = compatible ? form : { provider: form.provider, api_key: form.api_key }
    const response = await apiFetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    if (!response.ok) return pushToast('error', '凭据保存失败，请检查配置')
    const item = await response.json()
    if (compatible) setCustomModels((current) => [...current, item.data || item])
    else setCredentials((current) => [...current, item.data || item])
    setForm(EMPTY_CREDENTIAL)
    pushToast('success', '凭据已加密保存')
  }

  const removeCredential = async (id) => {
    const response = await apiFetch(`/api/v1/credentials/${encodeURIComponent(id)}`, { method: 'DELETE' })
    if (response.ok) setCredentials((current) => current.filter((item) => item.id !== id))
  }

  const testCredential = async (id) => {
    const response = await apiFetch(`/api/v1/credentials/${encodeURIComponent(id)}/test`, { method: 'POST' })
    pushToast(response.ok ? 'success' : 'error', response.ok ? '凭据连接验证通过' : '凭据验证失败，请检查后重试')
  }

  const removeCustomModel = async (id) => {
    const response = await apiFetch(`/api/v1/custom-models/${encodeURIComponent(id)}`, { method: 'DELETE' })
    if (response.ok) setCustomModels((current) => current.filter((item) => item.id !== id))
  }

  return (
    <PageShell title="设置" description="管理轻青的体验偏好。高阶功能与账户权益相互独立。">
      <section className="card-shell settings-card mb-5">
        <h3 className="section-title">通用设置</h3>
        <label className="settings-field">
          <span className="settings-field-label">主题模式</span>
          <select className="field-input" value={settings.theme || 'light'} onChange={(event) => replaceSettings({ ...settings, theme: event.target.value })}>
            <option value="light">亮色模式</option><option value="auto">跟随系统</option><option value="dark">深色模式</option>
          </select>
        </label>
        <label className="settings-field">
          <span className="settings-field-label">API 使用策略</span>
          <select className="field-input" value={settings.credentialPreference || 'platform_first'} onChange={async (event) => { const value = event.target.value; const response = await apiFetch('/api/v1/me/preferences', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ credential_preference: value }) }); if (response.ok) replaceSettings({ ...settings, credentialPreference: value }); else pushToast('error', 'API 使用策略保存失败') }}>
            <option value="platform_first">平台优先</option><option value="byok_first">我的 API 优先</option><option value="byok_only">仅使用我的 API</option>
          </select>
        </label>
      </section>

      <section className="card-shell settings-card mb-5">
        <h3 className="section-title">默认创作设置</h3>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="settings-field"><span className="settings-field-label">默认 BPM</span><input className="field-input" type="number" min="40" max="240" value={settings.defaultParams?.musicBpm ?? 120} onChange={(e) => replaceSettings({ ...settings, defaultParams: { ...settings.defaultParams, musicBpm: Number(e.target.value) } })} /></label>
          <label className="settings-field"><span className="settings-field-label">视频时长（秒）</span><input className="field-input" type="number" min="3" max="10" value={settings.defaultParams?.videoDuration ?? 6} onChange={(e) => replaceSettings({ ...settings, defaultParams: { ...settings.defaultParams, videoDuration: Number(e.target.value) } })} /></label>
          <label className="settings-field"><span className="settings-field-label">视频分辨率</span><select className="field-input" value={settings.defaultParams?.videoResolution ?? '768P'} onChange={(e) => replaceSettings({ ...settings, defaultParams: { ...settings.defaultParams, videoResolution: e.target.value } })}><option>512P</option><option>720P</option><option>768P</option><option>1080P</option></select></label>
        </div>
      </section>

      <section className="card-shell settings-card mb-5">
        <h3 className="section-title">记忆与风格</h3>
        <p className="mb-3 text-xs text-gray-500">完成创作后自动写入摘要；对话任务会注入相关记忆与风格偏好。</p>
        <label className="mb-3 flex items-center gap-3 text-sm">
          <input
            type="checkbox"
            checked={memoryEnabled}
            onChange={async (e) => {
              const enabled = e.target.checked
              const response = await apiFetch('/api/v1/me/preferences', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ memory_enabled: enabled }),
              })
              if (response.ok) setMemoryEnabled(enabled)
              else pushToast('error', '记忆开关保存失败')
            }}
          />
          <span>启用跨会话记忆</span>
        </label>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="settings-field">
            <span className="settings-field-label">语气</span>
            <input className="field-input" value={preferredTone} onChange={(e) => setPreferredTone(e.target.value)} placeholder="温和 / 专业 / 活泼" />
          </label>
          <label className="settings-field md:col-span-1">
            <span className="settings-field-label">风格笔记</span>
            <input className="field-input" value={styleNotes} onChange={(e) => setStyleNotes(e.target.value)} placeholder="留白、浅青、低饱和…" />
          </label>
          <label className="settings-field">
            <span className="settings-field-label">避免</span>
            <input className="field-input" value={avoidNotes} onChange={(e) => setAvoidNotes(e.target.value)} placeholder="过密排版、霓虹高饱和…" />
          </label>
        </div>
        <button
          type="button"
          className="btn-secondary mt-3"
          onClick={async () => {
            const response = await apiFetch('/api/v1/me/preferences', {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                style_notes: styleNotes,
                avoid_notes: avoidNotes,
                preferred_tone: preferredTone,
              }),
            })
            pushToast(response.ok ? 'success' : 'error', response.ok ? '风格偏好已保存' : '风格偏好保存失败')
          }}
        >
          保存风格偏好
        </button>
        <div className="mt-4 flex gap-2">
          <input
            className="field-input flex-1"
            value={memoryNote}
            onChange={(e) => setMemoryNote(e.target.value)}
            placeholder="手动添加一条记忆笔记…"
          />
          <button
            type="button"
            className="btn-gradient"
            onClick={async () => {
              if (!memoryNote.trim()) return
              const response = await apiFetch('/api/v1/memory', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: memoryNote.trim(), kind: 'note' }),
              })
              if (!response.ok) return pushToast('error', '记忆添加失败')
              setMemoryNote('')
              reloadMemory()
              pushToast('success', '记忆已添加')
            }}
          >
            添加
          </button>
        </div>
        <div className="mt-3 max-h-48 space-y-2 overflow-y-auto">
          {memoryItems.length === 0 ? (
            <p className="text-sm text-gray-500">暂无记忆。完成一次创作后会自动出现摘要。</p>
          ) : (
            memoryItems.map((item) => (
              <div key={item.id} className="flex items-start justify-between gap-2 rounded-lg border border-gray-200 p-3 text-sm">
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-gray-400">{item.kind} · {item.created_at ? new Date(item.created_at).toLocaleString() : ''}</div>
                  <div className="mt-1 whitespace-pre-wrap text-gray-700">{item.content}</div>
                </div>
                <button
                  type="button"
                  className="btn-secondary shrink-0"
                  onClick={async () => {
                    const response = await apiFetch(`/api/v1/memory/${encodeURIComponent(item.id)}`, { method: 'DELETE' })
                    if (response.ok) setMemoryItems((cur) => cur.filter((m) => m.id !== item.id))
                  }}
                >
                  删除
                </button>
              </div>
            ))
          )}
        </div>
        {tools.length > 0 ? (
          <div className="mt-4 border-t border-gray-100 pt-3">
            <div className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">内置工具（审计可调用）</div>
            <div className="flex flex-wrap gap-2">
              {tools.map((tool) => (
                <span key={tool.name} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600" title={tool.description}>
                  {tool.name}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <section className="card-shell settings-card">
        <h3 className="section-title">高阶选项</h3>
        <label className="flex items-center gap-3 text-sm">
          <input type="checkbox" aria-label="启用高阶模式" checked={advanced || showWarning} onChange={onToggle} />
          <span>启用高阶模式</span>
        </label>
        <p className="mt-2 text-xs text-gray-500">适合了解模型 API 的用户；与账户权益无关。</p>

        {showWarning && !advanced && (
          <div role="dialog" aria-label="高阶模式说明" className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <p>API 费用由相应供应商账户承担。轻青只在执行你的任务时使用凭据；自定义端点可能带来数据与隐私风险。</p>
            <div className="mt-3 flex gap-2"><button className="btn-gradient" onClick={async () => { setShowWarning(false); await persistAdvanced(true) }}>我已了解并启用</button><button className="btn-secondary" onClick={() => setShowWarning(false)}>取消</button></div>
          </div>
        )}

        {advanced && (
          <div className="mt-6 border-t border-gray-200 pt-5">
            <h3 className="section-title">模型与 API</h3>
            <p className="mb-4 text-xs text-gray-500">密钥提交到服务端加密保存，保存后不会再次显示明文。</p>
            <form onSubmit={saveCredential} className="grid gap-3 md:grid-cols-2">
              <select aria-label="供应商" className="field-input" value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}>
                <option value="openai">OpenAI</option><option value="google">Google Gemini</option><option value="qwen">通义千问</option><option value="minimax">MiniMax</option><option value="openai_compatible">OpenAI 兼容服务</option>
              </select>
              <input aria-label="服务名称" className="field-input" placeholder="显示名称" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <input aria-label={form.provider === 'openai_compatible' ? '自定义 API Key' : 'API Key'} required type="password" className="field-input" placeholder="API Key" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
              {form.provider === 'openai_compatible' && <input aria-label="Base URL" required type="url" className="field-input" placeholder="https://example.com/v1" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} />}
              {form.provider === 'openai_compatible' && <input aria-label="模型 ID" required className="field-input" placeholder="模型 ID" value={form.model_id} onChange={(e) => setForm({ ...form, model_id: e.target.value })} />}
              <button className="btn-gradient md:col-span-2" type="submit">{form.provider === 'openai_compatible' ? '添加自定义模型' : '加密保存凭据'}</button>
            </form>
            <div className="mt-5 space-y-2">{credentials.length === 0 ? <p className="text-sm text-gray-500">尚未配置我的 API</p> : credentials.map((item) => <div key={item.id} className="flex items-center justify-between rounded-lg border border-gray-200 p-3 text-sm"><span>{item.name || item.provider} · ••••{item.key_last4 || item.last_four || ''}</span><span className="flex gap-2"><button aria-label={`测试 ${item.provider} 凭据`} className="btn-secondary" onClick={() => testCredential(item.id)}>测试</button><button aria-label={`删除 ${item.provider} 凭据`} className="btn-secondary" onClick={() => removeCredential(item.id)}>删除</button></span></div>)}</div>
            <div className="mt-5 space-y-2">{customModels.map((item) => <div key={item.id} className="flex items-center justify-between rounded-lg border border-gray-200 p-3 text-sm"><span>{item.display_name} · {item.remote_model_id}</span><button aria-label={`删除自定义模型 ${item.display_name}`} className="btn-secondary" onClick={() => removeCustomModel(item.id)}>删除</button></div>)}</div>
          </div>
        )}
      </section>
    </PageShell>
  )
}
