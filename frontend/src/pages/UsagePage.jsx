import PageShell from '../components/PageShell'
import { useWorkbench } from '../context/WorkbenchContext'

function TinyStat({ label, value, hint }) {
  return (
    <div className="card-shell usage-stat-card">
      <div className="usage-stat-label">{label}</div>
      <div className="usage-stat-value">{value}</div>
      {hint ? <div className="usage-stat-hint">{hint}</div> : null}
    </div>
  )
}

export default function UsagePage() {
  const { usageAnalytics, usageEvents } = useWorkbench()
  const maxTrendCount = Math.max(1, ...usageAnalytics.dailyTrend.map((item) => item.count || 0))
  const maxModuleCount = Math.max(1, ...usageAnalytics.moduleDistribution.map((item) => item.count || 0))

  return (
    <PageShell
      title="用量分析"
      description="基于本地行为埋点统计，帮助你追踪模块调用频率、趋势和异常情况。"
    >
      <section className="usage-stats-grid">
        <TinyStat label="今日调用" value={usageAnalytics.todayCount} hint="本地设备统计" />
        <TinyStat label="本周调用" value={usageAnalytics.weekCount} hint="最近 7 天累计" />
        <TinyStat label="异常次数" value={usageAnalytics.errorCount} hint="接口失败或参数错误" />
        <TinyStat label="总事件数" value={usageEvents.length} hint="上限 1200 条循环保留" />
      </section>

      <section className="usage-grid-two">
        <div className="card-shell usage-panel-card">
          <h3 className="section-title">最近 7 天调用趋势</h3>
          <div className="usage-trend-list">
            {usageAnalytics.dailyTrend.map((item) => (
              <div key={item.dateKey} className="usage-trend-row">
                <div className="usage-trend-label">{item.label}</div>
                <div className="usage-trend-track">
                  <div
                    className="usage-trend-fill"
                    style={{ width: `${(item.count / maxTrendCount) * 100}%` }}
                  />
                </div>
                <div className="usage-trend-count">{item.count}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card-shell usage-panel-card">
          <h3 className="section-title">模块分布</h3>
          {usageAnalytics.moduleDistribution.length === 0 ? (
            <div className="empty-hint">暂无调用数据。</div>
          ) : (
            <div className="usage-module-list">
              {usageAnalytics.moduleDistribution.map((item) => (
                <div key={item.module} className="usage-trend-row">
                  <div className="usage-trend-label">{item.module}</div>
                  <div className="usage-trend-track">
                    <div
                      className="usage-module-fill"
                      style={{ width: `${(item.count / maxModuleCount) * 100}%` }}
                    />
                  </div>
                  <div className="usage-trend-count">{item.count}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="card-shell usage-note-card">
        <h3 className="section-title">统计口径说明</h3>
        <div className="copy-list">
          <div>数据来源于前端本地行为日志，不会上传到后端数据库。</div>
          <div>如需重置统计，可清空浏览器本地存储（会同时清除最近记录）。</div>
          <div>该页面用于创作工作流优化，不用于官方计费对账。</div>
        </div>
      </section>
    </PageShell>
  )
}
