import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Checkbox } from '../Checkbox'

describe('Checkbox', () => {
  it('renders the label and checked state', () => {
    render(<Checkbox label="Enabled" checked onChange={vi.fn()} />)
    expect(screen.getByRole('checkbox')).toBeChecked()
    expect(screen.getByText('Enabled')).toBeInTheDocument()
  })

  it('calls onChange with the toggled value', async () => {
    const onChange = vi.fn()
    render(<Checkbox label="Enabled" checked={false} onChange={onChange} />)
    await userEvent.click(screen.getByRole('checkbox'))
    expect(onChange).toHaveBeenCalledWith(true)
  })

  it('disables the input when disabled', () => {
    render(<Checkbox label="Enabled" checked={false} onChange={vi.fn()} disabled />)
    expect(screen.getByRole('checkbox')).toBeDisabled()
  })
})
