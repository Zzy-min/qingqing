import PageShell from '../components/PageShell'
import AgentRunComposer from '../components/AgentRunComposer'
import QuotaPanel from '../components/QuotaPanel'
import { useWorkbench } from '../context/WorkbenchContext'

export default function MusicPage() {
  const { tokenPlanSummary } = useWorkbench()
  const quotaItems = tokenPlanSummary?.itemsByCategory?.music || []

  return (
    <PageShell
      title="音乐生成"
      description="通过轻青 AgentRun 创建音乐任务：Auto 路由、预算审批与进度事件。"
    >
      <QuotaPanel items={quotaItems} />
      <AgentRunComposer
        capability="music"
        title="音乐创作 Agent"
        description="描述风格、情绪、BPM 或歌词方向，系统将走 /api/v1 账本与模型路由。"
        placeholder="例如：清新民谣，轻快 guzheng 与钢琴，适合产品开场 30 秒…"
      />
    </PageShell>
  )
}
