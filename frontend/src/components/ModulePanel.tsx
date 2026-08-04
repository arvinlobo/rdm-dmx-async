import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { ModuleSchema } from '../api/types'
import { useToast } from '../context/ToastContext'
import { MethodForm } from './MethodForm'
import { ReadOnlyField } from './ReadOnlyField'
import { Skeleton } from './Skeleton'

export interface ModulePanelProps {
  uid: string
  moduleName: string
  label: string
  accentClass?: string
}

/** Dynamically renders one device API module's read-only state plus its callable actions. */
export function ModulePanel({ uid, moduleName, label, accentClass }: ModulePanelProps) {
  const [schema, setSchema] = useState<ModuleSchema | null>(null)
  const [state, setState] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { showToast } = useToast()
  const hasLoadedOnceRef = useRef(false)

  // Only the very first load shows the full-panel skeleton; refreshes triggered by a
  // method's onSuccess must not unmount the already-rendered MethodForms, or the result
  // it just displayed (e.g. a decoded get_parameter_description) disappears instantly.
  const load = useCallback(async () => {
    const isFirstLoad = !hasLoadedOnceRef.current
    if (isFirstLoad) setLoading(true)
    setError(null)
    try {
      const [schemaResult, stateResult] = await Promise.all([
        api.getModuleSchema(uid, moduleName),
        api.getModuleState(uid, moduleName),
      ])
      setSchema(schemaResult)
      setState(stateResult)
      hasLoadedOnceRef.current = true
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load module'
      setError(message)
      showToast(`${label}: ${message}`)
      setSchema(null)
      setState(null)
    } finally {
      if (isFirstLoad) setLoading(false)
    }
  }, [uid, moduleName, label, showToast])

  useEffect(() => {
    hasLoadedOnceRef.current = false
    void load()
  }, [load])

  if (loading) {
    return (
      <div className={`module-panel module-panel-loading${accentClass ? ` ${accentClass}` : ''}`}>
        <p className="module-panel-summary module-panel-summary-static">{label}</p>
        <span className="sr-only">Loading {label}…</span>
        <Skeleton lines={3} />
      </div>
    )
  }
  if (error) return <p className="module-panel-status module-panel-error">{error}</p>
  if (!schema) return null

  // `is_getter` methods are already auto-fetched into `state` above; actions are everything else.
  const actions = schema.methods.filter((method) => !method.is_getter)
  const stateEntries = state ? Object.entries(state) : []

  return (
    <details className={`module-panel${accentClass ? ` ${accentClass}` : ''}`} open>
      <summary className="module-panel-summary">{label}</summary>

      {stateEntries.length > 0 && (
        <div className="module-panel-state">
          {stateEntries.map(([name, value]) => (
            <ReadOnlyField key={name} name={name} value={value} />
          ))}
        </div>
      )}

      {actions.length > 0 && (
        <div className="module-panel-actions">
          {actions.map((method) => (
            <MethodForm key={method.name} uid={uid} moduleName={moduleName} method={method} onSuccess={load} />
          ))}
        </div>
      )}
    </details>
  )
}
