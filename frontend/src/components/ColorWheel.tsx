import { useCallback, useRef } from 'react'

export interface ColorWheelValue {
  hue: number
  saturation: number
  value: number
}

export interface ColorWheelProps {
  hue: number
  saturation: number
  value: number
  onChange: (next: ColorWheelValue) => void
  size?: number
  disabled?: boolean
}

const RING_THICKNESS = 20
const RING_GAP = 6

type DragTarget = 'disc' | 'ring'

/**
 * Circular hue/saturation picker (the disc) with an intensity dial around its
 * rim (the ring), so brightness is set from the wheel itself rather than a
 * separate slider.
 */
export function ColorWheel({ hue, saturation, value, onChange, size = 200, disabled = false }: ColorWheelProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const dragTarget = useRef<DragTarget | null>(null)

  const center = size / 2
  const discRadius = center - RING_THICKNESS - RING_GAP
  const ringInner = discRadius + RING_GAP
  const ringOuter = center

  const updateFromPoint = useCallback(
    (clientX: number, clientY: number, target: DragTarget) => {
      const el = containerRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const x = clientX - rect.left - center
      const y = clientY - rect.top - center

      if (target === 'ring') {
        let angle = Math.atan2(x, -y)
        if (angle < 0) angle += Math.PI * 2
        onChange({ hue, saturation, value: angle / (Math.PI * 2) })
      } else {
        let angle = (Math.atan2(y, x) * 180) / Math.PI
        if (angle < 0) angle += 360
        const distance = Math.hypot(x, y)
        const nextSaturation = Math.min(1, distance / discRadius)
        onChange({ hue: angle, saturation: nextSaturation, value })
      }
    },
    [center, discRadius, hue, onChange, saturation, value],
  )

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (disabled) return
    const el = containerRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const x = event.clientX - rect.left - center
    const y = event.clientY - rect.top - center
    const distance = Math.hypot(x, y)
    if (distance > ringOuter) return

    const target: DragTarget = distance >= ringInner ? 'ring' : 'disc'
    dragTarget.current = target
    el.setPointerCapture(event.pointerId)
    updateFromPoint(event.clientX, event.clientY, target)
  }

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!dragTarget.current) return
    updateFromPoint(event.clientX, event.clientY, dragTarget.current)
  }

  const handlePointerUp = () => {
    dragTarget.current = null
  }

  const discAngle = (hue * Math.PI) / 180
  const discHandleRadius = saturation * discRadius
  const discHandleX = center + Math.cos(discAngle) * discHandleRadius
  const discHandleY = center + Math.sin(discAngle) * discHandleRadius

  const ringAngle = value * Math.PI * 2
  const ringHandleRadius = (ringInner + ringOuter) / 2
  const ringHandleX = center + Math.sin(ringAngle) * ringHandleRadius
  const ringHandleY = center - Math.cos(ringAngle) * ringHandleRadius

  return (
    <div
      ref={containerRef}
      className={`color-wheel${disabled ? ' color-wheel-disabled' : ''}`}
      style={{ width: size, height: size }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      role="group"
      aria-label="Color and intensity"
    >
      <div className="color-wheel-ring" />
      <div className="color-wheel-disc" style={{ width: discRadius * 2, height: discRadius * 2 }} />
      <div
        className="color-wheel-value-overlay"
        style={{ width: discRadius * 2, height: discRadius * 2, opacity: 1 - value }}
      />
      <div
        className="color-wheel-handle color-wheel-handle-ring"
        style={{ left: ringHandleX, top: ringHandleY }}
        title={`Intensity: ${Math.round(value * 255)}`}
      />
      <div
        className="color-wheel-handle color-wheel-handle-disc"
        style={{ left: discHandleX, top: discHandleY }}
        title={`Hue: ${Math.round(hue)}°, Saturation: ${Math.round(saturation * 100)}%`}
      />
    </div>
  )
}
