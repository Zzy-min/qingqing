import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch, setSessionToken } from '../services/qingqingApi'

export default function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [step, setStep] = useState('email')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const requestCode = async (event) => {
    event.preventDefault(); setBusy(true); setError('')
    const response = await apiFetch('/api/v1/auth/email/request-code', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) })
    const payload = await response.json().catch(() => ({})); setBusy(false)
    if (!response.ok) return setError('验证码发送失败，请稍后重试')
    if (payload.dev_code) setCode(payload.dev_code)
    setStep('code')
  }

  const verifyCode = async (event) => {
    event.preventDefault(); setBusy(true); setError('')
    const response = await apiFetch('/api/v1/auth/email/verify', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, code }) })
    const payload = await response.json().catch(() => ({})); setBusy(false)
    if (!response.ok || !payload.access_token) return setError('验证码无效或已过期')
    setSessionToken(payload.access_token); navigate('/chat', { replace: true })
  }

  return <main className="flex min-h-screen items-center justify-center bg-[#f4f7ff] px-5 py-12 text-slate-900">
    <section className="w-full max-w-md rounded-[28px] border border-indigo-100 bg-white p-8 shadow-[0_24px_80px_rgba(77,91,150,0.16)]">
      <div className="mb-8 flex items-center gap-3"><span className="grid h-12 w-12 place-items-center rounded-2xl bg-indigo-600 text-xl font-bold text-white">轻</span><div><h1 className="text-2xl font-semibold">登录轻青</h1><p className="text-sm text-slate-500">让创作任务在所有设备保持同步</p></div></div>
      {step === 'email' ? <form onSubmit={requestCode} className="space-y-5">
        <label className="block text-sm font-medium">邮箱<input required type="email" aria-label="邮箱" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="creator@example.com" className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 outline-none focus:border-indigo-500" /></label>
        <button disabled={busy} className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-medium text-white disabled:opacity-50">{busy ? '发送中…' : '获取验证码'}</button>
      </form> : <form onSubmit={verifyCode} className="space-y-5">
        <p className="text-sm text-slate-600">验证码已发送到 <strong>{email}</strong></p>
        <label className="block text-sm font-medium">六位验证码<input required inputMode="numeric" pattern="[0-9]{6}" aria-label="六位验证码" value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))} className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-center text-2xl tracking-[0.35em] outline-none focus:border-indigo-500" /></label>
        <button disabled={busy} className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-medium text-white disabled:opacity-50">{busy ? '验证中…' : '登录并继续'}</button>
        <button type="button" onClick={() => setStep('email')} className="w-full text-sm text-indigo-600">更换邮箱</button>
      </form>}
      {error && <p role="alert" className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      <p className="mt-7 text-xs leading-5 text-slate-400">登录即表示你同意轻青仅为同步创作任务和保护账户而处理必要数据。</p>
    </section>
  </main>
}
