import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiFetch, formatRunMessage, inferCapability, pollAgentRun, setSessionToken, streamAgentRun } from './qingqingApi'

afterEach(() => {
  setSessionToken('')
  vi.restoreAllMocks()
})

describe('qingqing API client', () => {
  it('attaches the signed session bearer without persisting it to localStorage', async () => {
    setSessionToken('signed-token')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    await apiFetch('/api/v1/models')
    const headers = fetch.mock.calls[0][1].headers
    expect(headers.get('Authorization')).toBe('Bearer signed-token')
    expect(localStorage.getItem('qingqing_session_token')).toBeNull()
  })

  it('never forwards the bearer token to an external asset URL', async () => {
    setSessionToken('signed-token')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    await apiFetch('https://assets.example.com/result.png')
    const headers = fetch.mock.calls[0][1].headers
    expect(headers.has('Authorization')).toBe(false)
  })

  it('polls until a terminal run status and formats chat output', async () => {
    let n = 0
    const fetchImpl = vi.fn(async () => {
      n += 1
      if (n === 1) return { ok: true, json: async () => ({ id: 'r1', status: 'running' }) }
      return {
        ok: true,
        json: async () => ({
          id: 'r1',
          status: 'completed',
          invocations: [{ capability: 'chat', output: { content: '最终答复' } }],
        }),
      }
    })
    const run = await pollAgentRun('r1', { fetchImpl, maxAttempts: 5 })
    expect(run.status).toBe('completed')
    expect(formatRunMessage(run)).toBe('最终答复')
    expect(formatRunMessage({ status: 'failed', error_code: 'provider_execution_failed' })).toMatch(/provider_execution_failed/)
  })

  it('parses SSE terminal events from the run event stream', async () => {
    const payload = {
      type: 'run_completed',
      status: 'completed',
      run: {
        id: 'r2',
        status: 'completed',
        invocations: [{ capability: 'chat', output: { content: '流式完成' } }],
      },
    }
    const sse = `event: snapshot\ndata: ${JSON.stringify({ type: 'snapshot', run: { id: 'r2', status: 'running' } })}\n\nevent: delta\ndata: ${JSON.stringify({ type: 'delta', delta: '流' })}\n\nevent: run_completed\ndata: ${JSON.stringify(payload)}\n\n`
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sse))
        controller.close()
      },
    })
    const deltas = []
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      body: stream,
      json: async () => ({}),
    }))
    const run = await streamAgentRun('r2', {
      fetchImpl,
      onEvent: (event) => {
        if (event.type === 'delta') deltas.push(event.data.delta)
      },
    })
    expect(run.status).toBe('completed')
    expect(formatRunMessage(run)).toBe('流式完成')
    expect(deltas).toEqual(['流'])
  })

  it('infers capability from natural language goals', () => {
    expect(inferCapability('做一张海报')).toBe('image')
    expect(inferCapability('生成配乐')).toBe('music')
    expect(inferCapability('旁白朗读这段文案')).toBe('tts')
    expect(inferCapability('15秒短视频')).toBe('video')
    expect(inferCapability('帮我写一段介绍')).toBe('chat')
  })
})
