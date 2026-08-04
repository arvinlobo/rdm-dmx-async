import type { ReactNode } from 'react'

export interface ButtonProps {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  variant?: 'primary' | 'secondary' | 'danger'
  type?: 'button' | 'submit'
  loading?: boolean
}

/** Reusable button used across network, device, and module-action controls. */
export function Button({ children, onClick, disabled, variant = 'primary', type = 'button', loading }: ButtonProps) {
  return (
    <button type={type} className={`btn btn-${variant}${loading ? ' btn-loading' : ''}`} onClick={onClick} disabled={disabled}>
      {loading && <span className="btn-spinner" aria-hidden="true" />}
      {children}
    </button>
  )
}
