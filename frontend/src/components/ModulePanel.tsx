import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { ModuleSchema } from '../api/types'
import { MethodForm } from './MethodForm'
import { ReadOnlyField } from './ReadOnlyField'

export interface ModulePanelProps {
  uid: string
  moduleName: string
  label: string
}

/** Dynamically renders one device API module's read-only state plus its callable actions. */
export function ModulePanel({ uid, moduleName, label }: ModulePanelProps) {
  const [schema, setSchema] = useState<ModuleSchema | null>(null)
  const [state, setState] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [schemaResult, stateResult] = await Promise.all([
        api.getModuleSchema(uid, moduleName),
        api.getModuleState(uid, moduleName),
      ])
      setSchema(schemaResult)
      setState(stateResult)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load module')
      setSchema(null)
      setState(null)
    } finally {
      setLoading(false)
    }
  }, [uid, moduleName])

  useEffect(() => {
    void load()
  }, [load])

  if (loading) return <p className="module-panel-status">Loading {label}…</p>
  if (error) return <p className="module-panel-status module-panel-error">{error}</p>
  if (!schema) return null

  // `is_getter` methods are already auto-fetched into `state` above; actions are everything else.
  const actions = schema.methods.filter((method) => !method.is_getter)
  const stateEntries = state ? Object.entries(state) : []

  return (
    <details className="module-panel" open>
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
