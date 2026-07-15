import { useState } from 'react'
import ModelSelector from './ModelSelector'
import { useWorkbench } from '../context/WorkbenchContext'
import { apiFetch, followAgentRun, formatRunMessage } from '../services/qingqingApi'

const CAPABILITY_LABEL = {
  chat: '对话 / 文案',
  image: '图片',
  tts: '语音',
  music: '音乐',
  video: '视频',
}

/**
 * Shared AgentRun UI for modality pages and dashboard shortcuts.
 * Creates /api/v1 runs, handles budget approval, follows SSE (with poll fallback).
 */
export default function AgentRunComposer({
  capability = 'chat',
  title,
  description,
  placeholder = '描述你想创作的内容…',
  defaultBudget = '10',
}) {
  const { settings, pushToast } = useWorkbench()
  const [goal, setGoal] = useState('')
  const [model, setModel] = useState('auto')
  const [budgetLimit, setBudgetLimit] = useState(defaultBudget)
  const [busy, setBusy] = useState(false)
  const [pendingRun, setPendingRun] = useState(null)
  const [statusText, setStatusText] = useState('')
  const [resultText, setResultText] = useState('')
  const [resultRun, setResultRun] = useState(null)
  const [routeError, setRouteError] = useState('')
  const [streamBuffer, setStreamBuffer] = useState('')

  const buildRouting = () => ({
    mode: model === 'auto' ? 'auto' : 'preferred',
    credential_preference: settings.credentialPreference || 'platform_first',
    preferred_model_id: model === 'auto' ? null : model,
    stage_overrides: {},
    budget_limit: budgetLimit === '' ? null : Number(budgetLimit),
  })

  const follow = async (runId) => {
    setStreamBuffer('')
    setStatusText('执行中，接收事件流…')
    const finished = await followAgentRun(runId, {
      onDelta: (delta) => {
        setStreamBuffer((prev) => prev + delta)
        setResultText((prev) => (prev || '') + delta)
      },
    })
    setResultRun(finished)
    setResultText((prev) => prev || formatRunMessage(finished))
    setStatusText(finished.status === 'completed' ? '已完成' : `状态：${finished.status}`)
    return finished
  }

  const executeAndFollow = async (runId) => {
    const executeResp = await apiFetch(`/api/v1/agent/runs/${encodeURIComponent(runId)}/execute`, { method: 'POST' })
    if (!executeResp.ok) {
      const failure = await executeResp.json().catch(() => ({}))
      throw new Error(failure.detail || '启动执行失败')
    }
    return follow(runId)
  }

  const createRun = async () => {
    if (!goal.trim() || busy) return
    setBusy(true)
    setRouteError('')
    setResultText('')
    setResultRun(null)
    setPendingRun(null)
    setStatusText('创建任务…')
    try {
      const routing = buildRouting()
      const previewResp = await apiFetch('/api/v1/model-routes/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capability, ...routing }),
      })
      if (!previewResp.ok) {
        const failure = await previewResp.json().catch(() => ({}))
        throw new Error(failure.detail || '路由预览失败')
      }
      const requestId = typeof crypto?.randomUUID === 'function' ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`
      const resp = await apiFetch('/api/v1/agent/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestId },
        body: JSON.stringify({ goal: goal.trim(), routing: { ...routing, capability } }),
      })
      if (!resp.ok) throw new Error((await resp.json().catch(() => ({}))).detail || '创建任务失败')
      const run = await resp.json()
      if (run.status === 'awaiting_approval') {
        setPendingRun(run)
        setStatusText(formatRunMessage(run))
        return
      }
      if (run.status === 'planned') {
        await executeAndFollow(run.id)
        return
      }
      if (run.status === 'running') {
        await follow(run.id)
        return
      }
      setResultRun(run)
      setResultText(formatRunMessage(run))
      setStatusText(run.status)
    } catch (error) {
      setRouteError(error.message)
      pushToast?.('error', error.message)
    } finally {
      setBusy(false)
    }
  }

  const resolveApproval = async (action) => {
    if (!pendingRun || busy) return
    setBusy(true)
    try {
      const response = await apiFetch(`/api/v1/agent/runs/${encodeURIComponent(pendingRun.id)}/${action}`, { method: 'POST' })
      if (!response.ok) throw new Error(action === 'approve' ? '确认失败' : '取消失败')
      const run = await response.json()
      setPendingRun(null)
      if (action === 'cancel') {
        setStatusText('任务已取消')
        return
      }
      await executeAndFollow(run.id)
    } catch (error) {
      setRouteError(error.message)
      pushToast?.('error', error.message)
    } finally {
      setBusy(false)
    }
  }

  const artifactHint = (() => {
    const inv = resultRun?.invocations?.find((item) => item?.output)
    const out = inv?.output
    if (!out) return null
    if (out.content_url) return out.content_url
    if (out.audio_url) return out.audio_url
    if (out.video_url) return out.video_url
    if (out.images?.[0]?.url) return out.images[0].url
    if (out.url) return out.url
    return null
  })()

  return (
    <div className="card-shell space-y-4 p-4 md:p-6">
      <div>
        <h3 className="text-lg font-semibold text-slate-800">{title || `${CAPABILITY_LABEL[capability] || capability} 创作`}</h3>
        {description ? <p className="mt-1 text-sm text-slate-500">{description}</p> : null}
        <p className="mt-1 text-xs text-teal-700">经轻青 AgentRun · 路由透明 · 预算可控 · SSE 进度</p>
      </div>

      <div className="grid gap-3 md:grid-cols-[1fr_140px_120px]">
        <ModelSelector capability={capability} value={model} onChange={setModel} />
        <label className="text-sm text-slate-600">
          任务预算
          <input
            type="number"
            min="0"
            step="0.1"
            value={budgetLimit}
            onChange={(e) => setBudgetLimit(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            disabled={busy}
          />
        </label>
        <div className="flex items-end">
          <button
            type="button"
            onClick={createRun}
            disabled={busy || !goal.trim()}
            className="w-full rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-500 disabled:opacity-50"
          >
            {busy ? '处理中…' : '开始创作'}
          </button>
        </div>
      </div>

      <textarea
        value={goal}
        onChange={(e) => setGoal(e.target.value)}
        rows={5}
        placeholder={placeholder}
        disabled={busy}
        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-teal-500"
      />

      {routeError ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{routeError}</div> : null}
      {statusText ? <div className="text-sm text-slate-600">{statusText}</div> : null}

      {pendingRun ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <span>预计消耗 {pendingRun.estimated_cost} 额度，超出预算，需确认。</span>
          <span className="flex gap-2">
            <button type="button" className="rounded-lg bg-amber-500 px-3 py-1 text-white" disabled={busy} onClick={() => resolveApproval('approve')}>确认执行</button>
            <button type="button" className="rounded-lg border border-amber-400 px-3 py-1" disabled={busy} onClick={() => resolveApproval('cancel')}>取消</button>
          </span>
        </div>
      ) : null}

      {(resultText || streamBuffer) ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">结果</div>
          <pre className="whitespace-pre-wrap font-sans text-sm text-slate-800">{resultText || streamBuffer}</pre>
          {artifactHint ? (
            <a href={artifactHint} target="_blank" rel="noreferrer" className="mt-3 inline-block text-sm text-teal-700 underline">
              打开产物
            </a>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
