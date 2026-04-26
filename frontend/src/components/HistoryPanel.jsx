import useEditorStore from '../stores/editorStore'

function HistoryPanel() {
  const { history, historyIndex, restoreFromHistory } = useEditorStore()

  if (history.length === 0) {
    return (
      <div className="p-8 text-center">
        <div className="text-4xl mb-2 opacity-50">📝</div>
        <div className="text-slate-500">暂无历史记录</div>
      </div>
    )
  }

  return (
    <div className="p-4">
      <div className="flex gap-4 overflow-x-auto pb-2">
        {history.map((entry, index) => (
          <div
            key={entry.timestamp}
            onClick={() => restoreFromHistory(index)}
            className={`flex-shrink-0 w-24 cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
              index === historyIndex
                ? 'border-accent'
                : 'border-transparent hover:border-violet-200'
            }`}
          >
            <div className="aspect-square bg-violet-50">
              {entry.result ? (
                <img
                  src={entry.result}
                  alt={`History ${index + 1}`}
                  className="w-full h-full object-cover"
                />
              ) : entry.original ? (
                <img
                  src={entry.original}
                  alt={`History ${index + 1}`}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-slate-500">
                  ?
                </div>
              )}
            </div>
            <div className="py-1 text-center text-xs text-slate-500">
              #{index + 1}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default HistoryPanel
