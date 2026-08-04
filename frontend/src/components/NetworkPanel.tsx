import { useState } from 'react'
import type { StatusResponse } from '../api/types'
import { Button } from './Button'

export interface NetworkPanelProps {
  status: StatusResponse
  ports: string[]
  connecting?: boolean
  onConnect: (port: string | null) => void
  onDisconnect: () => void
}

/** Connect/disconnect control for the serial interface (auto-detect if no port chosen). */
export function NetworkPanel({ status, ports, connecting, onConnect, onDisconnect }: NetworkPanelProps) {
  const [selectedPort, setSelectedPort] = useState('')

  if (status.connected) {
    return (
      <section className="network-panel">
        <p className="status-pill status-pill-connected">
          <span className="status-dot" aria-hidden="true" />
          Connected on <strong>{status.port}</strong> ({status.device_count} device
          {status.device_count === 1 ? '' : 's'})
        </p>
        <Button onClick={onDisconnect} variant="secondary">
          Disconnect
        </Button>
      </section>
    )
  }

  return (
    <section className="network-panel">
      <p className="status-pill status-pill-disconnected">
        <span className="status-dot" aria-hidden="true" />
        Not connected
      </p>
      <label className="field">
        <span className="field-label">Port</span>
        <select
          aria-label="Port"
          value={selectedPort}
          onChange={(event) => setSelectedPort(event.target.value)}
        >
          <option value="">Auto-detect</option>
          {ports.map((port) => (
            <option key={port} value={port}>
              {port}
            </option>
          ))}
        </select>
      </label>
      <Button onClick={() => onConnect(selectedPort || null)} disabled={connecting}>
        {connecting ? 'Connecting…' : 'Connect'}
      </Button>
    </section>
  )
}
