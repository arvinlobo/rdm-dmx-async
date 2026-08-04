/** Thin fetch wrapper for the rdm-dmx-async REST API (see api/app.py). */

import type {
  CapabilityReport,
  ConnectRequest,
  DiscoverResponse,
  DmxSendRequest,
  MethodCallResponse,
  ModuleSchema,
  OkResponse,
  PersonalityListResponse,
  PortListResponse,
  SensorReadingsResponse,
  StatusResponse,
} from './types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// The backend serializes every RDM call over one physical half-duplex serial
// port, so firing many requests at once (e.g. CapabilityDashboard mounting
// every ModulePanel concurrently) just makes them all queue up server-side
// and race each request's own retry timeout against that queue-wait time.
// Serializing here means each request completes (or fails) on its own
// timeout budget instead of starving behind unrelated in-flight calls.
let requestQueue: Promise<unknown> = Promise.resolve()

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const run = async () => {
    const response = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })

    if (!response.ok) {
      let detail = response.statusText
      try {
        const body = (await response.json()) as { detail?: string }
        detail = body.detail ?? detail
      } catch {
        // Response had no JSON body; fall back to statusText.
      }
      throw new ApiError(response.status, detail)
    }

    if (response.status === 204) {
      return undefined as T
    }
    return (await response.json()) as T
  }

  const result = requestQueue.then(run, run)
  // Swallow rejections in the queue chain itself so one failed request
  // doesn't stall every request queued behind it; callers still see the error.
  requestQueue = result.catch(() => undefined)
  return result
}

export const api = {
  getPorts: () => request<PortListResponse>('/network/ports'),
  getStatus: () => request<StatusResponse>('/network/status'),
  connect: (body: ConnectRequest = {}) =>
    request<StatusResponse>('/network/connect', { method: 'POST', body: JSON.stringify(body) }),
  disconnect: () => request<OkResponse>('/network/disconnect', { method: 'POST' }),

  listDevices: () => request<DiscoverResponse>('/devices'),
  discoverDevices: (timeout = 5.0) =>
    request<DiscoverResponse>('/devices/discover', {
      method: 'POST',
      body: JSON.stringify({ timeout }),
    }),

  getCapabilities: (uid: string) => request<CapabilityReport>(`/devices/${uid}/capabilities`),
  getModuleSchema: (uid: string, moduleName: string) =>
    request<ModuleSchema>(`/devices/${uid}/modules/${moduleName}/schema`),
  getModuleState: (uid: string, moduleName: string) =>
    request<Record<string, unknown>>(`/devices/${uid}/modules/${moduleName}/state`),
  callMethod: (uid: string, moduleName: string, methodName: string, args: unknown[]) =>
    request<MethodCallResponse>(`/devices/${uid}/modules/${moduleName}/${methodName}`, {
      method: 'POST',
      body: JSON.stringify({ args }),
    }),
  getPersonalities: (uid: string) =>
    request<PersonalityListResponse>(`/devices/${uid}/modules/dmx_config/personalities`),
  getSensorReadings: (uid: string) =>
    request<SensorReadingsResponse>(`/devices/${uid}/modules/sensors/readings`),

  sendDmx: (body: DmxSendRequest) =>
    request<OkResponse>('/dmx/send', { method: 'POST', body: JSON.stringify(body) }),
}
