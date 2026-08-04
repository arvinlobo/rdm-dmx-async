import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ModuleMethodSpec } from '../../api/types'

vi.mock('../../api/client', () => ({
  api: { callMethod: vi.fn() },
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

import { api } from '../../api/client'
import { MethodForm } from '../MethodForm'

const SET_HOURS_METHOD: ModuleMethodSpec = {
  name: 'set_hours',
  is_getter: false,
  supported: true,
  params: [{ name: 'hours', kind: 'int', required: true, default: null, min: 0, max: 255 }],
}

const IDENTIFY_METHOD: ModuleMethodSpec = {
  name: 'identify',
  is_getter: false,
  supported: true,
  params: [{ name: 'enable', kind: 'bool', required: false, default: true, min: null, max: null }],
}

const UNSUPPORTED_METHOD: ModuleMethodSpec = {
  name: 'set_hours',
  is_getter: false,
  supported: false,
  params: [{ name: 'hours', kind: 'int', required: true, default: null, min: 0, max: 255 }],
}

describe('MethodForm', () => {
  beforeEach(() => {
    vi.mocked(api.callMethod).mockReset()
  })

  it('renders a slider for an int param and calls the API with its value', async () => {
    vi.mocked(api.callMethod).mockResolvedValue({ result: true })
    const onSuccess = vi.fn()
    render(<MethodForm uid="ABC" moduleName="lamp" method={SET_HOURS_METHOD} onSuccess={onSuccess} />)

    const slider = screen.getByRole('slider', { name: 'hours' })
    expect(slider).toHaveValue('0')

    await userEvent.click(screen.getByRole('button', { name: 'Run' }))

    expect(api.callMethod).toHaveBeenCalledWith('ABC', 'lamp', 'set_hours', [0])
    expect(await screen.findByText('Result: true')).toBeInTheDocument()
    expect(onSuccess).toHaveBeenCalledOnce()
  })

  it('renders a checkbox for a bool param, defaulting to the schema default', async () => {
    vi.mocked(api.callMethod).mockResolvedValue({ result: true })
    render(<MethodForm uid="ABC" moduleName="control" method={IDENTIFY_METHOD} />)

    const checkbox = screen.getByRole('checkbox', { name: 'enable' })
    expect(checkbox).toBeChecked()

    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    expect(api.callMethod).toHaveBeenCalledWith('ABC', 'control', 'identify', [true])
  })

  it('shows an error message when the call fails', async () => {
    vi.mocked(api.callMethod).mockRejectedValue(new Error('boom'))
    render(<MethodForm uid="ABC" moduleName="lamp" method={SET_HOURS_METHOD} />)

    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    expect(await screen.findByText('Method call failed')).toBeInTheDocument()
  })

  it('disables all fields and the Run button when the method is unsupported', () => {
    render(<MethodForm uid="ABC" moduleName="lamp" method={UNSUPPORTED_METHOD} />)

    expect(screen.getByText('Not supported by this device')).toBeInTheDocument()
    expect(screen.getByRole('slider', { name: 'hours' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Run' })).toBeDisabled()
  })
})
