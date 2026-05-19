import type { NeuroAccountStats, NeuroCampaignStats, NeuroChannelStats } from '../types'
import { ChannelHealthBadge } from './ChannelHealthBadge'

type AnalyticsSectionProps = {
  stats: NeuroCampaignStats | null
  accounts: NeuroAccountStats[]
  channels: NeuroChannelStats[]
  loading?: boolean
  error?: string | null
}

export function AnalyticsSection({ stats, accounts, channels, loading = false, error = null }: AnalyticsSectionProps) {
  if (loading) return <section aria-label="Neuro analytics">Loading...</section>
  if (error) return <section aria-label="Neuro analytics">{error}</section>
  if (!stats) return <section aria-label="Neuro analytics">No analytics yet</section>

  return (
    <section aria-label="Neuro analytics">
      <div>
        {[
          ['Posts seen', stats.posts_seen],
          ['Generated', stats.comments_generated],
          ['Pending', stats.comments_pending],
          ['Approved', stats.comments_approved],
          ['Rejected', stats.comments_rejected],
          ['Sent', stats.comments_sent],
          ['Failed', stats.comments_failed],
          ['FloodWait', stats.flood_wait_count],
          ['Success rate', `${Math.round(stats.success_rate * 100)}%`],
          ['Approval rate', `${Math.round(stats.approval_rate * 100)}%`],
        ].map(([label, value]) => (
          <article key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </div>
      <table>
        <caption>Account performance</caption>
        <tbody>
          {accounts.map((account) => (
            <tr key={account.account_id}>
              <td>{account.account_id}</td>
              <td>{account.status ?? 'unknown'}</td>
              <td>{account.comments_sent}</td>
              <td>{account.comments_failed}</td>
              <td>{account.flood_wait_count}</td>
              <td>{Math.round(account.success_rate * 100)}%</td>
              <td>{account.cooldown_until ?? ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <table>
        <caption>Channel performance</caption>
        <tbody>
          {channels.map((channel) => (
            <tr key={channel.target_id}>
              <td>{channel.channel_ref}</td>
              <td><ChannelHealthBadge score={channel.health_score} /></td>
              <td>{channel.comments_sent}</td>
              <td>{channel.comments_failed}</td>
              <td>{channel.flood_wait_count}</td>
              <td>{channel.rule_status}</td>
              <td>{channel.last_success_at ?? ''}</td>
              <td>{channel.last_failure_at ?? ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
