import { Checkbox } from './Checkbox'
import { Slider } from './Slider'
import { TextField } from './TextField'

export interface ReadOnlyFieldProps {
  name: string
  value: unknown
}

/** Renders a getter's current value using the same reusable field components, disabled. */
export function ReadOnlyField({ name, value }: ReadOnlyFieldProps) {
  if (typeof value === 'number') {
    return <Slider label={name} value={value} onChange={() => {}} disabled />
  }
  if (typeof value === 'boolean') {
    return <Checkbox label={name} checked={value} onChange={() => {}} disabled />
  }
  if (typeof value === 'string') {
    return <TextField label={name} value={value} onChange={() => {}} disabled />
  }
  return (
    <div className="field field-readonly">
      <span className="field-label">{name}</span>
      <span className="field-value">
        {value === null || value === undefined ? '—' : JSON.stringify(value)}
      </span>
    </div>
  )
}
