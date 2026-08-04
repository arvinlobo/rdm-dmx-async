import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import { ColorWheel } from './ColorWheel'
import { Slider } from './Slider'
import { hsvToRgb } from '../utils/color'
import { resolveRgbwOffsets, resolveTwOffsets } from '../utils/dmxChannelMapping'

export interface DmxSlotPanelProps {
  uid?: string | null
  defaultStartAddress?: number
}

type Mode = 'single' | 'rgbw' | 'tw'

const UNIVERSE_SIZE = 512
const SEND_DEBOUNCE_MS = 150

/**
 * Raw DMX slot control, independent of RDM device selection: a single level
 * applied to the whole 512-channel universe, an RGBW block driven by a color
 * wheel (hue/saturation from the disc, intensity from the ring), or a
 * tunable-white warm/cool block.
 *
 * When a device is selected its real DMX slot descriptions are used to find
 * the actual R/G/B/W (or warm/cool) channel offsets; otherwise the classic
 * R,G,B,W repeating pattern is tiled across all 512 channels.
 *
 * Sends automatically (debounced) as controls move - no explicit Set button.
 */
export function DmxSlotPanel({ uid = null, defaultStartAddress = 1 }: DmxSlotPanelProps) {
  const [mode, setMode] = useState<Mode>('single')
  const [singleValue, setSingleValue] = useState(0)
  const [startAddress, setStartAddress] = useState(defaultStartAddress)
  const [hue, setHue] = useState(0)
  const [saturation, setSaturation] = useState(1)
  const [intensity, setIntensity] = useState(1)
  const [white, setWhite] = useState(0)
  const [warm, setWarm] = useState(0)
  const [cool, setCool] = useState(0)
  const [slotDescriptions, setSlotDescriptions] = useState<string[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const timeoutRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!uid) {
      setSlotDescriptions(null)
      return
    }
    let cancelled = false
    api
      .getModuleState(uid, 'slots')
      .then((state) => {
        if (cancelled) return
        const descriptions = state.get_all_slot_descriptions
        setSlotDescriptions(Array.isArray(descriptions) ? (descriptions as string[]) : null)
      })
      .catch(() => {
        if (!cancelled) setSlotDescriptions(null)
      })
    return () => {
      cancelled = true
    }
  }, [uid])

  useEffect(() => {
    if (timeoutRef.current !== undefined) window.clearTimeout(timeoutRef.current)
    timeoutRef.current = window.setTimeout(() => {
      const channels = new Array<number>(UNIVERSE_SIZE).fill(0)

      if (mode === 'single') {
        channels.fill(singleValue)
      } else if (mode === 'rgbw') {
        const { r, g, b } = hsvToRgb(hue, saturation, intensity)
        for (const group of resolveRgbwOffsets(slotDescriptions, startAddress)) {
          channels[group.red] = r
          channels[group.green] = g
          channels[group.blue] = b
          if (group.white >= 0) channels[group.white] = white
        }
      } else {
        for (const group of resolveTwOffsets(slotDescriptions, startAddress)) {
          channels[group.warm] = warm
          channels[group.cool] = cool
        }
      }

      api
        .sendDmx({ channels })
        .then(() => setError(null))
        .catch((err: unknown) => setError(err instanceof ApiError ? err.message : 'Failed to send DMX'))
    }, SEND_DEBOUNCE_MS)
    return () => {
      if (timeoutRef.current !== undefined) window.clearTimeout(timeoutRef.current)
    }
  }, [mode, singleValue, startAddress, hue, saturation, intensity, white, warm, cool, slotDescriptions])

  const { r, g, b } = hsvToRgb(hue, saturation, intensity)
  const usingRealSlots = slotDescriptions !== null && slotDescriptions.length > 0

  return (
    <section className="dmx-slot-panel">
      <h3>DMX Output</h3>
      <div className="segmented" role="group" aria-label="DMX Mode">
        <button
          type="button"
          className={`segmented-option${mode === 'single' ? ' segmented-option-active' : ''}`}
          aria-pressed={mode === 'single'}
          onClick={() => setMode('single')}
        >
          Single channel
        </button>
        <button
          type="button"
          className={`segmented-option${mode === 'rgbw' ? ' segmented-option-active' : ''}`}
          aria-pressed={mode === 'rgbw'}
          onClick={() => setMode('rgbw')}
        >
          RGBW
        </button>
        <button
          type="button"
          className={`segmented-option${mode === 'tw' ? ' segmented-option-active' : ''}`}
          aria-pressed={mode === 'tw'}
          onClick={() => setMode('tw')}
        >
          Tunable White
        </button>
      </div>

      {mode === 'single' && (
        <Slider label="Level (all 512 channels)" value={singleValue} onChange={setSingleValue} min={0} max={255} />
      )}

      {mode === 'rgbw' && (
        <div className="dmx-slot-panel-grid">
          <Slider label="Start Address" value={startAddress} onChange={setStartAddress} min={1} max={509} />
          <div className="color-wheel-row">
            <ColorWheel
              hue={hue}
              saturation={saturation}
              value={intensity}
              onChange={(next) => {
                setHue(next.hue)
                setSaturation(next.saturation)
                setIntensity(next.value)
              }}
            />
            <div className="color-wheel-readout" style={{ background: `rgb(${r}, ${g}, ${b})` }}>
              <span>R {r}</span>
              <span>G {g}</span>
              <span>B {b}</span>
            </div>
          </div>
          <Slider label="White" value={white} onChange={setWhite} min={0} max={255} />
        </div>
      )}

      {mode === 'tw' && (
        <div className="dmx-slot-panel-grid">
          <Slider label="Start Address" value={startAddress} onChange={setStartAddress} min={1} max={509} />
          <Slider label="Warm White" value={warm} onChange={setWarm} min={0} max={255} />
          <Slider label="Cool White" value={cool} onChange={setCool} min={0} max={255} />
        </div>
      )}

      {mode !== 'single' && (
        <p className="dmx-slot-panel-hint">
          {usingRealSlots
            ? "Using this device's real DMX slot layout."
            : 'No slot description available - using the default repeating pattern across all 512 channels.'}
        </p>
      )}
      {error && <p className="dmx-slot-panel-error">{error}</p>}
    </section>
  )
}
