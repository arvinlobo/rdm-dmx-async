import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { CapabilityReport } from '../../api/types'

vi.mock('../../api/client', () => ({
  api: {
    getCapabilities: vi.fn(),
    getModuleSchema: vi.fn(),
    getModuleState: vi.fn(),
    callMethod: vi.fn(),
    getSensorReadings: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

import { api } from '../../api/client'
import { CapabilityDashboard } from '../CapabilityDashboard'

const REPORT: CapabilityReport = {
  modules: {
    device_label: { supported: true, pids: [1], supported_pids: [1], missing_pids: [], coverage: 1 },
    proxy: { supported: false, pids: [2], supported_pids: [], missing_pids: [2], coverage: 0 },
  },
}

describe('CapabilityDashboard', () => {
  beforeEach(() => {
    vi.mocked(api.getCapabilities).mockReset()
    vi.mocked(api.getModuleSchema).mockReset()
    vi.mocked(api.getModuleState).mockReset()
  })

  it('renders a ModulePanel only for supported modules', async () => {
    vi.mocked(api.getCapabilities).mockResolvedValue(REPORT)
    vi.mocked(api.getModuleSchema).mockResolvedValue({ module: 'device_label', methods: [] })
    vi.mocked(api.getModuleState).mockResolvedValue({})

    render(<CapabilityDashboard uid="ABC" />)

    await waitFor(() => expect(screen.getByText('Device Label')).toBeInTheDocument())
    expect(screen.queryByText('Proxy')).not.toBeInTheDocument()
  })

  it('re-fetches capabilities when the uid changes (dropdown re-selection)', async () => {
    vi.mocked(api.getCapabilities).mockResolvedValue(REPORT)
    vi.mocked(api.getModuleSchema).mockResolvedValue({ module: 'device_label', methods: [] })
    vi.mocked(api.getModuleState).mockResolvedValue({})

    const { rerender } = render(<CapabilityDashboard uid="ABC" />)
    await waitFor(() => expect(api.getCapabilities).toHaveBeenCalledWith('ABC'))

    rerender(<CapabilityDashboard uid="XYZ" />)
    await waitFor(() => expect(api.getCapabilities).toHaveBeenCalledWith('XYZ'))
  })

  it('shows a message when no modules are supported', async () => {
    vi.mocked(api.getCapabilities).mockResolvedValue({ modules: {} })
    render(<CapabilityDashboard uid="ABC" />)
    expect(await screen.findByText('This device reports no supported modules.')).toBeInTheDocument()
  })

  it('shows an error message when the capability request fails', async () => {
    vi.mocked(api.getCapabilities).mockRejectedValue(new Error('down'))
    render(<CapabilityDashboard uid="ABC" />)
    expect(await screen.findByText('Failed to load capabilities')).toBeInTheDocument()
  })

  it('renders SensorsPanel for the sensors module and skips sensor_definitions', async () => {
    vi.mocked(api.getCapabilities).mockResolvedValue({
      modules: {
        sensors: { supported: true, pids: [1], supported_pids: [1], missing_pids: [], coverage: 1 },
        sensor_definitions: { supported: true, pids: [2], supported_pids: [2], missing_pids: [], coverage: 1 },
      },
    })
    vi.mocked(api.getSensorReadings).mockResolvedValue({ sensors: [] })
    vi.mocked(api.getModuleSchema).mockResolvedValue({ module: 'sensors', methods: [] })

    render(<CapabilityDashboard uid="ABC" />)

    await waitFor(() => expect(api.getSensorReadings).toHaveBeenCalledWith('ABC'))
    expect(api.getModuleSchema).not.toHaveBeenCalledWith('ABC', 'sensor_definitions')
  })
})
