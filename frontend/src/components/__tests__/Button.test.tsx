import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Button } from '../Button'

describe('Button', () => {
  it('renders children and calls onClick', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Connect</Button>)
    await userEvent.click(screen.getByRole('button', { name: 'Connect' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('applies the requested variant class', () => {
    render(<Button variant="secondary">Disconnect</Button>)
    expect(screen.getByRole('button')).toHaveClass('btn-secondary')
  })

  it('is disabled when disabled is set', () => {
    render(<Button disabled>Run</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('supports type="submit" without an onClick handler', () => {
    render(<Button type="submit">Run</Button>)
    expect(screen.getByRole('button')).toHaveAttribute('type', 'submit')
  })
})
