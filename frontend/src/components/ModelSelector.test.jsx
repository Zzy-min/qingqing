import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ModelSelector from './ModelSelector'

afterEach(() => vi.restoreAllMocks())

describe('ModelSelector', () => {
  it('defaults to Auto and exposes only selectable compatible models', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: [
        { id: 'openai:gpt-4o', provider: 'OpenAI', display_name: 'GPT-4o', capabilities: ['chat'], availability: 'available', speed_tier: 'fast', cost_tier: 'medium' },
        { id: 'vip:model', provider: 'Example', display_name: 'VIP Model', capabilities: ['chat'], availability: 'locked', unavailable_reason: '需要相应权益', vip_required: true },
      ] })
    }))
    const onChange = vi.fn()
    render(<ModelSelector capability="chat" value="auto" onChange={onChange} />)

    expect(screen.getByRole('option', { name: /Auto/ })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('option', { name: /GPT-4o/ })).toBeInTheDocument())
    expect(screen.getByRole('option', { name: /VIP Model/ })).toBeDisabled()
    await userEvent.selectOptions(screen.getByRole('combobox'), 'openai:gpt-4o')
    expect(onChange).toHaveBeenCalledWith('openai:gpt-4o')
  })
})

