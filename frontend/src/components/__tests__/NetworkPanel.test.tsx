import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { StatusResponse } from '../../api/types'
import { NetworkPanel } from '../NetworkPanel'

const DISCONNECTED: StatusResponse = { connected: false, port: null, device_count: 0 }
const CONNECTED: StatusResponse = { connected: true, port: 'COM5', device_count: 2 }
const INTERFACE_TYPES = ['ENTTEC_USB_PRO', 'DMXKING_ULTRA_DMX', 'BARE_USB_RS485']

describe('NetworkPanel', () => {
  it('shows a connect control with available ports when disconnected', () => {
    render(
      <NetworkPanel
        status={DISCONNECTED}
        ports={['COM3', 'COM5']}
        interfaceTypes={INTERFACE_TYPES}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: 'Connect' })).toBeInTheDocument()
    expect(screen.getByText('COM3')).toBeInTheDocument()
    expect(screen.getByText('COM5')).toBeInTheDocument()
  })

  it('calls onConnect with null port and the default interface type when nothing is changed', async () => {
    const onConnect = vi.fn()
    render(
      <NetworkPanel
        status={DISCONNECTED}
        ports={['COM5']}
        interfaceTypes={INTERFACE_TYPES}
        onConnect={onConnect}
        onDisconnect={vi.fn()}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Connect' }))
    expect(onConnect).toHaveBeenCalledWith({
      port: null,
      interfaceType: 'ENTTEC_USB_PRO',
      controllerUid: null,
    })
  })

  it('calls onConnect with the selected port', async () => {
    const onConnect = vi.fn()
    render(
      <NetworkPanel
        status={DISCONNECTED}
        ports={['COM5']}
        interfaceTypes={INTERFACE_TYPES}
        onConnect={onConnect}
        onDisconnect={vi.fn()}
      />,
    )
    await userEvent.type(screen.getByLabelText('Port'), 'COM5')
    await userEvent.click(screen.getByRole('button', { name: 'Connect' }))
    expect(onConnect).toHaveBeenCalledWith(
      expect.objectContaining({ port: 'COM5' }),
    )
  })

  it('calls onConnect with a manually typed port not in the detected list', async () => {
    const onConnect = vi.fn()
    render(
      <NetworkPanel
        status={DISCONNECTED}
        ports={['COM5']}
        interfaceTypes={INTERFACE_TYPES}
        onConnect={onConnect}
        onDisconnect={vi.fn()}
      />,
    )
    await userEvent.type(screen.getByLabelText('Port'), 'COM42')
    await userEvent.click(screen.getByRole('button', { name: 'Connect' }))
    expect(onConnect).toHaveBeenCalledWith(
      expect.objectContaining({ port: 'COM42' }),
    )
  })

  it('calls onConnect with the selected interface type and controller UID', async () => {
    const onConnect = vi.fn()
    render(
      <NetworkPanel
        status={DISCONNECTED}
        ports={['COM7']}
        interfaceTypes={INTERFACE_TYPES}
        onConnect={onConnect}
        onDisconnect={vi.fn()}
      />,
    )
    await userEvent.selectOptions(screen.getByLabelText('Interface'), 'BARE_USB_RS485')
    await userEvent.type(screen.getByLabelText('Controller UID'), '454E00000000')
    await userEvent.click(screen.getByRole('button', { name: 'Connect' }))
    expect(onConnect).toHaveBeenCalledWith({
      port: null,
      interfaceType: 'BARE_USB_RS485',
      controllerUid: '454E00000000',
    })
  })

  it('disables Connect until a controller UID is entered for interfaces with no onboard UID', async () => {
    render(
      <NetworkPanel
        status={DISCONNECTED}
        ports={['COM7']}
        interfaceTypes={INTERFACE_TYPES}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
      />,
    )
    await userEvent.selectOptions(screen.getByLabelText('Interface'), 'BARE_USB_RS485')
    expect(screen.getByRole('button', { name: 'Connect' })).toBeDisabled()
    expect(screen.getByText(/Required: Bare USB-RS485 \(FTDI\) has no onboard UID/)).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Controller UID'), '454E00000000')
    expect(screen.getByRole('button', { name: 'Connect' })).toBeEnabled()
  })

  it('does not require a controller UID for Enttec interfaces', () => {
    render(
      <NetworkPanel
        status={DISCONNECTED}
        ports={['COM5']}
        interfaceTypes={INTERFACE_TYPES}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: 'Connect' })).toBeEnabled()
    expect(screen.getByText(/Optional - auto-queried/)).toBeInTheDocument()
  })

  it('shows connection status and a disconnect control when connected', async () => {
    const onDisconnect = vi.fn()
    render(
      <NetworkPanel
        status={CONNECTED}
        ports={[]}
        interfaceTypes={INTERFACE_TYPES}
        onConnect={vi.fn()}
        onDisconnect={onDisconnect}
      />,
    )
    expect(screen.getByText(/Connected on/)).toBeInTheDocument()
    expect(screen.getByText('COM5', { exact: false })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Disconnect' }))
    expect(onDisconnect).toHaveBeenCalledOnce()
  })
})
