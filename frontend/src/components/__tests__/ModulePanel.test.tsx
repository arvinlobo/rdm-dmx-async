import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ModuleSchema } from '../../api/types'

vi.mock('../../api/client', () => ({
  api: { getModuleSchema: vi.fn(), getModuleState: vi.fn(), callMethod: vi.fn() },
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

import { api } from '../../api/client'
import { ModulePanel } from '../ModulePanel'

const LAMP_SCHEMA: ModuleSchema = {
  module: 'lamp',
  methods: [
    {
      name: 'get_hours',
      is_getter: true,
      supported: true,
      params: [{ name: 'use_cache', kind: 'bool', required: false, default: true, min: null, max: null }],
    },
    {
      name: 'set_hours',
      is_getter: false,
      supported: true,
      params: [{ name: 'hours', kind: 'int', required: true, default: null, min: 0, max: 255 }],
    },
  ],
}

describe('ModulePanel', () => {
  beforeEach(() => {
    vi.mocked(api.getModuleSchema).mockReset()
    vi.mocked(api.getModuleState).mockReset()
  })

  it('shows a loading state, then renders read-only state and an action form', async () => {
    vi.mocked(api.getModuleSchema).mockResolvedValue(LAMP_SCHEMA)
    vi.mocked(api.getModuleState).mockResolvedValue({ get_hours: 120 })

    render(<ModulePanel uid="ABC" moduleName="lamp" label="Lamp Control" />)

    expect(screen.getByText('Loading Lamp Control…')).toBeInTheDocument()

    await waitFor(() => expect(screen.getByText('Lamp Control')).toBeInTheDocument())
    expect(screen.getByText('get_hours')).toBeInTheDocument()
    expect(screen.getByText('set_hours')).toBeInTheDocument()
    expect(api.getModuleSchema).toHaveBeenCalledWith('ABC', 'lamp')
    expect(api.getModuleState).toHaveBeenCalledWith('ABC', 'lamp')
  })

  it('re-fetches when the module name changes (device/module switch)', async () => {
    vi.mocked(api.getModuleSchema).mockResolvedValue(LAMP_SCHEMA)
    vi.mocked(api.getModuleState).mockResolvedValue({ get_hours: 120 })

    const { rerender } = render(<ModulePanel uid="ABC" moduleName="lamp" label="Lamp Control" />)
    await waitFor(() => expect(api.getModuleSchema).toHaveBeenCalledWith('ABC', 'lamp'))

    rerender(<ModulePanel uid="XYZ" moduleName="lamp" label="Lamp Control" />)
    await waitFor(() => expect(api.getModuleSchema).toHaveBeenCalledWith('XYZ', 'lamp'))
  })

  it('shows an error message when the module fails to load', async () => {
    vi.mocked(api.getModuleSchema).mockRejectedValue(new Error('nope'))
    vi.mocked(api.getModuleState).mockResolvedValue({})

    render(<ModulePanel uid="ABC" moduleName="lamp" label="Lamp Control" />)
    expect(await screen.findByText('Failed to load module')).toBeInTheDocument()
  })
})
