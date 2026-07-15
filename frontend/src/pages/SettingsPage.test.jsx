import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SettingsPage from './SettingsPage'

vi.mock('../context/WorkbenchContext', () => ({
  useWorkbench: () => ({
    settings: { theme: 'light', advancedModeEnabled: false, defaults: {}, defaultParams: {} },
    replaceSettings: vi.fn(), validateApiKey: vi.fn(), settingsValidation: {}, apiKeySource: '平台托管'
  })
}))

describe('SettingsPage advanced mode', () => {
  beforeEach(() => {
    global.fetch = vi.fn(async (_url, options = {}) => ({
      ok: true,
      json: async () => options.method === 'PATCH'
        ? { advanced_mode_enabled: true, credential_preference: 'platform_first' }
        : { advanced_mode_enabled: false, credential_preference: 'platform_first' }
    }))
  })
  it('keeps API management hidden until the user accepts the warning', async () => {
    render(<SettingsPage />)
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/me/preferences', expect.any(Object)))
    expect(screen.queryByText('模型与 API')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('checkbox', { name: /启用高阶模式/ }))
    expect(screen.getByText(/API 费用由相应供应商账户承担/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '我已了解并启用' }))
    expect(screen.getByText('模型与 API')).toBeInTheDocument()
  })

  it('loads and deletes credentials and creates a custom model after enabling advanced mode', async () => {
    global.fetch = vi.fn(async (url, options = {}) => {
      if (url === '/api/v1/me/preferences') return {
        ok: true,
        json: async () => options.method === 'PATCH'
          ? { advanced_mode_enabled: true, credential_preference: 'platform_first' }
          : { advanced_mode_enabled: false, credential_preference: 'platform_first' }
      }
      if (url === '/api/v1/credentials' && !options.method) return { ok: true, json: async () => [{ id: 'cred-1', provider: 'openai', key_last4: '1234' }] }
      if (url === '/api/v1/custom-models' && !options.method) return { ok: true, json: async () => [] }
      if (options.method === 'DELETE') return { ok: true }
      if (url === '/api/v1/custom-models') return { ok: true, json: async () => ({ id: 'custom:1', display_name: '我的模型' }) }
      return { ok: true, json: async () => ({}) }
    })
    render(<SettingsPage />)
    await userEvent.click(screen.getByRole('checkbox', { name: /启用高阶模式/ }))
    await userEvent.click(screen.getByRole('button', { name: '我已了解并启用' }))
    await userEvent.click(await screen.findByRole('button', { name: '删除 openai 凭据' }))
    expect(fetch).toHaveBeenCalledWith('/api/v1/credentials/cred-1', expect.objectContaining({ method: 'DELETE' }))
    await userEvent.selectOptions(screen.getByLabelText('供应商'), 'openai_compatible')
    await userEvent.type(screen.getByLabelText('服务名称'), '我的模型')
    await userEvent.type(screen.getByLabelText('Base URL'), 'https://api.example.com/v1')
    await userEvent.type(screen.getByLabelText('自定义 API Key'), 'secret-key')
    await userEvent.type(screen.getByLabelText('模型 ID'), 'model-x')
    await userEvent.click(screen.getByRole('button', { name: '添加自定义模型' }))
    await screen.findByText(/我的模型/)
  })
})
