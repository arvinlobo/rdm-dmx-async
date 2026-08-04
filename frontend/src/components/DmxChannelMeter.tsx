export interface ChannelMeterEntry {
  label: string
  value: number
  color?: string
}

export interface DmxChannelMeterProps {
  entries: ChannelMeterEntry[]
}

/** Compact live bar-per-channel readout for the DMX values currently being sent. */
export function DmxChannelMeter({ entries }: DmxChannelMeterProps) {
  return (
    <div className="channel-meter" role="group" aria-label="Live channel levels">
      {entries.map((entry) => (
        <div key={entry.label} className="channel-meter-bar-wrap">
          <div className="channel-meter-track">
            <div
              className="channel-meter-fill"
              style={{ height: `${(entry.value / 255) * 100}%`, background: entry.color }}
            />
          </div>
          <span className="channel-meter-value">{entry.value}</span>
          <span className="channel-meter-label">{entry.label}</span>
        </div>
      ))}
    </div>
  )
}
