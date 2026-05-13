import { describe, expect, test, vi } from 'vitest'

import {
  createAndStartAuthBatchFromValidation,
} from '@/components/auth/BulkAuthScreen.logic'
import type { AuthBatchSnapshot, AuthBatchValidation } from '@/lib/authBatches'

function singlePhoneValidation(): AuthBatchValidation {
  return {
    active_batch_conflicts: [],
    duplicates: [],
    existing_accounts: [],
    invalid_items: [],
    valid_items: [{ phone_number: '+15550102000', label: null, position: 0 }],
  }
}

function snapshot(batchId: string, status: string): AuthBatchSnapshot {
  return {
    batch: {
      id: batchId,
      label: null,
      status,
      total_count: 1,
      success_count: 0,
      failed_count: 0,
      cancelled_count: 0,
      skipped_count: 0,
      max_running_commands: 2,
      max_waiting_input: 5,
      max_total_active: 6,
      created_at: '2026-05-13T00:00:00Z',
      started_at: status === 'pending' ? null : '2026-05-13T00:00:01Z',
      finished_at: null,
    },
    items: [
      {
        id: 'item-1',
        batch_id: batchId,
        account_id: 'account-1',
        phone_number: '+15550102000',
        phone_hint: '2000',
        label: null,
        position: 0,
        status: status === 'pending' ? 'queued' : 'starting',
        attempt_count: 0,
        resend_count: 0,
        code_error_count: 0,
        password_error_count: 0,
        code_expires_at: null,
        next_retry_at: null,
        error_code: null,
        error_message: null,
        updated_at: '2026-05-13T00:00:01Z',
        authorized_at: null,
      },
    ],
    server_time: '2026-05-13T00:00:01Z',
    poll_again_in_ms: 3000,
  }
}

describe('createAndStartAuthBatchFromValidation', () => {
  test('starts a one-phone add through auth batch create/start flow', async () => {
    const createBatch = vi.fn().mockResolvedValue(snapshot('batch-1', 'pending'))
    const startBatch = vi.fn().mockResolvedValue(snapshot('batch-1', 'running'))
    const onCreatedBatch = vi.fn()

    const started = await createAndStartAuthBatchFromValidation({
      createBatch,
      currentValidation: singlePhoneValidation(),
      idempotencyKey: 'batch-key-1',
      label: '',
      onCreatedBatch,
      startBatch,
    })

    expect(createBatch).toHaveBeenCalledOnce()
    expect(createBatch).toHaveBeenCalledWith({
      idempotency_key: 'batch-key-1',
      label: null,
      items: [{ phone_number: '+15550102000', label: null }],
      max_running_commands: 2,
      max_waiting_input: 5,
      max_total_active: 6,
    })
    expect(onCreatedBatch).toHaveBeenCalledWith('batch-1')
    expect(startBatch).toHaveBeenCalledOnce()
    expect(startBatch).toHaveBeenCalledWith('batch-1')
    expect(started.batch.status).toBe('running')
  })
})
