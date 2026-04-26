import { useState } from 'react'
import { imageApi } from '../services/api'

const MAX_PROMPT_LENGTH = 1500

const ASPECT_RATIOS = [
  { id: '1:1', label: '1:1', desc: '正方形' },
  { id: '3:4', label: '3:4', desc: '竖版' },
  { id: '4:3', label: '4:3', desc: '横版' },
  { id: '9:16', label: '9:16', desc: '手机竖屏' },
  { id: '16:9', label: '16:9', desc: '宽屏' },
  { id: '21:9', label: '21:9', desc: '超宽屏' }
]

const FILTER_PRESETS = [
  { id: 'vintage', label: '复古' },
  { id: 'bw', label: '黑白' },
  { id: 'sepia', label: '怀旧' },
  { id: 'edge', label: '锐化' },
  { id: 'sharpen', label: '清晰' }
]

function InlineError({ text, onRetry }) {
  if (!text) return null
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
      <div className="flex items-center justify-between gap-2">
        <span>{text}</span>
        {onRetry && (
          <button
            onClick={onRetry}
            className="rounded border border-current/30 px-2 py-1 text-[11px] text-current"
          >
            重试
          </button>
        )}
      </div>
    </div>
  )
}

function Toolbar({
  activeTab,
  originalImage,
  onProcess,
  isProcessing,
  setIsProcessing,
  onNotify
}) {
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [imageModel, setImageModel] = useState('image-01')
  const [aspectRatio, setAspectRatio] = useState('1:1')
  const [batchCount, setBatchCount] = useState(1)
  const [promptOptimizer, setPromptOptimizer] = useState(false)
  const [responseFormat, setResponseFormat] = useState('url')
  const [seed, setSeed] = useState('')
  const [customWidth, setCustomWidth] = useState('')
  const [customHeight, setCustomHeight] = useState('')
  const [noWatermark, setNoWatermark] = useState(false)
  const [generatedImages, setGeneratedImages] = useState([])
  const [activeImageIndex, setActiveImageIndex] = useState(0)
  const [error, setError] = useState('')
  const [lastAction, setLastAction] = useState(null)
  const [filters, setFilters] = useState({
    brightness: 1,
    contrast: 1,
    saturation: 1,
    sharpness: 1,
    blur: 0,
    rotate: 0,
    flipH: false,
    flipV: false
  })

  const hasImage = !!originalImage
  const mode = hasImage ? 'img2img' : 'text2img'

  const showError = (message) => {
    setError(message)
    onNotify?.('error', message)
  }

  const clearStatus = () => {
    setError('')
  }

  const extractErrorMessage = (apiError, fallback = '请求失败') => {
    const detail = apiError?.response?.data?.detail
    if (Array.isArray(detail)) {
      return detail.map((d) => `${d.loc?.join('.') || 'field'} ${d.msg}`).join('; ')
    }
    if (typeof detail === 'string') return detail
    return apiError?.message || fallback
  }

  const resolveImageUrlToData = (imageUrl) => new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = img.width
      canvas.height = img.height
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0)
      resolve(canvas.toDataURL('image/png'))
    }
    img.onerror = () => reject(new Error('图片加载失败，建议重试'))
    img.src = imageUrl
  })

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      const msg = '请输入提示词后再生成'
      showError(msg)
      onNotify?.('warning', msg)
      return
    }

    clearStatus()
    setIsProcessing(true)
    setGeneratedImages([])
    setActiveImageIndex(0)
    setLastAction(() => handleGenerate)

    try {
      const result = await imageApi.generate({
        model: imageModel,
        prompt: prompt.trim(),
        negative_prompt: negativePrompt.trim() || undefined,
        aspect_ratio: aspectRatio,
        n: batchCount,
        logo_watermark: !noWatermark,
        aigc_watermark: !noWatermark,
        prompt_optimizer: promptOptimizer,
        response_format: responseFormat,
        seed: seed ? parseInt(seed, 10) : undefined,
        width: customWidth ? parseInt(customWidth, 10) : undefined,
        height: customHeight ? parseInt(customHeight, 10) : undefined,
        image_data: originalImage || undefined
      })

      if (result.images && result.images.length > 1) {
        setGeneratedImages(result.images)
        setActiveImageIndex(0)
        onProcess(result.images[0])
      } else if (result.image_data) {
        onProcess(result.image_data)
      } else if (result.image_url) {
        const dataUrl = await resolveImageUrlToData(result.image_url)
        onProcess(dataUrl)
      } else {
        throw new Error(result.error || '生成失败: 响应里没有图片数据')
      }

      onNotify?.('success', mode === 'img2img' ? '图生图完成' : '文生图完成')
    } catch (apiError) {
      showError(`生成失败: ${extractErrorMessage(apiError, '未知错误')}`)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleSelectImage = (index) => {
    setActiveImageIndex(index)
    onProcess(generatedImages[index])
    clearStatus()
  }

  const handleFilterApply = async () => {
    if (!originalImage) {
      const msg = '请先上传或生成图片'
      showError(msg)
      onNotify?.('warning', msg)
      return
    }

    clearStatus()
    setIsProcessing(true)
    setLastAction(() => handleFilterApply)

    try {
      const result = await imageApi.process({
        image_data: originalImage,
        brightness: filters.brightness,
        contrast: filters.contrast,
        saturation: filters.saturation,
        sharpness: filters.sharpness,
        blur: filters.blur,
        rotate: filters.rotate,
        flip_h: filters.flipH,
        flip_v: filters.flipV
      })
      if (result.image_data) {
        onProcess(result.image_data)
        onNotify?.('success', '滤镜应用完成')
      } else {
        throw new Error('处理失败: 无返回数据')
      }
    } catch (apiError) {
      showError(`滤镜处理失败: ${extractErrorMessage(apiError, '未知错误')}`)
    } finally {
      setIsProcessing(false)
    }
  }

  const handlePresetFilter = async (filterId) => {
    if (!originalImage) {
      const msg = '请先上传或生成图片'
      showError(msg)
      onNotify?.('warning', msg)
      return
    }

    clearStatus()
    setIsProcessing(true)
    setLastAction(() => () => handlePresetFilter(filterId))

    try {
      const result = await imageApi.process({
        image_data: originalImage,
        filter_type: filterId
      })
      if (result.image_data) {
        onProcess(result.image_data)
        onNotify?.('success', `已应用 ${FILTER_PRESETS.find((x) => x.id === filterId)?.label || '预设滤镜'}`)
      } else {
        throw new Error('处理失败: 无返回数据')
      }
    } catch (apiError) {
      showError(`滤镜处理失败: ${extractErrorMessage(apiError, '未知错误')}`)
    } finally {
      setIsProcessing(false)
    }
  }

  const isOverLimit = prompt.length > MAX_PROMPT_LENGTH

  if (activeTab === 'ai') {
    return (
      <div className="flex h-full flex-col gap-3 overflow-y-auto p-4">
        <div className={`rounded-md border px-2 py-1 text-center text-xs font-medium ${
          mode === 'img2img'
            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
            : 'border-sky-500/30 bg-sky-500/10 text-sky-200'
        }`}>
          {mode === 'img2img' ? '图生图模式（原图 + 提示词）' : '文生图模式'}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">提示词</label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={mode === 'img2img' ? '描述要如何修改当前图片...' : '描述你希望生成的图像...'}
            className="field-input h-24 w-full resize-none"
          />
          <div className={`mt-1 text-right text-xs ${isOverLimit ? 'text-red-300' : 'text-slate-500'}`}>
            {prompt.length} / {MAX_PROMPT_LENGTH}
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            反向提示词
            <span className="ml-1 text-slate-500">(可选)</span>
          </label>
          <input
            type="text"
            value={negativePrompt}
            onChange={(e) => setNegativePrompt(e.target.value)}
            placeholder="例如：模糊、低清晰度、噪点"
            className="field-input w-full"
          />
        </div>

        <button
          onClick={() => setShowAdvanced((s) => !s)}
          className="text-left text-xs text-slate-500 hover:text-violet-700"
        >
          {showAdvanced ? '收起高级设置' : '展开高级设置'}
        </button>

        {showAdvanced && (
          <div className="space-y-3 rounded-lg border border-violet-100 bg-white/70 p-3">
            <div>
              <label className="mb-1.5 block text-xs text-slate-500">模型</label>
              <select
                value={imageModel}
                onChange={(e) => setImageModel(e.target.value)}
                className="field-input w-full text-xs"
              >
                <option value="image-01">image-01</option>
                <option value="image-01-live">image-01-live</option>
              </select>
            </div>

            <div>
              <label className="mb-1.5 block text-xs text-slate-500">画面比例</label>
              <div className="grid grid-cols-3 gap-1.5">
                {ASPECT_RATIOS.map((ratio) => (
                  <button
                    key={ratio.id}
                    onClick={() => setAspectRatio(ratio.id)}
                    className={`rounded px-2 py-1.5 text-xs transition ${
                      aspectRatio === ratio.id
                        ? 'bg-primary text-white'
                        : 'border border-violet-100 bg-white text-slate-600 hover:bg-violet-50'
                    }`}
                    title={ratio.desc}
                  >
                    {ratio.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs text-slate-500">生成数量: {batchCount}</label>
              <div className="grid grid-cols-3 gap-1.5">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
                  <button
                    key={n}
                    onClick={() => setBatchCount(n)}
                    className={`flex-1 rounded py-1.5 text-xs transition ${
                      batchCount === n
                        ? 'bg-primary text-white'
                        : 'border border-violet-100 bg-white text-slate-600 hover:bg-violet-50'
                    }`}
                  >
                    {n} 张
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="mb-1.5 block text-xs text-slate-500">宽度</label>
                <input
                  value={customWidth}
                  onChange={(e) => setCustomWidth(e.target.value)}
                  type="number"
                  min="512"
                  max="2048"
                  step="8"
                  placeholder="可选"
                  className="field-input w-full text-xs"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs text-slate-500">高度</label>
                <input
                  value={customHeight}
                  onChange={(e) => setCustomHeight(e.target.value)}
                  type="number"
                  min="512"
                  max="2048"
                  step="8"
                  placeholder="可选"
                  className="field-input w-full text-xs"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="mb-1.5 block text-xs text-slate-500">Seed</label>
                <input
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                  type="number"
                  placeholder="随机"
                  className="field-input w-full text-xs"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs text-slate-500">返回格式</label>
                <select value={responseFormat} onChange={(e) => setResponseFormat(e.target.value)} className="field-input w-full text-xs">
                  <option value="url">URL</option>
                  <option value="base64">Base64</option>
                </select>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">去除水印</span>
              <button
                onClick={() => setNoWatermark((s) => !s)}
                className={`relative h-5 w-10 rounded-full transition-colors ${noWatermark ? 'bg-primary' : 'bg-slate-300'}`}
              >
                <span
                  className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
                    noWatermark ? 'translate-x-5' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">提示词优化</span>
              <button
                onClick={() => setPromptOptimizer((s) => !s)}
                className={`relative h-5 w-10 rounded-full transition-colors ${promptOptimizer ? 'bg-primary' : 'bg-slate-300'}`}
              >
                <span
                  className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
                    promptOptimizer ? 'translate-x-5' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>
          </div>
        )}

        <InlineError text={error} onRetry={lastAction} />

        {generatedImages.length > 1 && (
          <div>
            <div className="mb-1.5 text-xs text-slate-500">已生成 {generatedImages.length} 张，点击切换</div>
            <div className="flex gap-1.5">
              {generatedImages.map((img, idx) => (
                <button
                  key={`${img.slice(0, 30)}-${idx}`}
                  onClick={() => handleSelectImage(idx)}
                  className={`h-12 w-12 overflow-hidden rounded border-2 ${
                    activeImageIndex === idx ? 'border-primary' : 'border-violet-200'
                  }`}
                >
                  <img src={img} alt={`候选图 ${idx + 1}`} className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="mt-auto">
          <button
            onClick={handleGenerate}
            disabled={isProcessing || !prompt.trim() || isOverLimit}
            className="btn-primary w-full py-3 text-base"
          >
            {isProcessing ? (mode === 'img2img' ? '图生图处理中...' : '文生图处理中...') : (mode === 'img2img' ? '开始图生图' : '开始文生图')}
          </button>
        </div>
      </div>
    )
  }

  if (activeTab === 'filters') {
    return (
      <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
        <div className="text-sm text-slate-700">快捷滤镜</div>
        <div className="grid grid-cols-3 gap-2">
          {FILTER_PRESETS.map((filter) => (
            <button
              key={filter.id}
              onClick={() => handlePresetFilter(filter.id)}
              disabled={!originalImage || isProcessing}
              className="btn-secondary py-2 text-xs disabled:opacity-50"
            >
              {filter.label}
            </button>
          ))}
        </div>

        <div className="mt-2 border-t border-violet-100 pt-4">
          <div className="mb-3 text-sm text-slate-700">精细参数</div>

          <div className="space-y-4">
            <div>
              <div className="mb-1 flex justify-between text-xs text-slate-500">
                <span>亮度</span>
                <span>{filters.brightness.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="2"
                step="0.1"
                value={filters.brightness}
                onChange={(e) => setFilters({ ...filters, brightness: parseFloat(e.target.value) })}
                className="slider"
              />
            </div>

            <div>
              <div className="mb-1 flex justify-between text-xs text-slate-500">
                <span>对比度</span>
                <span>{filters.contrast.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="2"
                step="0.1"
                value={filters.contrast}
                onChange={(e) => setFilters({ ...filters, contrast: parseFloat(e.target.value) })}
                className="slider"
              />
            </div>

            <div>
              <div className="mb-1 flex justify-between text-xs text-slate-500">
                <span>饱和度</span>
                <span>{filters.saturation.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={filters.saturation}
                onChange={(e) => setFilters({ ...filters, saturation: parseFloat(e.target.value) })}
                className="slider"
              />
            </div>

            <div>
              <div className="mb-1 flex justify-between text-xs text-slate-500">
                <span>模糊</span>
                <span>{filters.blur}</span>
              </div>
              <input
                type="range"
                min="0"
                max="20"
                step="1"
                value={filters.blur}
                onChange={(e) => setFilters({ ...filters, blur: parseInt(e.target.value, 10) })}
                className="slider"
              />
            </div>

            <div>
              <div className="mb-1 flex justify-between text-xs text-slate-500">
                <span>旋转</span>
                <span>{filters.rotate}°</span>
              </div>
              <input
                type="range"
                min="-180"
                max="180"
                step="15"
                value={filters.rotate}
                onChange={(e) => setFilters({ ...filters, rotate: parseInt(e.target.value, 10) })}
                className="slider"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setFilters({ ...filters, flipH: !filters.flipH })}
                className={`rounded-lg px-3 py-2 text-xs font-medium ${filters.flipH ? 'bg-primary text-white' : 'border border-violet-100 bg-white text-slate-600'}`}
              >
                水平翻转
              </button>
              <button
                onClick={() => setFilters({ ...filters, flipV: !filters.flipV })}
                className={`rounded-lg px-3 py-2 text-xs font-medium ${filters.flipV ? 'bg-primary text-white' : 'border border-violet-100 bg-white text-slate-600'}`}
              >
                垂直翻转
              </button>
            </div>
          </div>
        </div>

        <InlineError text={error} onRetry={lastAction} />

        <div className="mt-auto">
          <button
            onClick={handleFilterApply}
            disabled={!originalImage || isProcessing}
            className="btn-primary w-full py-3 text-base"
          >
            {isProcessing ? '滤镜处理中...' : '应用滤镜'}
          </button>
        </div>
      </div>
    )
  }

  return null
}

export default Toolbar
