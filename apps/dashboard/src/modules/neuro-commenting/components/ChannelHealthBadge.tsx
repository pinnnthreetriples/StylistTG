type ChannelHealthBadgeProps = {
  score: number
}

export function ChannelHealthBadge({ score }: ChannelHealthBadgeProps) {
  const clamped = Math.max(0, Math.min(1, score))
  const label = `${Math.round(clamped * 100)}%`
  const tone = clamped >= 0.75 ? 'good' : clamped >= 0.4 ? 'warn' : 'bad'

  return <span data-tone={tone}>{label}</span>
}
