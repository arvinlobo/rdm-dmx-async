import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { DeviceSummary } from '../../api/types'
import { DeviceSelector } from '../DeviceSelector'

const DEVICES: DeviceSummary[] = [
  {
    uid: '454E00000001',
    manufacturer: 'Acme',
    device_label: 'Fixture 1',
    model: 'Widget',
    dmx_start_address: 1,
    dmx_personality: 1,
    dmx_footprint: 4,
  },
  {
    uid: '454E00000002',
    manufacturer: 'Acme',
    device_label: '',
    model: 'Widget 2',
    dmx_start_address: 5,
    dmx_personality: 1,
    dmx_footprint: 4,
  },
]

describe('DeviceSelector', () => {
  it('lists all devices by label, falling back to model then uid', () => {
    render(
      <DeviceSelector devices={DEVICES} selectedUid={null} onSelect={vi.fn()} onDiscover={vi.fn()} />,
    )
    expect(screen.getByText(/Fixture 1 \(454E00000001\)/)).toBeInTheDocument()
    expect(screen.getByText(/Widget 2 \(454E00000002\)/)).toBeInTheDocument()
  })

  it('calls onSelect with the chosen uid', async () => {
    const onSelect = vi.fn()
    render(
      <DeviceSelector devices={DEVICES} selectedUid={null} onSelect={onSelect} onDiscover={vi.fn()} />,
    )
    await userEvent.selectOptions(screen.getByLabelText('Device'), '454E00000002')
    expect(onSelect).toHaveBeenCalledWith('454E00000002')
  })

  it('calls onDiscover when the discover button is clicked', async () => {
    const onDiscover = vi.fn()
    render(<DeviceSelector devices={[]} selectedUid={null} onSelect={vi.fn()} onDiscover={onDiscover} />)
    await userEvent.click(screen.getByRole('button', { name: 'Discover Devices' }))
    expect(onDiscover).toHaveBeenCalledOnce()
  })

  it('shows a discovering label and disables the button while discovering', () => {
    render(
      <DeviceSelector devices={[]} selectedUid={null} onSelect={vi.fn()} onDiscover={vi.fn()} discovering />,
    )
    expect(screen.getByRole('button', { name: 'Discovering…' })).toBeDisabled()
  })
})
