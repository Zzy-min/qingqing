import Multimodal from './Multimodal'
import PageShell from '../components/PageShell'
import { useWorkbench } from '../context/WorkbenchContext'

export default function VoicePage() {
  const { pushToast, tokenPlanSummary, settings } = useWorkbench()
  const quotaItems = tokenPlanSummary?.itemsByCategory?.tts || []

  return (
    <PageShell
      title="语音合成"
      description="输入文本并选择音色、语速与情绪参数，生成可试听、可下载的语音内容。"
    >
      <Multimodal
        section="tts"
        onNotify={pushToast}
        quotaItems={quotaItems}
        defaults={{
          ttsModel: settings?.defaults?.ttsModel
        }}
      />
    </PageShell>
  )
}
