export default function QuotaPanel({
  items,
  emptyMessage = '当前模块暂无独立日配额',
  title = '今日额度（每日重置）'
}) {
  const normalizedItems = Array.isArray(items) ? items : []
  return (
    <div className="quota-panel">
      <div className="quota-panel-title">{title}</div>
      {normalizedItems.length === 0 ? (
        <div className="quota-panel-empty">{emptyMessage}</div>
      ) : (
        <div className="quota-list">
          {normalizedItems.map((item) => (
            <div key={item.model_name} className="quota-item">
              <div className="quota-item-head">
                <span className="quota-item-name">{item.display_name || item.model_name}</span>
                <span className="quota-item-usage">{item.usage} / {item.limit || '-'}</span>
              </div>
              <div className="quota-item-remaining">
                剩余：{item.remainingDisplay}
              </div>
              <div className="quota-track">
                <div
                  className={`quota-fill ${item.ratio >= 90 ? 'quota-fill-danger' : item.ratio >= 70 ? 'quota-fill-warn' : 'quota-fill-safe'}`}
                  style={{ width: `${item.ratio}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
