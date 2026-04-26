export default function PageShell({ title, description, children, extra }) {
  return (
    <section className="page-stack">
      <div className="card-shell page-header-card">
        <div>
          <h2 className="page-title">{title}</h2>
          {description && <p className="page-desc">{description}</p>}
        </div>
        {extra ? <div className="page-header-extra">{extra}</div> : null}
      </div>
      {children}
    </section>
  )
}
