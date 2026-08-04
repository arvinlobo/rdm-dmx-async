import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { CapabilityReport } from '../api/types'
import { MODULE_CATEGORIES, MODULE_CATEGORY_ACCENTS, MODULE_CATEGORY_ORDER, MODULE_LABELS } from '../api/types'
import { useToast } from '../context/ToastContext'
import { ModulePanel } from './ModulePanel'
import { Skeleton } from './Skeleton'
import { SensorsPanel } from './SensorsPanel'

export interface CapabilityDashboardProps {
  uid: string
}

const UNCATEGORIZED = 'Other'

/** Fetches the selected device's capability report and renders one ModulePanel per supported module. */
export function CapabilityDashboard({ uid }: CapabilityDashboardProps) {
  const [report, setReport] = useState<CapabilityReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { showToast } = useToast()

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
        if (cancelled) return
        const message = err instanceof ApiError ? err.message : 'Failed to load capabilities'
        setError(message)
        showToast(message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [uid, showToast])

  if (loading) {
    return (
      <div className="capability-dashboard">
        <div className="module-panel module-panel-loading">
          <Skeleton lines={4} />
        </div>
        <div className="module-panel module-panel-loading">
          <Skeleton lines={3} />
        </div>
      </div>
    )
  }
  if (error) return <p className="dashboard-status dashboard-error">{error}</p>
  if (!report) return null

  const supportedModules = Object.entries(report.modules).filter(([, info]) => info.supported)

  if (supportedModules.length === 0) {
    return <p className="dashboard-status">This device reports no supported modules.</p>
  }

  // Group supported modules by dashboard section so related cards sit together.
  const sections = new Map<string, string[]>()
  for (const [moduleName] of supportedModules) {
    if (moduleName === 'sensor_definitions') continue // folded into the sensors module's own display
    const category = MODULE_CATEGORIES[moduleName] ?? UNCATEGORIZED
    const existing = sections.get(category) ?? []
    existing.push(moduleName)
    sections.set(category, existing)
  }

  const orderedCategories = [...MODULE_CATEGORY_ORDER, UNCATEGORIZED].filter((category) => sections.has(category))

  return (
    <div className="capability-sections">
      {orderedCategories.map((category) => (
        <section key={category} className="capability-section">
          <h2 className="capability-section-title">{category}</h2>
          <div className="capability-dashboard">
            {sections.get(category)!.map((moduleName) =>
              moduleName === 'sensors' ? (
                <SensorsPanel key={moduleName} uid={uid} />
              ) : (
                <ModulePanel
                  key={moduleName}
                  uid={uid}
                  moduleName={moduleName}
                  label={MODULE_LABELS[moduleName] ?? moduleName}
                  accentClass={MODULE_CATEGORY_ACCENTS[category]}
                />
              ),
            )}
          </div>
        </section>
      ))}
    </div>
  )
}
