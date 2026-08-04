import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ReadOnlyField } from '../ReadOnlyField'

describe('ReadOnlyField', () => {
  it('renders a disabled slider for number values', () => {
    render(<ReadOnlyField name="get_hours" value={120} />)
    expect(screen.getByRole('slider')).toBeDisabled()
    expect(screen.getByRole('slider')).toHaveValue('120')
  })

  it('renders a disabled checkbox for boolean values', () => {
    render(<ReadOnlyField name="get_state" value={true} />)
    expect(screen.getByRole('checkbox')).toBeDisabled()
    expect(screen.getByRole('checkbox')).toBeChecked()
  })

  it('renders a disabled text field for string values', () => {
    render(<ReadOnlyField name="get" value="Fixture 1" />)
    expect(screen.getByDisplayValue('Fixture 1')).toBeDisabled()
  })

  it('renders a placeholder for null values', () => {
    render(<ReadOnlyField name="get_model" value={null} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('renders JSON for object/array values', () => {
    render(<ReadOnlyField name="get_status" value={{ a: 1 }} />)
    expect(screen.getByText('{"a":1}')).toBeInTheDocument()
  })
})
