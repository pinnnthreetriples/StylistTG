import { Badge } from '@stylisttg/ui'

export type GgrBucket = 'strong' | 'medium' | 'weak'

const BUCKET_CONFIG: Record<GgrBucket, { tone: 'green' | 'amber' | 'red'; label: string }> = {
  strong: { tone: 'green', label: 'Сильный' },
  medium: { tone: 'amber', label: 'Средний' },
  weak: { tone: 'red', label: 'Слабый' },
}

export function GGRBadge({
  score,
  bucket,
}: {
  score: number
  bucket: GgrBucket
}) {
  const config = BUCKET_CONFIG[bucket]
  return (
    <Badge tone={config.tone} title={`GGR: ${score.toFixed(1)} — ${config.label}`}>
      {score.toFixed(1)}
    </Badge>
  )
}
