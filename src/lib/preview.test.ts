import { describe, expect, it } from 'vitest'

import { buildPreviewStatus } from '@/lib/preview'
import type { ProfilePreview } from '@/lib/api'

const basePreview = {
  can_create_job: true,
  blocking_errors: [],
  warnings: [],
  normalized_payload: {},
  execution_intent_hash: 'hash',
  plan_json_snapshot: { steps: [] },
  steps: [],
  requires_execution_usable: true,
  dedup_would_block: false,
  dedup_blocked_by_job_id: null,
} satisfies ProfilePreview

describe('buildPreviewStatus', () => {
  it('returns empty state before preview is loaded', () => {
    expect(buildPreviewStatus(null)).toEqual({
      kind: 'empty',
      title: 'Предпросмотр не готов',
      description: 'Измените профиль, чтобы увидеть план применения.',
      items: [],
    })
  })

  it('explains blocked previews before create job', () => {
    expect(
      buildPreviewStatus({
        ...basePreview,
        can_create_job: false,
        blocking_errors: ['profile job cooldown active'],
      }),
    ).toEqual({
      kind: 'blocked',
      title: 'Запуск заблокирован',
      description: 'Нужно устранить блокирующие условия перед созданием задачи.',
      items: ['Сработала пауза между запусками задач'],
    })
  })

  it('labels disabled live story publishing in Russian', () => {
    expect(
      buildPreviewStatus({
        ...basePreview,
        can_create_job: false,
        blocking_errors: ['stories live TDLib execution is not enabled'],
      }).items,
    ).toEqual(['Публикация историй через TDLib пока выключена'])
  })

  it('labels disabled stories in Russian', () => {
    expect(
      buildPreviewStatus({
        ...basePreview,
        can_create_job: false,
        blocking_errors: ['stories are disabled'],
      }).items,
    ).toEqual(['Истории выключены в настройках приложения'])
  })

  it('explains deduplicated previews', () => {
    expect(
      buildPreviewStatus({
        ...basePreview,
        dedup_would_block: true,
        dedup_blocked_by_job_id: 'job-1',
      }),
    ).toEqual({
      kind: 'dedup',
      title: 'Такая задача уже есть',
      description: 'Повторный запуск с тем же набором изменений не нужен.',
      items: ['job-1'],
    })
  })

  it('reports ready previews with operation count', () => {
    expect(
      buildPreviewStatus({
        ...basePreview,
        steps: [
          { step_key: 'set_name', step_type: 'set_name', order: 0, required: true, idempotency_class: 'idempotent', payload: {} },
          { step_key: 'set_bio', step_type: 'set_bio', order: 1, required: true, idempotency_class: 'idempotent', payload: {} },
        ],
      }),
    ).toEqual({
      kind: 'ready',
      title: 'Готово к запуску',
      description: 'Будет применено 2 операции.',
      items: [],
    })
  })
})
