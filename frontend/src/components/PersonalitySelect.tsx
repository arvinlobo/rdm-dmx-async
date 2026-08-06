import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { PersonalityOption } from '../api/types'
import { useToast } from '../context/useToast'

export interface PersonalitySelectProps {
  uid: string
  label: string
  value: number
  onChange: (value: number) => void
  disabled?: boolean
}

/** Lets a personality be picked by its human-readable description instead of a raw index. */
export function PersonalitySelect({ uid, label, value, onChange, disabled }: PersonalitySelectProps) {
  const [options, setOptions] = useState<PersonalityOption[]>([])
  const [error, setError] = useState<string | null>(null)
  const { showToast } = useToast()

  useEffect(() => {
    let cancelled = false
    api
      .getPersonalities(uid)
      .then((result) => {
        if (!cancelled) setOptions(result.options)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof ApiError ? err.message : 'Failed to load personalities'
        setError(message)
        showToast(`Personalities: ${message}`)
      })
    return () => {
      cancelled = true
    }
  }, [uid, showToast])

  if (error) return <p className="field field-error">{error}</p>

  const selected = options.find((option) => option.personality === value)

  return (
    <label className="field field-select">
      <span className="field-label">{label}</span>
      <select
        aria-label={label}
        title={selected ? `${selected.personality}: ${selected.description} (${selected.footprint} ch)` : undefined}
        value={value}
        disabled={disabled || options.length === 0}
        onChange={(event) => onChange(Number(event.target.value))}
      >
        <option value={0} disabled>
          -- Select a personality --
        </option>
        {options.map((option) => (
          <option key={option.personality} value={option.personality}>
            {option.personality}: {option.description} ({option.footprint} ch)
          </option>
        ))}
      </select>
    </label>
  )
}
