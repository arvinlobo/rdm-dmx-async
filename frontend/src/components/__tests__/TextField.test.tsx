import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { TextField } from '../TextField'

describe('TextField', () => {
  it('renders the label and value', () => {
    render(<TextField label="Device Label" value="Fixture 1" onChange={vi.fn()} />)
    expect(screen.getByText('Device Label')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Fixture 1')).toBeInTheDocument()
  })

  it('calls onChange with the new string as the user types', async () => {
    const onChange = vi.fn()
    render(<TextField label="Device Label" value="" onChange={onChange} />)
    await userEvent.type(screen.getByLabelText('Device Label'), 'Hi')
    expect(onChange).toHaveBeenCalledWith('H')
    expect(onChange).toHaveBeenCalledWith('i')
  })

  it('respects maxLength', () => {
    render(<TextField label="Device Label" value="" onChange={vi.fn()} maxLength={32} />)
    expect(screen.getByLabelText('Device Label')).toHaveAttribute('maxlength', '32')
  })

  it('disables the input when disabled', () => {
    render(<TextField label="Device Label" value="x" onChange={vi.fn()} disabled />)
    expect(screen.getByLabelText('Device Label')).toBeDisabled()
  })
})
