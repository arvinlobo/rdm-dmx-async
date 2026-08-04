import type { ReactNode } from 'react'

export interface ButtonProps {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  variant?: 'primary' | 'secondary' | 'danger'
  type?: 'button' | 'submit'
}

/** Reusable button used across network, device, and module-action controls. */
export function Button({ children, onClick, disabled, variant = 'primary', type = 'button' }: ButtonProps) {
  return (
    <button type={type} className={`btn btn-${variant}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  )
}
