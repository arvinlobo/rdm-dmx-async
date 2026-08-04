import { useState } from 'react'
import type { StatusResponse } from '../api/types'
import { Button } from './Button'

export interface NetworkConnectConfig {
  port: string | null
  interfaceType: string
  controllerUid: string | null
}

export interface NetworkPanelProps {
  status: StatusResponse
  ports: string[]
  interfaceTypes: string[]
  connecting?: boolean
  onConnect: (config: NetworkConnectConfig) => void
  onDisconnect: () => void
}

const DEFAULT_INTERFACE_TYPE = 'ENTTEC_USB_PRO'

// Only the Enttec widget can report its own UID; every other interface type
// needs it supplied explicitly (see NetworkManager.start()).
const INTERFACE_TYPES_WITH_ONBOARD_UID = new Set(['ENTTEC_USB_PRO'])

// Friendlier labels for the raw backend enum names shown in the Interface select.
const INTERFACE_TYPE_LABELS: Record<string, string> = {
  ENTTEC_USB_PRO: 'Enttec USB Pro',
  DMXKING_ULTRA_DMX: 'DMXKing Ultra DMX',
  GENERIC_SERIAL: 'Generic Serial',
  BARE_USB_RS485: 'Bare USB-RS485 (FTDI)',
  CUSTOM: 'Custom',
}

function interfaceTypeLabel(type: string): string {
  return INTERFACE_TYPE_LABELS[type] ?? type
}

/** Connect/disconnect control for the serial interface (auto-detect if no port chosen). */
export function NetworkPanel({
  status,
  ports,
  interfaceTypes,
  connecting,
  onConnect,
  onDisconnect,
}: NetworkPanelProps) {
  const [selectedPort, setSelectedPort] = useState('')
  const [portSuggestionsOpen, setPortSuggestionsOpen] = useState(false)
  const [interfaceType, setInterfaceType] = useState(DEFAULT_INTERFACE_TYPE)
  const [controllerUid, setControllerUid] = useState('')
  const needsControllerUid = !INTERFACE_TYPES_WITH_ONBOARD_UID.has(interfaceType)
  const canConnect = !connecting && (!needsControllerUid || controllerUid.trim() !== '')
  const portSuggestions = ports.filter((port) =>
    port.toLowerCase().includes(selectedPort.toLowerCase()),
  )

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
        <span className="field-label">Interface</span>
        <select
          aria-label="Interface"
          value={interfaceType}
          onChange={(event) => setInterfaceType(event.target.value)}
        >
          {interfaceTypes.map((type) => (
            <option key={type} value={type}>
              {interfaceTypeLabel(type)}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span className="field-label">Port</span>
        {/* Detected ports are offered as suggestions in a self-positioned dropdown
            (native <input list>/<datalist> popups mis-position inside wrapping
            flex layouts in Chromium), but any port name can be typed in directly
            (e.g. one not enumerated by the OS at page-load time). */}
        <div className="port-combo">
          <input
            type="text"
            aria-label="Port"
            placeholder="Auto-detect"
            autoComplete="off"
            value={selectedPort}
            onChange={(event) => {
              setSelectedPort(event.target.value)
              setPortSuggestionsOpen(true)
            }}
            onFocus={() => setPortSuggestionsOpen(true)}
            onBlur={() => setPortSuggestionsOpen(false)}
          />
          <ul
            className={`port-suggestions${
              portSuggestionsOpen && portSuggestions.length > 0 ? ' port-suggestions-open' : ''
            }`}
          >
            {portSuggestions.map((port) => (
              <li key={port}>
                <button
                  type="button"
                  onMouseDown={(event) => {
                    // Prevent the input's blur (which would close this list before the click registers).
                    event.preventDefault()
                  }}
                  onClick={() => {
                    setSelectedPort(port)
                    setPortSuggestionsOpen(false)
                  }}
                >
                  {port}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </label>
      <label className="field">
        <span className="field-label">Controller UID</span>
        <input
          type="text"
          aria-label="Controller UID"
          placeholder="e.g. 454E00000000"
          value={controllerUid}
          onChange={(event) => setControllerUid(event.target.value)}
        />
        {needsControllerUid ? (
          <span className="field-hint">
            Required: {interfaceTypeLabel(interfaceType)} has no onboard UID to query.
          </span>
        ) : (
          <span className="field-hint">
            Optional - auto-queried from the {interfaceTypeLabel(interfaceType)} widget.
          </span>
        )}
      </label>
      <Button
        onClick={() =>
          onConnect({
            port: selectedPort || null,
            interfaceType,
            controllerUid: controllerUid || null,
          })
        }
        disabled={!canConnect}
        loading={connecting}
      >
        Connect
      </Button>
    </section>
  )
}
