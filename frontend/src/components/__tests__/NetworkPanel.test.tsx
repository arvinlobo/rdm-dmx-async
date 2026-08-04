import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { StatusResponse } from '../../api/types'
import { NetworkPanel } from '../NetworkPanel'

const DISCONNECTED: StatusResponse = { connected: false, port: null, device_count: 0 }
const CONNECTED: StatusResponse = { connected: true, port: 'COM5', device_count: 2 }

describe('NetworkPanel', () => {
  it('shows a connect control with available ports when disconnected', () => {
    render(
      <NetworkPanel status={DISCONNECTED} ports={['COM3', 'COM5']} onConnect={vi.fn()} onDisconnect={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: 'Connect' })).toBeInTheDocument()
    expect(screen.getByText('COM3')).toBeInTheDocument()
    expect(screen.getByText('COM5')).toBeInTheDocument()
  })

  it('calls onConnect with null when no port is chosen (auto-detect)', async () => {
    const onConnect = vi.fn()
    render(<NetworkPanel status={DISCONNECTED} ports={['COM5']} onConnect={onConnect} onDisconnect={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Connect' }))
    expect(onConnect).toHaveBeenCalledWith(null)
  })

  it('calls onConnect with the selected port', async () => {
    const onConnect = vi.fn()
    render(<NetworkPanel status={DISCONNECTED} ports={['COM5']} onConnect={onConnect} onDisconnect={vi.fn()} />)
    await userEvent.selectOptions(screen.getByLabelText('Port'), 'COM5')
    await userEvent.click(screen.getByRole('button', { name: 'Connect' }))
    expect(onConnect).toHaveBeenCalledWith('COM5')
  })

  it('shows connection status and a disconnect control when connected', async () => {
    const onDisconnect = vi.fn()
    render(<NetworkPanel status={CONNECTED} ports={[]} onConnect={vi.fn()} onDisconnect={onDisconnect} />)
    expect(screen.getByText(/Connected on/)).toBeInTheDocument()
    expect(screen.getByText('COM5', { exact: false })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Disconnect' }))
    expect(onDisconnect).toHaveBeenCalledOnce()
  })
})
