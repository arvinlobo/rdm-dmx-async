/** Thin fetch wrapper for the rdm-dmx-async REST API (see api/app.py). */

import type {
  CapabilityReport,
  ConnectRequest,
  DiscoverResponse,
  DmxSendRequest,
  InterfaceTypeListResponse,
  MethodCallResponse,
  ModuleSchema,
  OkResponse,
  PersonalityListResponse,
  PortListResponse,
  SensorReadingsResponse,
  StatusResponse,
  SupportedPidListResponse,
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

const personalitiesCache = new Map<string, Promise<PersonalityListResponse>>()
const supportedPidsCache = new Map<string, Promise<SupportedPidListResponse>>()

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
  getInterfaceTypes: () => request<InterfaceTypeListResponse>('/network/interface-types'),
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
  getPersonalities: (uid: string) => {
    // Each personality's description is its own RDM round trip (PID DMX_PERSONALITY_DESCRIPTION
    // has no "get all" form), so this list is expensive - up to ~20 RDM transactions. The set of
    // descriptions is static per device, so cache per uid instead of refetching on every mount
    // (e.g. every `set_personality`/`get_personality_description` form remounting after a run).
    const cached = personalitiesCache.get(uid)
    if (cached) return cached
    const result = request<PersonalityListResponse>(`/devices/${uid}/modules/dmx_config/personalities`)
    personalitiesCache.set(uid, result)
    result.catch(() => personalitiesCache.delete(uid))
    return result
  },
  getSensorReadings: (uid: string) =>
    request<SensorReadingsResponse>(`/devices/${uid}/modules/sensors/readings`),
  getSupportedPids: (uid: string) => {
    // Same static-per-device, expensive-to-refetch reasoning as getPersonalities above.
    const cached = supportedPidsCache.get(uid)
    if (cached) return cached
    const result = request<SupportedPidListResponse>(`/devices/${uid}/modules/system/supported-pids`)
    supportedPidsCache.set(uid, result)
    result.catch(() => supportedPidsCache.delete(uid))
    return result
  },

  sendDmx: (body: DmxSendRequest) =>
    request<OkResponse>('/dmx/send', { method: 'POST', body: JSON.stringify(body) }),
}
