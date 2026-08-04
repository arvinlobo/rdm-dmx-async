export interface CheckboxProps {
  label: string
  checked: boolean
  onChange: (value: boolean) => void
  disabled?: boolean
}

/** Reusable checkbox for any boolean field. */
export function Checkbox({ label, checked, onChange, disabled }: CheckboxProps) {
  return (
    <label className="field field-checkbox">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="field-label">{label}</span>
    </label>
  )
}
