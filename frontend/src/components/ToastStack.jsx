import { useWorkbench } from '../context/WorkbenchContext'

export default function ToastStack() {
  const { toasts, dismissToast } = useWorkbench()

  if (!toasts.length) return null

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-80 max-w-[92vw] flex-col gap-2">
      {toasts.map((toast) => (
        <button
          key={toast.id}
          type="button"
          onClick={() => dismissToast(toast.id)}
          className={`pointer-events-auto rounded-xl border px-3 py-2 text-left text-sm shadow-lg backdrop-blur transition hover:-translate-y-0.5 ${
            toast.type === 'error'
              ? 'border-rose-200 bg-rose-50/95 text-rose-700'
              : toast.type === 'warning'
                ? 'border-amber-200 bg-amber-50/95 text-amber-700'
                : 'border-emerald-200 bg-emerald-50/95 text-emerald-700'
          }`}
        >
          {toast.message}
        </button>
      ))}
    </div>
  )
}
