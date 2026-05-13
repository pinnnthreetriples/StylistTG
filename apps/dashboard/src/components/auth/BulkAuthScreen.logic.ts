import type {
  AuthBatchPhoneInput,
  AuthBatchSnapshot,
  AuthBatchValidation,
} from '@/lib/authBatches'

const DEFAULT_AUTH_BATCH_LIMITS = {
  max_running_commands: 2,
  max_waiting_input: 5,
  max_total_active: 6,
}

type CreateAuthBatchPayload = {
  idempotency_key: string
  label?: string | null
  items: AuthBatchPhoneInput[]
  max_running_commands: number
  max_waiting_input: number
  max_total_active: number
}

type CreateAuthBatchFn = (payload: CreateAuthBatchPayload) => Promise<AuthBatchSnapshot>
type StartAuthBatchFn = (batchId: string) => Promise<AuthBatchSnapshot>

export async function createAndStartAuthBatchFromValidation({
  createBatch,
  currentValidation,
  idempotencyKey,
  label,
  onCreatedBatch,
  startBatch,
}: {
  createBatch: CreateAuthBatchFn
  currentValidation: AuthBatchValidation
  idempotencyKey: string
  label: string
  onCreatedBatch?: (batchId: string) => void
  startBatch: StartAuthBatchFn
}): Promise<AuthBatchSnapshot> {
  const created = await createBatch({
    idempotency_key: idempotencyKey,
    label: label || null,
    items: currentValidation.valid_items.map((item) => ({ phone_number: item.phone_number, label: item.label })),
    ...DEFAULT_AUTH_BATCH_LIMITS,
  })
  onCreatedBatch?.(created.batch.id)
  return startBatch(created.batch.id)
}
