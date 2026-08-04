import type { DeviceSummary } from '../api/types'
import { Button } from './Button'

export interface DeviceSelectorProps {
  devices: DeviceSummary[]
  selectedUid: string | null
  onSelect: (uid: string | null) => void
  onDiscover: () => void
  discovering?: boolean
}

/** Dropdown of known devices; selecting a different device drives the dynamic capability UI below it. */
export function DeviceSelector({ devices, selectedUid, onSelect, onDiscover, discovering }: DeviceSelectorProps) {
  return (
    <section className="device-selector">
      <label className="field">
        <span className="field-label">Device</span>
        <select
          aria-label="Device"
          value={selectedUid ?? ''}
          onChange={(event) => onSelect(event.target.value || null)}
        >
          <option value="">-- Select a device --</option>
          {devices.map((device) => (
            <option key={device.uid} value={device.uid}>
              {device.device_label || device.model || device.uid} ({device.uid})
            </option>
          ))}
        </select>
      </label>
      <Button onClick={onDiscover} disabled={discovering} variant="secondary" loading={discovering}>
        Discover Devices
      </Button>
    </section>
  )
}
