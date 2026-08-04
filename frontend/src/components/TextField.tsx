export interface TextFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  maxLength?: number
}

/** Reusable text input for any string field, per the project convention: "all string fields from input strings". */
export function TextField({ label, value, onChange, disabled, maxLength }: TextFieldProps) {
  return (
    <label className="field field-text">
      <span className="field-label">{label}</span>
      <input
        type="text"
        value={value}
        maxLength={maxLength}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}
