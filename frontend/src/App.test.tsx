import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { CapabilityReport, DeviceSummary, StatusResponse } from './api/types'

vi.mock('./api/client', () => ({
  api: {
    getStatus: vi.fn(),
    getPorts: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    listDevices: vi.fn(),
    discoverDevices: vi.fn(),
    getCapabilities: vi.fn(),
    getModuleSchema: vi.fn(),
    getModuleState: vi.fn(),
    callMethod: vi.fn(),
    sendDmx: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

import { api } from './api/client'
import App from './App'

const CONNECTED_STATUS: StatusResponse = { connected: true, port: 'COM5', device_count: 2 }

const DEVICE_A: DeviceSummary = {
  uid: '454E00000001',
  manufacturer: 'Acme',
  device_label: 'Fixture A',
  model: 'Widget',
  dmx_start_address: 1,
  dmx_personality: 1,
  dmx_footprint: 4,
}

const DEVICE_B: DeviceSummary = {
  uid: '454E00000002',
  manufacturer: 'Acme',
  device_label: 'Fixture B',
  model: 'Widget',
  dmx_start_address: 5,
  dmx_personality: 1,
  dmx_footprint: 4,
}

function capabilityReportFor(moduleName: string): CapabilityReport {
  return {
    modules: {
      [moduleName]: { supported: true, pids: [1], supported_pids: [1], missing_pids: [], coverage: 1 },
    },
  }
}

describe('App', () => {
  beforeEach(() => {
    vi.mocked(api.getStatus).mockReset().mockResolvedValue(CONNECTED_STATUS)
    vi.mocked(api.getPorts).mockReset().mockResolvedValue({ ports: ['COM5'] })
    vi.mocked(api.listDevices).mockReset().mockResolvedValue({ devices: [DEVICE_A, DEVICE_B] })
    vi.mocked(api.getCapabilities).mockReset()
    vi.mocked(api.getModuleSchema).mockReset().mockResolvedValue({ module: 'x', methods: [] })
    vi.mocked(api.getModuleState).mockReset().mockResolvedValue({})
    vi.mocked(api.sendDmx).mockReset().mockResolvedValue({ success: true })
  })

  it('shows the device dropdown once connected, populated from listDevices', async () => {
    render(<App />)
    expect(await screen.findByText(/Fixture A/)).toBeInTheDocument()
    expect(screen.getByText(/Fixture B/)).toBeInTheDocument()
  })

  it('populates a new dynamic GUI when a different device is selected from the dropdown', async () => {
    vi.mocked(api.getCapabilities).mockImplementation((uid: string) =>
      Promise.resolve(capabilityReportFor(uid === DEVICE_A.uid ? 'device_label' : 'lamp')),
    )

    render(<App />)
    await screen.findByText(/Fixture A/)

    await userEvent.selectOptions(screen.getByLabelText('Device'), DEVICE_A.uid)
    await waitFor(() => expect(api.getCapabilities).toHaveBeenCalledWith(DEVICE_A.uid))
    expect(await screen.findByText('Device Label')).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText('Device'), DEVICE_B.uid)
    await waitFor(() => expect(api.getCapabilities).toHaveBeenCalledWith(DEVICE_B.uid))
    expect(await screen.findByText('Lamp Control')).toBeInTheDocument()
    expect(screen.queryByText('Device Label')).not.toBeInTheDocument()
  })
})
