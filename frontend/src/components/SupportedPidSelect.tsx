import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { SupportedPidOption } from '../api/types'
import { useToast } from '../context/ToastContext'

export interface SupportedPidSelectProps {
  uid: string
  label: string
  value: number
  onChange: (value: number) => void
  disabled?: boolean
}

/** Lets a PID be picked from the device's own GET_SUPPORTED_PARAMETERS list instead of a raw
 * numeric field, so callers can't select a PID the device will just NAK as UNKNOWN_PID. */
export function SupportedPidSelect({ uid, label, value, onChange, disabled }: SupportedPidSelectProps) {
  const [options, setOptions] = useState<SupportedPidOption[]>([])
  const [error, setError] = useState<string | null>(null)
  const { showToast } = useToast()

  useEffect(() => {
    let cancelled = false
    api
      .getSupportedPids(uid)
      .then((result) => {
        if (!cancelled) setOptions(result.options)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof ApiError ? err.message : 'Failed to load supported PIDs'
        setError(message)
        showToast(`Supported PIDs: ${message}`)
      })
    return () => {
      cancelled = true
    }
  }, [uid, showToast])

  if (error) return <p className="field field-error">{error}</p>

  return (
    <label className="field field-select">
      <span className="field-label">{label}</span>
      <select
        aria-label={label}
        value={value}
        disabled={disabled || options.length === 0}
        onChange={(event) => onChange(Number(event.target.value))}
      >
        <option value={0} disabled>
          -- Select a PID --
        </option>
        {options.map((option) => (
          <option key={option.pid} value={option.pid}>
            {option.name} (0x{option.pid.toString(16).toUpperCase().padStart(4, '0')})
          </option>
        ))}
      </select>
    </label>
  )
}
