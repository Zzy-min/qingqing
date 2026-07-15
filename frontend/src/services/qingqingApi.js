const SESSION_TOKEN_KEY = 'qingqing_session_token'

export function getSessionToken() {
  if (typeof window === 'undefined') return ''
  return window.sessionStorage.getItem(SESSION_TOKEN_KEY) || ''
}

export function setSessionToken(token) {
  if (typeof window === 'undefined') return
  if (token) window.sessionStorage.setItem(SESSION_TOKEN_KEY, token)
  else window.sessionStorage.removeItem(SESSION_TOKEN_KEY)
  window.dispatchEvent(new Event('qingqing-session-changed'))
}

export function apiFetch(input, init = {}) {
  const token = getSessionToken()
  const headers = new Headers(init.headers || {})
  const target = new URL(input, window.location.href)
  if (token && target.origin === window.location.origin && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return fetch(input, { ...init, headers })
}

export { SESSION_TOKEN_KEY }
