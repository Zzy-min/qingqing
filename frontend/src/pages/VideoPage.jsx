import PageShell from '../components/PageShell'
import AgentRunComposer from '../components/AgentRunComposer'
import QuotaPanel from '../components/QuotaPanel'
import { useWorkbench } from '../context/WorkbenchContext'

export default function VideoPage() {
  const { tokenPlanSummary } = useWorkbench()
  const quotaItems = tokenPlanSummary?.itemsByCategory?.video || []

  return (
    <PageShell
      title="视频生成"
      description="通过轻青 AgentRun 发起视频任务（进度 SSE / 轮询兼容）。"
    >
      <QuotaPanel items={quotaItems} />
      <AgentRunComposer
        capability="video"
        title="视频创作 Agent"
        description="描述镜头、时长与风格。当前为单步视频 capability，多步流水线见后续 Phase。"
        placeholder="例如：产品特写推近，自然光，15 秒竖版短视频，干净背景…"
      />
    </PageShell>
  )
}
