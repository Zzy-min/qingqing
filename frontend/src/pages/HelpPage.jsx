import PageShell from '../components/PageShell'

const HELP_SECTIONS = [
  {
    id: 'quickstart',
    title: '快速开始',
    content: [
      '1. 在“设置”页面填写或粘贴你的 MiniMax API Key。',
      '2. 返回“工作台”选择照片、语音、音乐或视频模块。',
      '3. 生成后可在模块结果区下载，最近记录会自动同步到首页。'
    ]
  },
  {
    id: 'routing',
    title: '页面导航',
    content: [
      '工作台采用独立路由页面，点击左侧菜单会直接进入对应能力页。',
      '首页仅显示总览与入口，不承载完整功能表单。',
      '移动端下侧栏可折叠，核心 CTA 保持可见。'
    ]
  },
  {
    id: 'quota',
    title: '额度说明',
    content: [
      '文本模型按 5 小时滚动窗口统计。',
      '非文本模型按自然日重置，且各模型独立计算。',
      'Token Plan 与按量 API Key 不可混用。'
    ]
  }
]

export default function HelpPage() {
  return (
    <PageShell
      title="帮助文档"
      description="常见使用问题、工作流建议与路由化工作台说明。"
    >
      <section className="docs-layout docs-layout-balanced">
        <aside className="card-shell docs-toc">
          <div className="docs-toc-title">目录</div>
          {HELP_SECTIONS.map((section) => (
            <a key={section.id} href={`#${section.id}`} className="docs-toc-link">
              {section.title}
            </a>
          ))}
          <a
            href="https://platform.minimaxi.com/docs"
            target="_blank"
            rel="noreferrer"
            className="docs-external-link"
          >
            打开官方文档
          </a>
        </aside>

        <article className="card-shell docs-content">
          {HELP_SECTIONS.map((section) => (
            <section key={section.id} id={section.id} className="docs-section docs-section-card">
              <h3>{section.title}</h3>
              <div className="docs-paragraph-list">
                {section.content.map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </div>
            </section>
          ))}
        </article>
      </section>
    </PageShell>
  )
}
