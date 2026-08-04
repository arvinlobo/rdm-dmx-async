import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { api, ApiError } from './api/client'
import type { DeviceSummary, StatusResponse } from './api/types'
import { CapabilityDashboard } from './components/CapabilityDashboard'
import { DeviceSelector } from './components/DeviceSelector'
import { DmxSlotPanel } from './components/DmxSlotPanel'
import { NetworkPanel } from './components/NetworkPanel'

const EMPTY_STATUS: StatusResponse = { connected: false, port: null, device_count: 0 }

function App() {
  const [status, setStatus] = useState<StatusResponse>(EMPTY_STATUS)
  const [ports, setPorts] = useState<string[]>([])
  const [devices, setDevices] = useState<DeviceSummary[]>([])
  const [selectedUid, setSelectedUid] = useState<string | null>(null)
  const [connecting, setConnecting] = useState(false)
  const [discovering, setDiscovering] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await api.getStatus())
    } catch {
      // Backend unreachable at startup; leave status as disconnected.
    }
  }, [])

  const refreshPorts = useCallback(async () => {
    try {
      setPorts((await api.getPorts()).ports)
    } catch {
      setPorts([])
    }
  }, [])

  const refreshDevices = useCallback(async () => {
    try {
      setDevices((await api.listDevices()).devices)
    } catch {
      setDevices([])
    }
  }, [])

  useEffect(() => {
    void refreshStatus()
    void refreshPorts()
  }, [refreshStatus, refreshPorts])

  // Detects the backend losing its connection out from under us (e.g. a dev-server
  // --reload restart, or the serial device being unplugged) so we stop rendering
  // controls that would otherwise keep firing requests at a now-disconnected backend.
  useEffect(() => {
    const interval = window.setInterval(() => void refreshStatus(), 4000)
    return () => window.clearInterval(interval)
  }, [refreshStatus])

  useEffect(() => {
    if (status.connected) {
      void refreshDevices()
    } else {
      setDevices([])
      setSelectedUid(null)
    }
  }, [status.connected, refreshDevices])

  const handleConnect = async (port: string | null) => {
    setConnecting(true)
    setError(null)
    try {
      setStatus(await api.connect(port ? { port } : {}))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to connect')
    } finally {
      setConnecting(false)
    }
  }

  const handleDisconnect = async () => {
    setError(null)
    try {
      await api.disconnect()
      setStatus(EMPTY_STATUS)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to disconnect')
    }
  }

  const handleDiscover = async () => {
    setDiscovering(true)
    setError(null)
    try {
      setDevices((await api.discoverDevices()).devices)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Discovery failed')
    } finally {
      setDiscovering(false)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>RDM/DMX Control</h1>
      </header>

      {error && <p className="app-error">{error}</p>}

      <div className="toolbar">
        <NetworkPanel
          status={status}
          ports={ports}
          connecting={connecting}
          onConnect={(port) => void handleConnect(port)}
          onDisconnect={() => void handleDisconnect()}
        />

        {status.connected && (
          <DeviceSelector
            devices={devices}
            selectedUid={selectedUid}
            onSelect={setSelectedUid}
            onDiscover={() => void handleDiscover()}
            discovering={discovering}
          />
        )}
      </div>

      <main className="app-main">
        {status.connected && (
          <DmxSlotPanel
            uid={selectedUid}
            defaultStartAddress={devices.find((d) => d.uid === selectedUid)?.dmx_start_address ?? 1}
          />
        )}

        {selectedUid && <CapabilityDashboard uid={selectedUid} />}
      </main>
    </div>
  )
}

export default App
