import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { ModuleSchema, SensorReading } from '../api/types'
import { MethodForm } from './MethodForm'

export interface SensorsPanelProps {
  uid: string
}

// RDM E1.20 SENSOR_DEFINITION prefix codes -> power-of-ten exponent.
const PREFIX_EXPONENT: Record<number, number> = {
  0: 0,
  1: -1,
  2: -2,
  3: -3,
  4: -6,
  5: -9,
  6: -12,
  7: -15,
  8: -18,
  9: 3,
  10: 6,
  11: 9,
  12: 12,
  13: 15,
  14: 18,
  15: 21,
  16: 24,
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

function formatValue(raw: number | null, unit: number, prefix: number): string {
  if (raw === null) return '—'
  const scaled = raw * 10 ** (PREFIX_EXPONENT[prefix] ?? 0)
  const label = UNIT_LABEL[unit] ?? `unit ${unit}`
  return `${scaled.toFixed(2)} ${label}`.trim()
}

/** Maps each sensor's live value to its definition (description/unit/scaling) for display. */
export function SensorsPanel({ uid }: SensorsPanelProps) {
  const [readings, setReadings] = useState<SensorReading[] | null>(null)
  const [schema, setSchema] = useState<ModuleSchema | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

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
      setError(err instanceof ApiError ? err.message : 'Failed to load sensors')
      setReadings(null)
      setSchema(null)
    } finally {
      setLoading(false)
    }
  }, [uid])

  useEffect(() => {
    void load()
  }, [load])

  if (loading) return <p className="module-panel-status">Loading Sensors…</p>
  if (error) return <p className="module-panel-status module-panel-error">{error}</p>
  if (!readings) return null

  const actions = schema?.methods.filter((method) => !method.is_getter) ?? []

  return (
    <details className="module-panel sensors-panel" open>
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
                <td>{formatValue(sensor.present_value, sensor.unit, sensor.prefix)}</td>
                <td>
                  {formatValue(sensor.range_min, sensor.unit, sensor.prefix)} to{' '}
                  {formatValue(sensor.range_max, sensor.unit, sensor.prefix)}
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
