import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { CapabilityReport } from '../api/types'
import { MODULE_LABELS } from '../api/types'
import { ModulePanel } from './ModulePanel'
import { SensorsPanel } from './SensorsPanel'

export interface CapabilityDashboardProps {
  uid: string
}

/** Fetches the selected device's capability report and renders one ModulePanel per supported module. */
export function CapabilityDashboard({ uid }: CapabilityDashboardProps) {
  const [report, setReport] = useState<CapabilityReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setReport(null)
    api
      .getCapabilities(uid)
      .then((result) => {
        if (!cancelled) setReport(result)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Failed to load capabilities')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [uid])

  if (loading) return <p className="dashboard-status">Loading device capabilities…</p>
  if (error) return <p className="dashboard-status dashboard-error">{error}</p>
  if (!report) return null

  const supportedModules = Object.entries(report.modules).filter(([, info]) => info.supported)

  if (supportedModules.length === 0) {
    return <p className="dashboard-status">This device reports no supported modules.</p>
  }

  return (
    <div className="capability-dashboard">
      {supportedModules.map(([moduleName]) =>
        // sensor_definitions is folded into the sensors module's own mapped display.
        moduleName === 'sensor_definitions' ? null : moduleName === 'sensors' ? (
          <SensorsPanel key={moduleName} uid={uid} />
        ) : (
          <ModulePanel key={moduleName} uid={uid} moduleName={moduleName} label={MODULE_LABELS[moduleName] ?? moduleName} />
        ),
      )}
    </div>
  )
}
