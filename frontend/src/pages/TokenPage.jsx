import PageShell from '../components/PageShell'
import QuotaPanel from '../components/QuotaPanel'
import { useWorkbench } from '../context/WorkbenchContext'

function TokenOverviewCard({ label, usage, limit, ratio, note }) {
  return (
    <div className="card-shell token-overview-card">
      <div className="token-overview-label">{label}</div>
      <div className="token-overview-value-row">
        <span className="token-overview-usage">{usage}</span>
        <span className="token-overview-limit">/ {limit}</span>
      </div>
      <div className="quota-track token-overview-track">
        <div className="quota-fill quota-fill-safe" style={{ width: `${ratio || 0}%` }} />
      </div>
      <div className="token-overview-note">{note}</div>
    </div>
  )
}

function ModuleQuotaCard({ title, items }) {
  return (
    <div className="card-shell token-module-card">
      <h3 className="section-title">{title}</h3>
      <QuotaPanel items={items} emptyMessage="当前分类暂无额度明细" title="模型日配额" />
    </div>
  )
}

export default function TokenPage() {
  const {
    tokenPlanSummary,
    tokenPlanState,
    fetchTokenPlanRemains,
    apiKeySource
  } = useWorkbench()

  return (
    <PageShell
      title="Token Plan"
      description="查看文本窗口与各非文本模型额度，支持即时刷新并确认 API Key 生效来源。"
      extra={(
        <button type="button" onClick={() => fetchTokenPlanRemains()} className="btn-gradient">
          刷新额度
        </button>
      )}
    >
      <section className="token-stats-grid">
        <TokenOverviewCard
          label="文本窗口（5小时）"
          usage={tokenPlanSummary?.textUsageDisplay || '-'}
          limit={tokenPlanSummary?.textLimitDisplay || '-'}
          ratio={tokenPlanSummary?.textRatio || 0}
          note="5 小时滚动窗口自动释放"
        />
        <TokenOverviewCard
          label="非文本总量（每日）"
          usage={tokenPlanSummary?.nonTextUsageDisplay || '-'}
          limit={tokenPlanSummary?.nonTextLimitDisplay || '-'}
          ratio={tokenPlanSummary?.nonTextRatio || 0}
          note="各模型独立日配额汇总"
        />
        <div className="card-shell token-status-card">
          <div className="token-status-title">API Key 状态</div>
          <div className="token-status-row">当前来源：{apiKeySource}</div>
          <div className="token-status-time">
            最后刷新：{tokenPlanState.updatedAt ? tokenPlanState.updatedAt.toLocaleString() : '未刷新'}
          </div>
          {tokenPlanState.error ? (
            <div className="token-status-box token-status-box-error">
              配额读取失败：{tokenPlanState.error}
            </div>
          ) : (
            <div className="token-status-box token-status-box-ok">
              配额读取正常，可继续创作任务。
            </div>
          )}
        </div>
      </section>

      <section className="token-module-grid">
        <ModuleQuotaCard title="照片模型配额" items={tokenPlanSummary?.itemsByCategory?.photo || []} />
        <ModuleQuotaCard title="语音模型配额" items={tokenPlanSummary?.itemsByCategory?.tts || []} />
        <ModuleQuotaCard title="音乐模型配额" items={tokenPlanSummary?.itemsByCategory?.music || []} />
        <ModuleQuotaCard title="视频模型配额" items={tokenPlanSummary?.itemsByCategory?.video || []} />
      </section>

      <section className="card-shell token-note-card">
        <h3 className="section-title">额度说明</h3>
        <div className="copy-list">
          <div>文本模型采用 5 小时滚动窗口，超过窗口会自动恢复额度。</div>
          <div>非文本模型（图像/语音/音乐/视频）采用自然日重置机制。</div>
          <div>Token Plan Key 与按量 Key 不可混用，建议在设置页统一管理。</div>
        </div>
      </section>
    </PageShell>
  )
}
