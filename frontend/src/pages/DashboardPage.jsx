import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageShell from '../components/PageShell'
import AgentRunComposer from '../components/AgentRunComposer'
import { useWorkbench } from '../context/WorkbenchContext'
import { inferCapability } from '../services/qingqingApi'

function StatCard({ label, value, note }) {
  return (
    <div className="card-shell stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {note ? <div className="stat-note">{note}</div> : null}
    </div>
  )
}

const QUICK_TEMPLATES = [
  { title: '短视频配乐', desc: '输入风格与情绪，快速生成 30 秒配乐', path: '/music', capability: 'music' },
  { title: '产品配音', desc: '一段文案快速合成多音色语音', path: '/voice', capability: 'tts' },
  { title: '镜头分镜', desc: '文生视频并附带镜头运动提示', path: '/video', capability: 'video' },
  { title: '海报创作', desc: '提示词 + 风格模板生成视觉主图', path: '/photo', capability: 'image' },
]

const CAPABILITY_PATH = {
  chat: '/chat',
  image: '/photo',
  tts: '/voice',
  music: '/music',
  video: '/video',
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { modules, tokenPlanSummary, usageAnalytics, recentGenerations } = useWorkbench()
  const [composerGoal, setComposerGoal] = useState('')
  const inferred = useMemo(() => inferCapability(composerGoal), [composerGoal])

  return (
    <PageShell
      title="工作台首页"
      description="统一创作入口：一句话发起 AgentRun，或进入各能力模块。"
    >
      <section className="stats-grid">
        <StatCard
          label="文本额度（5小时）"
          value={`${tokenPlanSummary?.textUsageDisplay || '-'} / ${tokenPlanSummary?.textLimitDisplay || '-'}`}
          note="按滚动窗口自动恢复"
        />
        <StatCard
          label="非文本额度（每日）"
          value={`${tokenPlanSummary?.nonTextUsageDisplay || '-'} / ${tokenPlanSummary?.nonTextLimitDisplay || '-'}`}
          note="各模型独立日配额"
        />
        <StatCard label="今日调用次数" value={usageAnalytics.todayCount} note="来自本地行为统计" />
        <StatCard label="本周调用次数" value={usageAnalytics.weekCount} note={`异常 ${usageAnalytics.errorCount} 次`} />
      </section>

      <section className="mb-6 space-y-3">
        <div className="card-shell p-4 md:p-5">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h3 className="section-title mb-0">快速创作</h3>
              <p className="mt-1 text-sm text-slate-500">
                根据描述自动识别能力（当前推断：
                <strong className="text-teal-700"> {inferred}</strong>
                ）。也可直接在下方完整 Composer 执行。
              </p>
            </div>
            <button
              type="button"
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
              onClick={() => navigate(CAPABILITY_PATH[inferred] || '/chat')}
            >
              打开 {inferred} 页面
            </button>
          </div>
          <input
            value={composerGoal}
            onChange={(e) => setComposerGoal(e.target.value)}
            placeholder="例如：生成一段清新民谣配乐 / 做一张产品海报…"
            className="mb-3 w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm outline-none focus:border-teal-500"
          />
        </div>
        <AgentRunComposer
          key={inferred}
          capability={inferred}
          title="Agent 创作 Composer"
          description="首页统一入口：路由预览、预算审批、SSE 进度与结果展示。"
          placeholder={composerGoal || '描述你想做的事，支持图 / 音 / 乐 / 视频 / 对话…'}
        />
      </section>

      <section className="module-card-grid">
        {modules.map((module) => (
          <button
            key={module.id}
            type="button"
            onClick={() => navigate(module.path)}
            className={`module-card ${module.tone}`}
          >
            <div className="module-card-icon" aria-hidden="true">{module.icon}</div>
            <div>
              <div className="module-card-title">{module.title}</div>
              <div className="module-card-subtitle">{module.subtitle}</div>
              <div className="module-card-desc">{module.desc}</div>
            </div>
          </button>
        ))}
      </section>

      <section className="dashboard-lower-grid">
        <div className="card-shell dashboard-panel-card">
          <h3 className="section-title">最近生成记录</h3>
          {recentGenerations.length === 0 ? (
            <div className="empty-hint">暂无记录，开始一次创作后会显示在这里。</div>
          ) : (
            <div className="record-list">
              {recentGenerations.map((item, index) => (
                <div key={`${item.timestamp}-${index}`} className="recent-row">
                  <div className="recent-main">
                    <div className="recent-title">{item.title}</div>
                    <div className="recent-meta">
                      {item.module} · {new Date(item.timestamp).toLocaleString()}
                    </div>
                  </div>
                  <span className={`recent-badge ${item.status === 'error' ? 'recent-badge-error' : 'recent-badge-success'}`}>
                    {item.status === 'error' ? '失败' : '完成'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card-shell dashboard-panel-card">
          <h3 className="section-title">快捷开始</h3>
          <div className="template-list">
            {QUICK_TEMPLATES.map((tpl) => (
              <button
                key={tpl.title}
                type="button"
                onClick={() => navigate(tpl.path)}
                className="quick-template"
              >
                <div className="quick-template-title">{tpl.title}</div>
                <div className="quick-template-desc">{tpl.desc}</div>
              </button>
            ))}
          </div>
        </div>
      </section>
    </PageShell>
  )
}
