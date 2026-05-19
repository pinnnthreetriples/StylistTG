import type { FormEvent } from 'react'

import type { NeuroChannelRule, NeuroChannelRuleCreate } from '../types'

type ChannelRulesSectionProps = {
  rules: NeuroChannelRule[]
  loading?: boolean
  error?: string | null
  onCreate?: (payload: NeuroChannelRuleCreate) => void
  onDelete?: (ruleId: string) => void
}

export function ChannelRulesSection({ rules, loading = false, error = null, onCreate, onDelete }: ChannelRulesSectionProps) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    onCreate?.({
      target_ref: String(form.get('target_ref') ?? ''),
      rule_type: String(form.get('rule_type') ?? 'blacklist') as NeuroChannelRuleCreate['rule_type'],
      reason: String(form.get('reason') ?? '') || undefined,
    })
    event.currentTarget.reset()
  }

  if (loading) return <section aria-label="Neuro channel rules">Loading...</section>
  if (error) return <section aria-label="Neuro channel rules">{error}</section>

  return (
    <section aria-label="Neuro channel rules">
      <form onSubmit={submit}>
        <input name="target_ref" aria-label="Target ref" />
        <select name="rule_type" aria-label="Rule type">
          <option value="blacklist">Blacklist</option>
          <option value="whitelist">Whitelist</option>
        </select>
        <input name="reason" aria-label="Reason" />
        <button type="submit">Create</button>
      </form>
      {rules.length === 0 ? <p>No channel rules yet</p> : null}
      <ul>
        {rules.map((rule) => (
          <li key={rule.id}>
            <span>{rule.target_ref}</span>
            <span>{rule.rule_type}</span>
            {rule.rule_type.startsWith('auto_') ? <span>suggested</span> : null}
            <button type="button" onClick={() => onDelete?.(rule.id)}>Delete</button>
          </li>
        ))}
      </ul>
    </section>
  )
}
