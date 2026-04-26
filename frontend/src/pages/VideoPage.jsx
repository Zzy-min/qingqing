import Multimodal from './Multimodal'
import PageShell from '../components/PageShell'
import { useWorkbench } from '../context/WorkbenchContext'

export default function VideoPage() {
  const { pushToast, tokenPlanSummary, settings } = useWorkbench()
  const quotaItems = tokenPlanSummary?.itemsByCategory?.video || []

  return (
    <PageShell
      title="视频生成"
      description="配置提示词、参考图、时长和镜头运动，生成并轮询视频任务。"
    >
      <Multimodal
        section="video"
        onNotify={pushToast}
        quotaItems={quotaItems}
        defaults={{
          videoModel: settings?.defaults?.videoModel,
          videoDuration: settings?.defaultParams?.videoDuration,
          videoResolution: settings?.defaultParams?.videoResolution
        }}
      />
    </PageShell>
  )
}
