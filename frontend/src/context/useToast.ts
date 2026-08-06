import { useContext } from 'react'
import { ToastContext, type ToastContextValue } from './toast-context'

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  // Falls back to a no-op outside a provider (e.g. components under test in isolation)
  // rather than throwing, since toasts are a supplementary notification channel.
  return ctx ?? { showToast: () => {} }
}
