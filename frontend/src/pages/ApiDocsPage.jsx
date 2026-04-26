import PageShell from '../components/PageShell'

const API_SECTIONS = [
  {
    id: 'token',
    title: 'Token Plan 配额',
    method: 'GET',
    path: '/api/token-plan/remains',
    description: '查询文本窗口与非文本模型配额。',
    requestExample: 'curl -X GET http://127.0.0.1:8001/api/token-plan/remains',
    responseExample: `{
  "success": true,
  "text_window_usage": 34,
  "text_window_limit": 200,
  "non_text_daily_items": []
}`
  },
  {
    id: 'tts',
    title: '语音合成',
    method: 'POST',
    path: '/api/tts/synthesize',
    description: '提交文本并返回音频结果或音频 URL。',
    requestExample: `{
  "text": "你好，欢迎使用 MiniMax 工作台",
  "model": "speech-2.8-hd",
  "voice": "female-yujie"
}`,
    responseExample: `{
  "success": true,
  "audio_url": "/api/tts/audio/xxx.mp3"
}`
  },
  {
    id: 'video',
    title: '视频生成与查询',
    method: 'POST',
    path: '/api/video/generate',
    description: '提交视频任务，返回 task_id 后可调用 /api/video/task 轮询。',
    requestExample: `{
  "prompt": "城市夜景慢镜头",
  "model": "MiniMax-Hailuo-2.3",
  "duration": 6
}`,
    responseExample: `{
  "success": true,
  "task_id": "video-task-xxx",
  "status": "Pending"
}`
  }
]

export default function ApiDocsPage() {
  return (
    <PageShell
      title="API 文档"
      description="站内展示关键接口，完整参数与调试入口请使用 Swagger。"
      extra={(
        <a href="/docs" target="_blank" rel="noreferrer" className="btn-gradient">
          打开 Swagger
        </a>
      )}
    >
      <section className="docs-layout docs-layout-balanced">
        <aside className="card-shell docs-toc">
          <div className="docs-toc-title">目录</div>
          {API_SECTIONS.map((section) => (
            <a key={section.id} href={`#${section.id}`} className="docs-toc-link">
              {section.title}
            </a>
          ))}
        </aside>

        <article className="card-shell docs-content">
          {API_SECTIONS.map((section) => (
            <section key={section.id} id={section.id} className="docs-section docs-section-card">
              <h3>{section.title}</h3>
              <p className="docs-api-path">
                <span>{section.method}</span> {section.path}
              </p>
              <p>{section.description}</p>
              <div className="docs-code-wrap">
                <div className="docs-code-title">请求示例</div>
                <pre><code>{section.requestExample}</code></pre>
              </div>
              <div className="docs-code-wrap">
                <div className="docs-code-title">响应示例</div>
                <pre><code>{section.responseExample}</code></pre>
              </div>
            </section>
          ))}
        </article>
      </section>
    </PageShell>
  )
}
