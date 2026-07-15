import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import LoginPage from './LoginPage'

function Location() { return <span data-testid="location">{useLocation().pathname}</span> }

afterEach(() => {
  sessionStorage.clear()
  vi.restoreAllMocks()
})

describe('email login', () => {
  it('requests a code, verifies it and stores only the signed session token', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ accepted: true, dev_code: '123456' }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ access_token: 'signed-session' }) }))
    render(<MemoryRouter initialEntries={['/login']}><LoginPage /><Location /></MemoryRouter>)
    await userEvent.type(screen.getByLabelText('邮箱'), 'creator@example.com')
    await userEvent.click(screen.getByRole('button', { name: '获取验证码' }))
    expect(screen.getByLabelText('六位验证码')).toHaveValue('123456')
    await userEvent.click(screen.getByRole('button', { name: '登录并继续' }))
    expect(await screen.findByTestId('location')).toHaveTextContent('/chat')
    expect(sessionStorage.getItem('qingqing_session_token')).toBe('signed-session')
    expect(localStorage.getItem('qingqing_session_token')).toBeNull()
  })
})
