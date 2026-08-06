import { useCallback, useRef, useState, type ReactNode } from 'react'
import { ToastContext, type ToastVariant } from './toast-context'

interface ToastItem {
  id: number
  message: string
  variant: ToastVariant
}

const AUTO_DISMISS_MS = 5000

/** Stacked, auto-dismissing notifications so errors from different panels don't clobber each other. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const nextId = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id))
  }, [])

  const showToast = useCallback(
    (message: string, variant: ToastVariant = 'error') => {
      const id = nextId.current++
      setToasts((prev) => [...prev, { id, message, variant }])
      window.setTimeout(() => dismiss(id), AUTO_DISMISS_MS)
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="toast-stack" role="region" aria-live="polite" aria-label="Notifications">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.variant}`}>
            <span>{toast.message}</span>
            <button type="button" className="toast-dismiss" aria-label="Dismiss notification" onClick={() => dismiss(toast.id)}>
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
