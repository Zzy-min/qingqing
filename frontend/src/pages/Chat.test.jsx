import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Chat from './Chat'

vi.mock('../context/WorkbenchContext', () => ({ useWorkbench: () => ({ settings: { credentialPreference: 'byok_first' } }) }))

afterEach(() => vi.restoreAllMocks())

describe('Chat routing controls', () => {
  it('uses BYOK preference, stage overrides and budget and exposes preview failure', async () => {
    Element.prototype.scrollIntoView = vi.fn()
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (String(url).includes('/models')) return { ok: true, json: async () => ({ models: [{ id: 'qwen:test', display_name: 'Test', capabilities: ['chat'], availability: 'available' }] }) }
      return { ok: false, json: async () => ({ detail: '没有符合预算的模型' }) }
    }))
    localStorage.setItem('mmx_workbench_settings_v1', JSON.stringify({ credentialPreference: 'byok_first' }))
    render(<Chat />)
    await userEvent.click(screen.getByRole('button', { name: '模型安排' }))
    await userEvent.clear(screen.getByLabelText('任务预算'))
    await userEvent.type(screen.getByLabelText('任务预算'), '0.5')
    await userEvent.type(screen.getByPlaceholderText(/输入消息/), '写一个故事')
    await userEvent.click(screen.getByRole('button', { name: '发送' }))
    await waitFor(() => expect(screen.getByText(/路由预览失败：没有符合预算的模型/)).toBeInTheDocument())
    const previewBody = JSON.parse(fetch.mock.calls.find(([url]) => String(url).includes('preview'))[1].body)
    expect(previewBody.credential_preference).toBe('byok_first')
    expect(previewBody.budget_limit).toBe(0.5)
    expect(previewBody.stage_overrides).toEqual({})
  })

  it('shows an explicit approval gate for an over-budget run', async () => {
    Element.prototype.scrollIntoView = vi.fn()
    vi.stubGlobal('crypto', { randomUUID: () => 'request-1' })
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (String(url).includes('/models')) return { ok: true, json: async () => ({ models: [] }) }
      if (String(url).includes('preview')) return { ok: true, json: async () => ({ selected_model: { display_name: 'Auto' }, reason: 'balanced', estimated_cost: { min: 0.8, max: 1 } }) }
      if (String(url).includes('/approve')) return { ok: true, json: async () => ({ id: 'run-1', status: 'planned' }) }
      if (String(url).includes('/execute')) return { ok: true, json: async () => ({ id: 'run-1', status: 'running' }) }
      if (String(url).includes('/agent/runs/run-1') && !String(url).includes('/execute') && !String(url).includes('/approve')) {
        return {
          ok: true,
          json: async () => ({
            id: 'run-1',
            status: 'completed',
            invocations: [{ capability: 'chat', output: { content: '预算确认后的最终回复' }, status: 'completed' }],
          }),
        }
      }
      return { ok: true, json: async () => ({ id: 'run-1', status: 'awaiting_approval', estimated_cost: 1 }) }
    }))
    render(<Chat />)
    await userEvent.type(screen.getByPlaceholderText(/输入消息/), '生成视频')
    await userEvent.click(screen.getByRole('button', { name: '发送' }))
    await screen.findByRole('button', { name: '确认执行' })
    const runCall = fetch.mock.calls.find(([url]) => String(url).endsWith('/agent/runs'))
    expect(runCall[1].headers.get('Idempotency-Key')).toBe('request-1')
    await userEvent.click(screen.getByRole('button', { name: '确认执行' }))
    await waitFor(() => expect(screen.getByText('预算确认后的最终回复')).toBeInTheDocument())
  })

  it('polls a planned run until the model output is available', async () => {
    Element.prototype.scrollIntoView = vi.fn()
    vi.stubGlobal('crypto', { randomUUID: () => 'request-2' })
    let pollCount = 0
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      const path = String(url)
      if (path.includes('/models')) return { ok: true, json: async () => ({ models: [] }) }
      if (path.includes('preview')) {
        return { ok: true, json: async () => ({ selected_model: { display_name: 'Auto' }, reason: 'balanced', estimated_cost: { min: 0.01, max: 0.02 } }) }
      }
      if (path.endsWith('/agent/runs') && !path.includes('run-2')) {
        return { ok: true, json: async () => ({ id: 'run-2', status: 'planned', estimated_cost: 0.02 }) }
      }
      if (path.includes('/execute')) return { ok: true, json: async () => ({ id: 'run-2', status: 'running' }) }
      if (path.includes('/agent/runs/run-2')) {
        pollCount += 1
        if (pollCount < 2) {
          return { ok: true, json: async () => ({ id: 'run-2', status: 'running', invocations: [] }) }
        }
        return {
          ok: true,
          json: async () => ({
            id: 'run-2',
            status: 'completed',
            invocations: [{ capability: 'chat', status: 'completed', output: { content: '你好，这是模型的真实回复' } }],
          }),
        }
      }
      return { ok: false, json: async () => ({ detail: 'unexpected' }) }
    }))
    render(<Chat />)
    await userEvent.type(screen.getByPlaceholderText(/输入消息/), '你好')
    await userEvent.click(screen.getByRole('button', { name: '发送' }))
    await waitFor(() => expect(screen.getByText('你好，这是模型的真实回复')).toBeInTheDocument(), { timeout: 5000 })
    expect(pollCount).toBeGreaterThanOrEqual(2)
  })
})
