import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'
import { useWorkbench } from '../context/WorkbenchContext'

function QingQingLogo() {
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true" className="h-10 w-10">
      <defs>
        <linearGradient id="minimax-logo-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#6d7cff" />
          <stop offset="50%" stopColor="#9d5bff" />
          <stop offset="100%" stopColor="#ff78c8" />
        </linearGradient>
      </defs>
      <rect x="6" y="6" width="52" height="52" rx="16" fill="url(#minimax-logo-gradient)" opacity="0.14" />
      <path
        d="M16 46V18l12 14 12-14v28M28 32h8"
        fill="none"
        stroke="url(#minimax-logo-gradient)"
        strokeWidth="6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function BellIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 0 0-12 0v3.2a2 2 0 0 1-.6 1.4L4 17h5" />
      <path d="M10 19a2 2 0 0 0 4 0" />
    </svg>
  )
}

const PAGE_TITLES = {
  '/dashboard': '工作台总览',
  '/chat': 'Chat',
  '/photo': '照片编辑',
  '/voice': '语音合成',
  '/music': '音乐生成',
  '/video': '视频生成',
  '/token': 'Token Plan',
  '/usage': '用量分析',
  '/help': '帮助文档',
  '/api-docs': 'API 文档',
  '/settings': '设置'
}

export default function MainLayout() {
  const {
    navGroups,
    tokenPlanState,
    tokenPlanSummary,
    fetchTokenPlanRemains,
    apiKeySource
  } = useWorkbench()
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const currentPageTitle = useMemo(() => PAGE_TITLES[location.pathname] || '多模态工作台', [location.pathname])

  const closeSidebar = () => setSidebarOpen(false)

  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  return (
    <div className="workspace-shell">
      {sidebarOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          onClick={closeSidebar}
          aria-label="关闭侧边导航"
        />
      )}
      <aside className={`workspace-sidebar ${sidebarOpen ? 'workspace-sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <QingQingLogo />
          <div>
            <div className="brand-title">轻青</div>
            <div className="brand-subtitle">个人创作 Agent</div>
          </div>
        </div>

        <div className="sidebar-scroll">
          {navGroups.map((group) => (
            <div key={group.id} className="sidebar-group">
              <div className="sidebar-group-title">{group.title}</div>
              <div className="sidebar-group-items">
                {group.items.map((item) => (
                  <NavLink
                    key={item.id}
                    to={item.path}
                    onClick={closeSidebar}
                    className={({ isActive }) => `sidebar-item ${isActive ? 'sidebar-item-active' : ''}`}
                  >
                    <span className="sidebar-item-highlight" />
                    <span className="sidebar-item-icon" aria-hidden="true">{item.icon}</span>
                    <span className="sidebar-item-label">{item.label}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </div>
      </aside>

      <div className="workspace-main">
        <header className="workspace-topbar page-fade">
          <div className="topbar-left">
            <button
              type="button"
              className="menu-btn"
              onClick={() => setSidebarOpen((v) => !v)}
              aria-label="切换导航菜单"
            >
              ☰
            </button>
            <div>
              <h1 className="hero-title">你好，创意探索者！👋</h1>
              <p className="hero-subtitle">欢迎使用轻青，让多种模型协作完成你的创作</p>
              <div className="hero-note-wrap">
                <span className="hero-note-pill">当前页面：{currentPageTitle}</span>
                <span className="hero-note-pill">模型凭据：{apiKeySource}</span>
              </div>
            </div>
          </div>

          <div className="token-usage-glass">
            <div className="token-usage-top">
              <div className="token-usage-title-wrap">
                <span className="token-dot" />
                <span className="token-usage-title">Token Plan 用量</span>
              </div>
              <span className="token-usage-time">
                更新于 {tokenPlanState.updatedAt ? tokenPlanState.updatedAt.toLocaleTimeString() : '--:--:--'}
              </span>
            </div>

            {tokenPlanState.loading ? (
              <div className="space-y-2">
                <div className="h-2 w-full animate-pulse rounded-full bg-violet-100" />
                <div className="h-2 w-2/3 animate-pulse rounded-full bg-violet-100" />
              </div>
            ) : tokenPlanState.error ? (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-600">
                加载失败：{tokenPlanState.error}
              </div>
            ) : (
              <>
                <div className="token-progress-row">
                  <div className="token-progress-track">
                    <div
                      className="token-progress-fill"
                      style={{ width: `${tokenPlanSummary?.textRatio ?? 0}%` }}
                    />
                  </div>
                  <div className="token-progress-value">
                    {tokenPlanSummary?.textUsageDisplay} / {tokenPlanSummary?.textLimitDisplay}
                  </div>
                </div>
                <div className="token-progress-subline">
                  文本 5 小时窗口 · 非文本每日重置
                </div>
              </>
            )}

            <div className="token-usage-actions">
              <button type="button" className="icon-btn" aria-label="通知">
                <BellIcon />
              </button>
              <button
                onClick={() => fetchTokenPlanRemains()}
                className="btn-gradient"
                type="button"
              >
                刷新额度
              </button>
              <button
                onClick={() => navigate('/token')}
                className="btn-secondary text-sm"
                type="button"
              >
                查看详情
              </button>
            </div>
          </div>
        </header>

        <main className="workspace-content page-fade">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
