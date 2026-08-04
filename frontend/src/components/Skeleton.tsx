export interface SkeletonProps {
  lines?: number
  height?: number
}

/** Shimmering placeholder shown in place of a module's state/actions while its schema loads. */
export function Skeleton({ lines = 3, height = 16 }: SkeletonProps) {
  return (
    <div className="skeleton-group" aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <div key={index} className="skeleton-line" style={{ height }} />
      ))}
    </div>
  )
}
