import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { ModuleSchema, SensorReading } from '../api/types'
import { useToast } from '../context/useToast'
import { MethodForm } from './MethodForm'
import { Skeleton } from './Skeleton'

export interface SensorsPanelProps {
  uid: string
}

// RDM E1.20 SENSOR_DEFINITION unit codes -> display label (most common subset).
const UNIT_LABEL: Record<number, string> = {
  0: '',
  1: '°C',
  2: 'V DC',
  3: 'V AC (peak)',
  4: 'V AC (RMS)',
  5: 'A DC',
  6: 'A AC (peak)',
  7: 'A AC (RMS)',
  8: 'Hz',
  9: 'Ω',
  10: 'W',
}

// The backend already scales these by the sensor's SI unit prefix (ANSI E1.20),
// so this only needs to attach the unit label - no further exponent math here.
function formatValue(value: number | null, unit: number): string {
  if (value === null) return '—'
  const label = UNIT_LABEL[unit] ?? `unit ${unit}`
  return `${value.toFixed(2)} ${label}`.trim()
}

// Clamps the present value into the sensor's declared range as a 0-100% gauge width.
function gaugePercent(sensor: SensorReading): number {
  if (sensor.present_value === null) return 0
  const span = sensor.range_max - sensor.range_min
  if (span <= 0) return 0
  const fraction = (sensor.present_value - sensor.range_min) / span
  return Math.min(100, Math.max(0, fraction * 100))
}

/** Maps each sensor's live value to its definition (description/unit/scaling) for display. */
export function SensorsPanel({ uid }: SensorsPanelProps) {
  const [readings, setReadings] = useState<SensorReading[] | null>(null)
  const [schema, setSchema] = useState<ModuleSchema | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { showToast } = useToast()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [readingsResult, schemaResult] = await Promise.all([
        api.getSensorReadings(uid),
        api.getModuleSchema(uid, 'sensors'),
      ])
      setReadings(readingsResult.sensors)
      setSchema(schemaResult)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load sensors'
      setError(message)
      showToast(`Sensors: ${message}`)
      setReadings(null)
      setSchema(null)
    } finally {
      setLoading(false)
    }
  }, [uid, showToast])

  useEffect(() => {
    void load()
  }, [load])

  if (loading) {
    return (
      <div className="module-panel module-panel-loading category-sensors">
        <p className="module-panel-summary module-panel-summary-static">Sensors</p>
        <span className="sr-only">Loading Sensors…</span>
        <Skeleton lines={3} />
      </div>
    )
  }
  if (error) return <p className="module-panel-status module-panel-error">{error}</p>
  if (!readings) return null

  const actions = schema?.methods.filter((method) => !method.is_getter) ?? []

  return (
    <details className="module-panel sensors-panel category-sensors" open>
      <summary className="module-panel-summary">Sensors</summary>
      {readings.length === 0 ? (
        <p>This device has no sensors.</p>
      ) : (
        <table className="sensors-table">
          <thead>
            <tr>
              <th>Sensor</th>
              <th>Value</th>
              <th>Range</th>
            </tr>
          </thead>
          <tbody>
            {readings.map((sensor) => (
              <tr key={sensor.sensor_number}>
                <td>{sensor.description || `#${sensor.sensor_number}`}</td>
                <td>
                  <div className="sensor-value">
                    <span>{formatValue(sensor.present_value, sensor.unit)}</span>
                    <span className="sensor-gauge" aria-hidden="true">
                      <span className="sensor-gauge-fill" style={{ width: `${gaugePercent(sensor)}%` }} />
                    </span>
                  </div>
                </td>
                <td>
                  {formatValue(sensor.range_min, sensor.unit)} to{' '}
                  {formatValue(sensor.range_max, sensor.unit)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {actions.length > 0 && (
        <div className="module-panel-actions">
          {actions.map((method) => (
            <MethodForm key={method.name} uid={uid} moduleName="sensors" method={method} onSuccess={load} />
          ))}
        </div>
      )}
    </details>
  )
}
