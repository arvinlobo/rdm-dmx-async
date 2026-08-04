export interface SliderProps {
  label: string
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  disabled?: boolean
}

/**
 * Reusable slider for any 0-255 (or custom-range) integer field, per the
 * project convention: "all 0 to 255 values from slider".
 */
export function Slider({ label, value, onChange, min = 0, max = 255, step = 1, disabled }: SliderProps) {
  return (
    <label className="field field-slider">
      <span className="field-label">{label}</span>
      <div className="field-slider-row">
        <input
          type="range"
          aria-label={label}
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(Number(event.target.value))}
        />
        <input
          type="number"
          aria-label={`${label} value`}
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(Number(event.target.value))}
          className="field-slider-number"
        />
      </div>
    </label>
  )
}
