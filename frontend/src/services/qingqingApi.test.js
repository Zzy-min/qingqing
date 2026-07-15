import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiFetch, setSessionToken } from './qingqingApi'

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
})
