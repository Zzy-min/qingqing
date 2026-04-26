import { useState, useRef, useCallback, useEffect, useId } from 'react'

function Canvas({ image, label, onUpload, showActions = true }) {
  const [showCamera, setShowCamera] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const [cameraReady, setCameraReady] = useState(false)
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const fileInputRef = useRef(null)
  const fileInputId = useId()
  const canEdit = Boolean(onUpload) && showActions

  // Attach stream to video element once it mounts
  useEffect(() => {
    if (showCamera && streamRef.current && videoRef.current) {
      videoRef.current.srcObject = streamRef.current
      videoRef.current.onloadedmetadata = () => {
        setCameraReady(true)
        videoRef.current.play()
      }
    }
    return () => {
      setCameraReady(false)
    }
  }, [showCamera])

  // Cleanup stream on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
      }
    }
  }, [])

  const startCamera = useCallback(async () => {
    try {
      setCameraError('')
      setCameraReady(false)
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'environment',
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false
      })
      streamRef.current = stream
      setShowCamera(true)
    } catch (err) {
      console.error('Camera error:', err)
      if (err.name === 'NotAllowedError') {
        setCameraError('摄像头权限被拒绝，请在浏览器设置中允许访问摄像头')
      } else if (err.name === 'NotFoundError') {
        setCameraError('未找到摄像头设备')
      } else if (err.name === 'NotReadableError') {
        setCameraError('摄像头被其他应用占用')
      } else {
        setCameraError('无法访问摄像头: ' + err.message)
      }
    }
  }, [])

  const capturePhoto = useCallback(() => {
    const video = videoRef.current
    if (!video || !cameraReady) return

    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth || 1280
    canvas.height = video.videoHeight || 720
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    const dataUrl = canvas.toDataURL('image/jpeg', 0.92)

    // Stop camera
    stopCamera()
    setShowCamera(false)

    // Set as original image via onUpload
    if (onUpload) {
      // Simulate the format that handleImageUpload expects: { target: { result } }
      onUpload({ target: { result: dataUrl } })
    }
  }, [cameraReady, onUpload])

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }
  }, [])

  const cancelCamera = useCallback(() => {
    stopCamera()
    setShowCamera(false)
    setCameraError('')
  }, [stopCamera])

  const openFilePicker = useCallback((e) => {
    e?.preventDefault?.()
    e?.stopPropagation?.()
    if (!canEdit) return
    const input = fileInputRef.current
    if (!input) return
    if (typeof input.showPicker === 'function') {
      try {
        input.showPicker()
        return
      } catch {
        // Fall back to click when showPicker is unavailable in this browser context.
      }
    }
    input.click()
  }, [canEdit])

  const handleFileSelected = useCallback((e) => {
    if (!canEdit) return
    const file = e.target.files?.[0]
    if (!file) return
    onUpload({ target: { files: [file] } })
    // Reset value so selecting the same file again can still trigger onChange.
    e.target.value = ''
  }, [canEdit, onUpload])

  // Camera modal
  if (showCamera) {
    return (
      <div className="h-full flex flex-col overflow-hidden rounded-xl border border-violet-100 bg-white/90">
        <div className="flex shrink-0 items-center justify-between border-b border-violet-100 bg-violet-50/70 px-4 py-2">
          <span className="text-sm text-slate-700">📷 拍照</span>
          <div className="flex gap-2">
            <button
              onClick={cancelCamera}
              className="rounded-lg border border-violet-100 bg-white px-3 py-1 text-xs text-slate-600 hover:bg-violet-50"
            >
              取消
            </button>
            <button
              onClick={capturePhoto}
              disabled={!cameraReady}
              className={`px-3 py-1 text-xs rounded-lg ${
                cameraReady
                  ? 'bg-primary text-white hover:bg-primary/80'
                  : 'bg-slate-200 text-slate-500 cursor-not-allowed'
              }`}
            >
              拍照
            </button>
          </div>
        </div>
        <div className="relative flex flex-1 items-center justify-center bg-slate-950">
          {cameraError ? (
            <div className="text-center p-4">
              <div className="text-3xl mb-3">⚠️</div>
              <div className="text-sm text-red-400 mb-3">{cameraError}</div>
              <button
                onClick={cancelCamera}
                className="rounded-lg border border-violet-100 bg-white px-4 py-2 text-xs text-slate-600 hover:bg-violet-50"
              >
                关闭
              </button>
            </div>
          ) : (
            <>
              {!cameraReady && (
                <div className="absolute inset-0 flex items-center justify-center z-10">
                  <span className="text-slate-400 animate-pulse">正在启动摄像头...</span>
                </div>
              )}
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className={`max-w-full max-h-full object-contain ${cameraReady ? '' : 'opacity-0'}`}
              />
            </>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {image ? (
        <div className="flex flex-1 items-center justify-center overflow-hidden rounded-xl border border-violet-100 bg-white/90">
          <img
            src={image}
            alt={label}
            className="max-w-full max-h-full object-contain"
          />
        </div>
      ) : (
        <div
          className={`drop-zone flex-1 flex flex-col items-center justify-center ${canEdit ? 'cursor-pointer' : 'cursor-default'}`}
          onDrop={(e) => {
            e.preventDefault()
            if (canEdit) {
              const file = e.dataTransfer.files[0]
              if (file) {
                onUpload({ target: { files: [file] } })
              }
            }
          }}
          onDragOver={(e) => e.preventDefault()}
          onClick={canEdit ? openFilePicker : undefined}
        >
          <div className="text-6xl mb-4 opacity-50">📷</div>
          <div className="text-lg text-slate-400 mb-2">{label}</div>
          <div className="text-sm text-slate-500 mb-4">支持 PNG, JPG, WebP</div>
          {canEdit && (
            <input
              id={fileInputId}
              ref={fileInputRef}
              type="file"
              accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
              onChange={handleFileSelected}
              className="hidden"
            />
          )}
          {canEdit && (
            <div className="flex gap-3">
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  startCamera()
                }}
                className="px-4 py-2 bg-primary/20 text-primary rounded-lg text-sm hover:bg-primary/30 transition-colors"
              >
                📷 拍照
              </button>
              <button
                type="button"
                onClick={openFilePicker}
                className="px-4 py-2 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600 transition-colors"
              >
                📁 选择文件
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default Canvas
