import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../client'

describe('api client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns parsed JSON on success', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ports: ['COM5'] }), { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.getPorts()

    expect(result).toEqual({ ports: ['COM5'] })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/network/ports',
      expect.objectContaining({ headers: { 'Content-Type': 'application/json' } }),
    )
  })

  it('throws an ApiError with the backend detail message on failure', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Not connected' }), { status: 409 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.getStatus()).rejects.toMatchObject(
      new ApiError(409, 'Not connected'),
    )
  })

  it('falls back to statusText when the error body is not JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('', { status: 500, statusText: 'Server Error' }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.getStatus()).rejects.toMatchObject({ status: 500, message: 'Server Error' })
  })

  it('sends a JSON body for POST requests like connect()', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ connected: true, port: 'COM5', device_count: 0 }), { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await api.connect({ port: 'COM5' })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/network/connect',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ port: 'COM5' }) }),
    )
  })

  it('sends positional args for callMethod()', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ result: true }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.callMethod('ABC', 'lamp', 'set_hours', [200])

    expect(result).toEqual({ result: true })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/devices/ABC/modules/lamp/set_hours',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ args: [200] }) }),
    )
  })
})
