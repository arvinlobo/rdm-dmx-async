import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { api, ApiError } from './api/client'
import type { DeviceSummary, StatusResponse } from './api/types'
import { CapabilityDashboard } from './components/CapabilityDashboard'
import { DeviceSelector } from './components/DeviceSelector'
import { DmxSlotPanel } from './components/DmxSlotPanel'
import type { NetworkConnectConfig } from './components/NetworkPanel'
import { NetworkPanel } from './components/NetworkPanel'
import { ThemeToggle } from './components/ThemeToggle'
import { ThemeProvider } from './context/ThemeContext'
import { ToastProvider } from './context/ToastContext'
import { useToast } from './context/useToast'

const EMPTY_STATUS: StatusResponse = { connected: false, port: null, device_count: 0 }

function AppShell() {
  const [status, setStatus] = useState<StatusResponse>(EMPTY_STATUS)
  const [ports, setPorts] = useState<string[]>([])
  const [interfaceTypes, setInterfaceTypes] = useState<string[]>([])
  const [devices, setDevices] = useState<DeviceSummary[]>([])
  const [selectedUid, setSelectedUid] = useState<string | null>(null)
  const [connecting, setConnecting] = useState(false)
  const [discovering, setDiscovering] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { showToast } = useToast()

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

  const refreshInterfaceTypes = useCallback(async () => {
    try {
      setInterfaceTypes((await api.getInterfaceTypes()).interface_types)
    } catch {
      setInterfaceTypes([])
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
    void refreshInterfaceTypes()
  }, [refreshStatus, refreshPorts, refreshInterfaceTypes])

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

  const handleConnect = async (config: NetworkConnectConfig) => {
    setConnecting(true)
    setError(null)
    try {
      setStatus(
        await api.connect({
          ...(config.port ? { port: config.port } : {}),
          interface_type: config.interfaceType,
          controller_uid: config.controllerUid,
        }),
      )
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to connect'
      setError(message)
      showToast(message)
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
      const message = err instanceof ApiError ? err.message : 'Failed to disconnect'
      setError(message)
      showToast(message)
    }
  }

  const handleDiscover = async () => {
    setDiscovering(true)
    setError(null)
    try {
      setDevices((await api.discoverDevices()).devices)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Discovery failed'
      setError(message)
      showToast(message)
    } finally {
      setDiscovering(false)
    }
  }

  const selectedDevice = devices.find((d) => d.uid === selectedUid) ?? null

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-brand">
          <span className="app-header-logo" aria-hidden="true">
            ⏻
          </span>
          <h1>RDM/DMX Control</h1>
        </div>
        <div className="app-header-actions">
          <span className={`status-pill${status.connected ? ' status-pill-connected' : ' status-pill-disconnected'}`}>
            <span className="status-dot" aria-hidden="true" />
            {status.connected ? `${status.port} · ${status.device_count} device${status.device_count === 1 ? '' : 's'}` : 'Not connected'}
          </span>
          <ThemeToggle />
        </div>
      </header>

      {status.connected && (
        <nav className="breadcrumb" aria-label="Connection context">
          <span className="breadcrumb-item">Connected → {status.port}</span>
          {selectedDevice && (
            <span className="breadcrumb-item breadcrumb-item-current">
              Device → {selectedDevice.device_label || selectedDevice.model || selectedDevice.uid}
            </span>
          )}
        </nav>
      )}

      {error && <p className="app-error">{error}</p>}

      <div className="toolbar">
        <NetworkPanel
          status={status}
          ports={ports}
          interfaceTypes={interfaceTypes}
          connecting={connecting}
          onConnect={(config) => void handleConnect(config)}
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

function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AppShell />
      </ToastProvider>
    </ThemeProvider>
  )
}

export default App
