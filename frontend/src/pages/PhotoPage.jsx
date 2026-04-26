import { useCallback, useState } from 'react'
import Canvas from '../components/Canvas'
import HistoryPanel from '../components/HistoryPanel'
import Toolbar from '../components/Toolbar'
import PageShell from '../components/PageShell'
import QuotaPanel from '../components/QuotaPanel'
import useEditorStore from '../stores/editorStore'
import { useWorkbench } from '../context/WorkbenchContext'

function makeTimestamp() {
  return new Date().toISOString().replace(/[:.]/g, '-')
}

async function downloadGeneratedFile(source, filename, onNotify) {
  if (!source) return
  try {
    const response = await fetch(source)
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    URL.revokeObjectURL(url)
  } catch {
    const anchor = document.createElement('a')
    anchor.href = source
    anchor.download = filename
    anchor.target = '_blank'
    anchor.rel = 'noopener noreferrer'
    anchor.click()
    onNotify?.('warning', '浏览器阻止直接下载，已尝试打开文件链接')
  }
}

export default function PhotoPage() {
  const { tokenPlanSummary, pushToast } = useWorkbench()
  const [photoTab, setPhotoTab] = useState('ai')
  const {
    originalImage,
    processedImage,
    isProcessing,
    setOriginalImage,
    setProcessedImage,
    setIsProcessing
  } = useEditorStore()

  const handleImageUpload = useCallback((event) => {
    if (event.target && event.target.result) {
      setOriginalImage(event.target.result)
      return
    }
    const file = event?.target?.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (e) => setOriginalImage(e.target.result)
    reader.readAsDataURL(file)
  }, [setOriginalImage])

  const handleDrop = useCallback((event) => {
    event.preventDefault()
    const file = event.dataTransfer.files?.[0]
    if (!file || !file.type.startsWith('image/')) return
    const reader = new FileReader()
    reader.onload = (e) => setOriginalImage(e.target.result)
    reader.readAsDataURL(file)
  }, [setOriginalImage])

  const handleProcess = useCallback((result) => {
    setProcessedImage(result)
    setOriginalImage(result)
  }, [setProcessedImage, setOriginalImage])

  const toolbarImage = originalImage || processedImage
  const photoQuotaItems = tokenPlanSummary?.itemsByCategory?.photo || []

  return (
    <PageShell
      title="照片编辑"
      description="上传图片或输入提示词，完成图像生成、滤镜处理与历史回溯。"
    >
      <QuotaPanel items={photoQuotaItems} />

      <div className="photo-workbench-grid">
        <section className="card-shell photo-card">
          <div className="panel-title">
            <span>原图输入</span>
            {originalImage && (
              <button
                onClick={() => setOriginalImage(null)}
                className="panel-action-link"
              >
                清除
              </button>
            )}
          </div>
          <div
            className="photo-panel-body"
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
          >
            <Canvas
              image={originalImage}
              label="上传或拖拽图片到此处"
              onUpload={handleImageUpload}
            />
          </div>
        </section>

        <section className="card-shell photo-card">
          <div className="panel-title">
            <div className="photo-tab-grid">
              <button
                onClick={() => setPhotoTab('ai')}
                className={`photo-tab ${photoTab === 'ai' ? 'photo-tab-active' : ''}`}
              >
                AI
              </button>
              <button
                onClick={() => setPhotoTab('filters')}
                className={`photo-tab ${photoTab === 'filters' ? 'photo-tab-active' : ''}`}
              >
                滤镜
              </button>
              <button
                onClick={() => setPhotoTab('history')}
                className={`photo-tab ${photoTab === 'history' ? 'photo-tab-active' : ''}`}
              >
                历史
              </button>
            </div>
          </div>

          <div className="photo-panel-scroll">
            {photoTab === 'history' ? (
              <HistoryPanel />
            ) : (
              <Toolbar
                activeTab={photoTab}
                originalImage={toolbarImage}
                onProcess={handleProcess}
                isProcessing={isProcessing}
                setIsProcessing={setIsProcessing}
                onNotify={pushToast}
              />
            )}
          </div>
        </section>

        <section className="card-shell photo-card">
          <div className="panel-title">
            <span>处理结果</span>
            <div className="photo-result-actions">
              {isProcessing && <span className="photo-processing-hint">处理中...</span>}
              {processedImage && (
                <button
                  onClick={() => downloadGeneratedFile(processedImage, `image-${makeTimestamp()}.png`, pushToast)}
                  className="panel-action-link"
                >
                  下载
                </button>
              )}
            </div>
          </div>
          <div className="photo-panel-body">
            <Canvas image={processedImage} label="AI 结果会显示在这里" showActions={false} />
          </div>
        </section>
      </div>
    </PageShell>
  )
}
