import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Slider } from '../Slider'

describe('Slider', () => {
  it('renders the label and current value', () => {
    render(<Slider label="Hours" value={42} onChange={vi.fn()} />)
    expect(screen.getByText('Hours')).toBeInTheDocument()
    expect(screen.getByRole('slider')).toHaveValue('42')
  })

  it('defaults to a 0-255 range', () => {
    render(<Slider label="Level" value={10} onChange={vi.fn()} />)
    const slider = screen.getByRole('slider')
    expect(slider).toHaveAttribute('min', '0')
    expect(slider).toHaveAttribute('max', '255')
  })

  it('calls onChange with a number when the range input changes', () => {
    const onChange = vi.fn()
    render(<Slider label="Level" value={10} onChange={onChange} />)
    fireEvent.change(screen.getByRole('slider'), { target: { value: '50' } })
    expect(onChange).toHaveBeenCalledWith(50)
  })

  it('calls onChange when the numeric field is edited', () => {
    const onChange = vi.fn()
    render(<Slider label="Level" value={10} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Level value'), { target: { value: '99' } })
    expect(onChange).toHaveBeenCalledWith(99)
  })

  it('disables both inputs when disabled', () => {
    render(<Slider label="Level" value={10} onChange={vi.fn()} disabled />)
    expect(screen.getByRole('slider')).toBeDisabled()
    expect(screen.getByLabelText('Level value')).toBeDisabled()
  })
})
