import { useState } from 'react'
import { api, ApiError } from '../api/client'
import type { ModuleMethodSpec } from '../api/types'
import { useToast } from '../context/useToast'
import { Button } from './Button'
import { Checkbox } from './Checkbox'
import { PersonalitySelect } from './PersonalitySelect'
import { Select } from './Select'
import { Slider } from './Slider'
import { SupportedPidSelect } from './SupportedPidSelect'
import { TextField } from './TextField'

export interface MethodFormProps {
  uid: string
  moduleName: string
  method: ModuleMethodSpec
  onSuccess?: () => void
}

type ParamValue = boolean | number | string

function defaultValueFor(
  kind: string,
  fallback: ParamValue | null,
  min: number | null,
  options: string[] | null,
): ParamValue {
  if (fallback !== null && fallback !== undefined) return fallback
  if (kind === 'bool') return false
  // Enum and PID-select params both use 0 as an explicit "nothing selected" sentinel,
  // so they must not default to the param's real minimum.
  if (kind === 'enum' || kind === 'pid') return 0
  if (kind === 'int') return min ?? 0
  if (kind === 'choice') return options?.[0] ?? ''
  return ''
}

/** Dynamically renders a form for one module method, using reusable field components per param kind. */
export function MethodForm({ uid, moduleName, method, onSuccess }: MethodFormProps) {
  const [values, setValues] = useState<ParamValue[]>(() =>
    method.params.map((param) =>
      defaultValueFor(param.kind, param.default, param.min ?? null, param.options ?? null),
    ),
  )
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { showToast } = useToast()

  const setParam = (index: number, value: ParamValue) => {
    setValues((prev) => prev.map((v, i) => (i === index ? value : v)))
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError(null)
    setResult(null)
    try {
      const response = await api.callMethod(uid, moduleName, method.name, values)
      setResult(JSON.stringify(response.result))
      onSuccess?.()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Method call failed'
      setError(message)
      showToast(`${method.name}: ${message}`)
    } finally {
      setSubmitting(false)
    }
  }

  const disabled = !method.supported

  return (
    <form
      className="method-form"
      onSubmit={(event) => {
        event.preventDefault()
        void handleSubmit()
      }}
    >
      <div className="method-form-header">
        <h4>{method.name}</h4>
        <Button type="submit" disabled={submitting || disabled} loading={submitting}>
          Run
        </Button>
      </div>
      {disabled && <p className="method-form-unsupported">Not supported by this device</p>}
      <div className="method-form-fields">
        {method.params.map((param, index) => {
        const value = values[index]
        if (param.kind === 'bool') {
          return (
            <Checkbox
              key={param.name}
              label={param.name}
              checked={Boolean(value)}
              onChange={(v) => setParam(index, v)}
              disabled={disabled}
            />
          )
        }
        if (param.kind === 'enum') {
          return (
            <PersonalitySelect
              key={param.name}
              uid={uid}
              label={param.name}
              value={typeof value === 'number' ? value : 0}
              onChange={(v) => setParam(index, v)}
              disabled={disabled}
            />
          )
        }
        if (param.kind === 'pid') {
          return (
            <SupportedPidSelect
              key={param.name}
              uid={uid}
              label={param.name}
              value={typeof value === 'number' ? value : 0}
              onChange={(v) => setParam(index, v)}
              disabled={disabled}
            />
          )
        }
        if (param.kind === 'int') {
          return (
            <Slider
              key={param.name}
              label={param.name}
              value={typeof value === 'number' ? value : 0}
              onChange={(v) => setParam(index, v)}
              min={param.min ?? 0}
              max={param.max ?? 255}
              disabled={disabled}
            />
          )
        }
        if (param.kind === 'choice') {
          return (
            <Select
              key={param.name}
              label={param.name}
              value={typeof value === 'string' ? value : String(value)}
              options={param.options ?? []}
              onChange={(v) => setParam(index, v)}
              disabled={disabled}
            />
          )
        }
        return (
          <TextField
            key={param.name}
            label={param.name}
            value={typeof value === 'string' ? value : String(value)}
            onChange={(v) => setParam(index, v)}
            disabled={disabled}
          />
        )
        })}
      </div>
      {result !== null && <p className="method-form-result">Result: {result}</p>}
      {error !== null && <p className="method-form-error">{error}</p>}
    </form>
  )
}
