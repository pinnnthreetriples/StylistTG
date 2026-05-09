import { describe, expect, test } from 'vitest'

import {
  WARMUP_EVENT_LABELS,
  WARMUP_EXECUTION_MODE_LABELS,
  WARMUP_PRESET_LABELS,
  WARMUP_RISK_LEVEL_LABELS,
  WARMUP_RISK_TONES,
  WARMUP_SKIP_REASON_LABELS,
  formatWarmupEventPayload,
  warmupProgressPercent,
} from './labels'
import type { WarmupEvent } from './types'

describe('warmup label helpers', () => {
  test('preset labels are localized for all known kinds', () => {
    expect(WARMUP_PRESET_LABELS.express).toBe('Экспресс')
    expect(WARMUP_PRESET_LABELS.standard).toBe('Стандарт')
    expect(WARMUP_PRESET_LABELS.hardened).toBe('Усиленный')
    expect(WARMUP_PRESET_LABELS.custom).toBe('Кастомный')
  })

  test('execution mode labels surface a safe-mode wording for dry_run', () => {
    expect(WARMUP_EXECUTION_MODE_LABELS.dry_run).toMatch(/безопасный/i)
    expect(WARMUP_EXECUTION_MODE_LABELS.shadow).toMatch(/симуляц/i)
    expect(WARMUP_EXECUTION_MODE_LABELS.network).toBeDefined()
    expect(WARMUP_EXECUTION_MODE_LABELS.advanced).toBeDefined()
    // network and advanced must not promise anti-ban or guarantee safety
    expect(WARMUP_EXECUTION_MODE_LABELS.network).not.toMatch(/гарант/i)
    expect(WARMUP_EXECUTION_MODE_LABELS.advanced).not.toMatch(/гарант/i)
  })

  test('risk levels map to a non-neutral tone for medium/high', () => {
    expect(WARMUP_RISK_LEVEL_LABELS.low).toBeDefined()
    expect(WARMUP_RISK_TONES.low).toBe('green')
    expect(WARMUP_RISK_TONES.medium).toBe('amber')
    expect(WARMUP_RISK_TONES.high).toBe('red')
  })

  test('warmupProgressPercent uses the strategy duration, not 14 days', () => {
    expect(warmupProgressPercent(0, 7)).toBe(0)
    expect(warmupProgressPercent(7, 7)).toBe(100)
    expect(warmupProgressPercent(7, 14)).toBe(50)
    expect(warmupProgressPercent(21, 21)).toBe(100)
    // Defends against divide-by-zero from a malformed strategy.
    expect(warmupProgressPercent(0, 0)).toBe(0)
  })

  test('formatWarmupEventPayload describes Phase 1 events explicitly', () => {
    const simulated: WarmupEvent = {
      id: 'evt-1',
      event_type: 'session_action_simulated',
      payload: { day: 4, action_type: 'feed_read', simulated: true },
      created_at: '2026-06-01T12:00:00Z',
    }
    expect(formatWarmupEventPayload(simulated)).toContain('feed_read')
    expect(formatWarmupEventPayload(simulated)).toMatch(/симулир/i)
    expect(formatWarmupEventPayload(simulated)).toMatch(/без|никаких/i)

    const opened: WarmupEvent = {
      id: 'evt-2',
      event_type: 'micro_session_window_opened',
      payload: { day: 4 },
      created_at: '2026-06-01T12:00:00Z',
    }
    expect(formatWarmupEventPayload(opened)).toMatch(/окно/i)
    expect(formatWarmupEventPayload(opened)).toContain('4')

    const claimed: WarmupEvent = {
      id: 'evt-3',
      event_type: 'isolation_claimed',
      payload: { held_by: 'warmup:abc', execution_mode: 'shadow' },
      created_at: '2026-06-01T12:00:00Z',
    }
    expect(formatWarmupEventPayload(claimed)).toMatch(/изолир/i)
  })

  test('Phase 3+4: session_action_executed describes live action with mode', () => {
    const executed: WarmupEvent = {
      id: 'evt-exec-1',
      event_type: 'session_action_executed',
      payload: { day: 3, action_type: 'join_chat', execution_mode: 'network', simulated: false },
      created_at: '2026-06-02T10:00:00Z',
    }
    expect(formatWarmupEventPayload(executed)).toContain('join_chat')
    expect(formatWarmupEventPayload(executed)).toMatch(/network|сетевой/i)
    expect(formatWarmupEventPayload(executed)).toContain('3')
    // event label must be defined and not raw code
    expect(WARMUP_EVENT_LABELS['session_action_executed']).toBeDefined()
    expect(WARMUP_EVENT_LABELS['session_action_executed']).not.toBe('session_action_executed')
  })

  test('Phase 3+4: task_skipped with known reason codes produce human text', () => {
    const skipReasons = [
      'quiet_hours',
      'passive_disabled',
      'write_action_not_enabled',
      'no_target_channels_configured',
      'no_eligible_trusted_peers',
      'text_provider_unavailable',
    ] as const

    for (const reason of skipReasons) {
      expect(WARMUP_SKIP_REASON_LABELS[reason]).toBeDefined()
      // Must not be just the raw code
      expect(WARMUP_SKIP_REASON_LABELS[reason]).not.toBe(reason)
    }

    const skippedEvent: WarmupEvent = {
      id: 'evt-skip-1',
      event_type: 'task_skipped',
      payload: { day: 2, action_type: 'p2p_send', reason: 'no_eligible_trusted_peers' },
      created_at: '2026-06-02T11:00:00Z',
    }
    const label = formatWarmupEventPayload(skippedEvent)
    expect(label).toMatch(/пропущен/i)
    expect(label).toContain('p2p_send')
    // Must show human text, not raw code
    expect(label).not.toContain('no_eligible_trusted_peers')
    expect(label).toContain(WARMUP_SKIP_REASON_LABELS['no_eligible_trusted_peers'])
  })

  test('Phase 3+4: task_failed event shows action and error code', () => {
    const failed: WarmupEvent = {
      id: 'evt-fail-1',
      event_type: 'task_failed',
      payload: {
        day: 5,
        action_type: 'join_chat',
        execution_mode: 'network',
        status: 'flood_wait',
        error_code: 'FLOOD_WAIT_60',
      },
      created_at: '2026-06-02T12:00:00Z',
    }
    const label = formatWarmupEventPayload(failed)
    expect(label).toContain('join_chat')
    expect(label).toContain('FLOOD_WAIT_60')
    expect(label).toContain('5')
    expect(WARMUP_EVENT_LABELS['task_failed']).toBeDefined()
    expect(WARMUP_EVENT_LABELS['task_failed']).not.toBe('task_failed')
  })

  test('Phase 4: p2p_contact_recorded event is human-readable', () => {
    const p2p: WarmupEvent = {
      id: 'evt-p2p-1',
      event_type: 'p2p_contact_recorded',
      payload: { day: 7, receiver_account_id: 'acc-xyz', receiver_contacts: 1 },
      created_at: '2026-06-03T09:00:00Z',
    }
    const label = formatWarmupEventPayload(p2p)
    expect(label).toMatch(/p2p|контакт/i)
    expect(label).toContain('7')
    expect(WARMUP_EVENT_LABELS['p2p_contact_recorded']).toBeDefined()
    expect(WARMUP_EVENT_LABELS['p2p_contact_recorded']).not.toBe('p2p_contact_recorded')
  })

  test('Phase 4: p2p_contact_recording_failed event is human-readable', () => {
    const p2pFail: WarmupEvent = {
      id: 'evt-p2p-fail-1',
      event_type: 'p2p_contact_recording_failed',
      payload: { day: 7, receiver_account_id: 'acc-xyz', error: 'receiver is not in trusted-peer pool' },
      created_at: '2026-06-03T09:00:00Z',
    }
    const label = formatWarmupEventPayload(p2pFail)
    expect(label).toMatch(/p2p|контакт/i)
    expect(label).toContain('receiver is not in trusted-peer pool')
    expect(WARMUP_EVENT_LABELS['p2p_contact_recording_failed']).toBeDefined()
  })

  test('circuit_breaker_tripped event shows failure count and is human-readable', () => {
    const cbTripped: WarmupEvent = {
      id: 'evt-cb-1',
      event_type: 'circuit_breaker_tripped',
      payload: { consecutive_failures: 5, max_failures: 5 },
      created_at: '2026-06-03T10:00:00Z',
    }
    const label = formatWarmupEventPayload(cbTripped)
    expect(label).toContain('5')
    expect(label).toMatch(/пауз|остановл/i)
    // Both event name variants map to same human label
    expect(WARMUP_EVENT_LABELS['circuit_breaker_tripped']).toBe(WARMUP_EVENT_LABELS['circuit_breaker_triggered'])
  })

  test('unknown event types fall back to JSON payload (not raw code as label)', () => {
    const unknown: WarmupEvent = {
      id: 'evt-unknown-1',
      event_type: 'some_future_event_type',
      payload: { foo: 'bar' },
      created_at: '2026-06-04T00:00:00Z',
    }
    // formatWarmupEventPayload falls back to JSON — not an empty string
    const payloadText = formatWarmupEventPayload(unknown)
    expect(payloadText).toContain('bar')
    // WarmupEventLog uses label fallback: shows raw event_type when label is missing
    expect(WARMUP_EVENT_LABELS['some_future_event_type']).toBeUndefined()
  })
})
