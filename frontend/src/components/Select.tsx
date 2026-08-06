export interface SelectProps {
  label: string
  value: string
  options: string[]
  onChange: (value: string) => void
  disabled?: boolean
}

/** Static dropdown for a fixed set of string choices (e.g. a Literal[...]-typed param). */
export function Select({ label, value, options, onChange, disabled }: SelectProps) {
  return (
    <label className="field field-select">
      <span className="field-label">{label}</span>
      <select
        aria-label={label}
        title={value}
        value={value}
        disabled={disabled || options.length === 0}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  )
}
