import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiFetch, formatRunMessage, pollAgentRun, setSessionToken } from './qingqingApi'

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
})
