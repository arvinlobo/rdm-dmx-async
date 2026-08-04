/** TypeScript types mirroring the backend's Pydantic schemas (api/schemas.py). */

export interface PortListResponse {
  ports: string[]
}

export interface ConnectRequest {
  port?: string | null
  interface_type?: string
}

export interface StatusResponse {
  connected: boolean
  port: string | null
  device_count: number
}

export interface DeviceSummary {
  uid: string
  manufacturer: string
  device_label: string
  model: string
  dmx_start_address: number
  dmx_personality: number
  dmx_footprint: number
}

export interface DiscoverResponse {
  devices: DeviceSummary[]
}

export interface OkResponse {
  success: boolean
}

/** Per-module PID coverage, as reported by `RdmDevice.get_api_support_details()`. */
export interface ModuleSupport {
  supported: boolean
  pids: number[]
  supported_pids: number[]
  missing_pids: number[]
  coverage: number
}

export interface CapabilityReport {
  modules: Record<string, ModuleSupport>
}

export type ParamKind = 'int' | 'str' | 'bool' | 'enum' | 'unknown'

export interface ModuleParamSpec {
  name: string
  kind: ParamKind
  required: boolean
  default: boolean | number | string | null
  min: number | null
  max: number | null
}

/** A callable method on a device API module (getter or action). */
export interface ModuleMethodSpec {
  name: string
  is_getter: boolean
  params: ModuleParamSpec[]
  supported: boolean
}

export interface ModuleSchema {
  module: string
  methods: ModuleMethodSpec[]
}

export type MethodValue = boolean | number | string | null

export interface MethodCallResponse {
  result: MethodValue | MethodValue[] | Record<string, unknown> | null
}

export interface PersonalityOption {
  personality: number
  footprint: number
  description: string
}

export interface PersonalityListResponse {
  current: number | null
  options: PersonalityOption[]
}

/** A sensor's live value merged with its static definition, for display. */
export interface SensorReading {
  sensor_number: number
  description: string
  unit: number
  prefix: number
  present_value: number | null
  lowest: number | null
  highest: number | null
  recorded: number | null
  range_min: number
  range_max: number
  normal_min: number
  normal_max: number
  supports_recording: boolean
}

export interface SensorReadingsResponse {
  sensors: SensorReading[]
}

export interface DmxSendRequest {
  channels: number[]
  port?: number
}

/** Human-friendly labels for the 16 device API modules (matches API_PID_MAPPING keys). */
export const MODULE_LABELS: Record<string, string> = {
  device_label: 'Device Label',
  dmx_config: 'DMX Configuration',
  control: 'Device Control',
  sensors: 'Sensors',
  sensor_definitions: 'Sensor Definitions',
  maintenance: 'Maintenance',
  info: 'Device Info',
  slots: 'DMX Slots',
  modes: 'DMX Modes',
  lamp: 'Lamp Control',
  display: 'Display Settings',
  position: 'Position Configuration',
  power: 'Power Control',
  self_test: 'Self Test',
  presets: 'Preset Control',
  system: 'System Info',
  proxy: 'Proxy',
}
