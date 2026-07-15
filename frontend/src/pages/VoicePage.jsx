import PageShell from '../components/PageShell'
import AgentRunComposer from '../components/AgentRunComposer'
import QuotaPanel from '../components/QuotaPanel'
import { useWorkbench } from '../context/WorkbenchContext'

export default function VoicePage() {
  const { tokenPlanSummary } = useWorkbench()
  const quotaItems = tokenPlanSummary?.itemsByCategory?.tts || []

  return (
    <PageShell
      title="语音合成"
      description="通过轻青 AgentRun 合成语音：权益校验、预算与产物可追溯。"
    >
      <QuotaPanel items={quotaItems} />
      <AgentRunComposer
        capability="tts"
        title="语音合成 Agent"
        description="输入要朗读的文案；Auto 选择 TTS 模型并返回可访问产物。"
        placeholder="例如：用温和女声朗读：欢迎使用轻青，开启你的多模态创作之旅。"
      />
    </PageShell>
  )
}
