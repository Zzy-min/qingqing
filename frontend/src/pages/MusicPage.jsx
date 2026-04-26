import Multimodal from './Multimodal'
import PageShell from '../components/PageShell'
import { useWorkbench } from '../context/WorkbenchContext'

export default function MusicPage() {
  const { pushToast, tokenPlanSummary, settings } = useWorkbench()
  const quotaItems = tokenPlanSummary?.itemsByCategory?.music || []

  return (
    <PageShell
      title="音乐生成"
      description="输入音乐描述、风格与歌词，快速生成完整音乐作品。"
    >
      <Multimodal
        section="music"
        onNotify={pushToast}
        quotaItems={quotaItems}
        defaults={{
          musicModel: settings?.defaults?.musicModel,
          musicBpm: settings?.defaultParams?.musicBpm
        }}
      />
    </PageShell>
  )
}
