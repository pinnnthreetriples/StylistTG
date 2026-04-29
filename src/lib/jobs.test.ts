import { describe, expect, it } from 'vitest'

import {
  buildJobDisplayItems,
  buildJobProgressSummary,
  buildJobResultSummary,
  buildJobStepItems,
  shouldResetDraftAfterJobState,
} from '@/lib/jobs'
import type { JobDetail, JobStep, ProfilePreview } from '@/lib/api'

describe('buildJobStepItems', () => {
  it('merges preview plan and persisted step results into user-facing items', () => {
    const preview = {
      steps: [
        { step_key: 'set_name', step_type: 'set_name', order: 0, required: true, idempotency_class: 'idempotent', payload: {} },
        { step_key: 'set_bio', step_type: 'set_bio', order: 1, required: true, idempotency_class: 'idempotent', payload: {} },
        { step_key: 'set_username', step_type: 'set_username', order: 2, required: true, idempotency_class: 'idempotent', payload: {} },
        { step_key: 'add_profile_audio', step_type: 'add_profile_audio', order: 3, required: true, idempotency_class: 'idempotent', payload: {} },
      ],
    } as ProfilePreview
    const steps: JobStep[] = [
      {
        step_key: 'set_name',
        step_type: 'set_name',
        status: 'succeeded',
        verification_attempted: false,
        verification_result: null,
        uncertain_reason: null,
        error_code: null,
        error_class: null,
        started_at: '2026-04-24T00:00:00Z',
        finished_at: '2026-04-24T00:00:01Z',
      },
      {
        step_key: 'set_username',
        step_type: 'set_username',
        status: 'uncertain',
        verification_attempted: true,
        verification_result: { matched: false },
        uncertain_reason: 'verify mismatch',
        error_code: 'USERNAME_AMBIGUOUS',
        error_class: 'verification',
        started_at: '2026-04-24T00:00:02Z',
        finished_at: '2026-04-24T00:00:03Z',
      },
    ]

    expect(buildJobStepItems(steps, preview)).toEqual([
      {
        key: 'set_name',
        title: 'Имя',
        status: 'succeeded',
        statusLabel: 'Готово',
        detail: 'Применено',
        tone: 'success',
      },
      {
        key: 'set_bio',
        title: 'Описание',
        status: 'planned',
        statusLabel: 'Запланировано',
        detail: 'Ожидает запуска',
        tone: 'neutral',
      },
      {
        key: 'set_username',
        title: 'Юзернейм',
        status: 'uncertain',
        statusLabel: 'Проверить',
        detail: 'Юзернейм требует проверки',
        tone: 'warning',
      },
      {
        key: 'add_profile_audio',
        title: 'Музыка профиля',
        status: 'planned',
        statusLabel: 'Запланировано',
        detail: 'Ожидает запуска',
        tone: 'neutral',
      },
    ])
  })

  it('uses TDLib payload message when a generic TDLib error hides the concrete reason', () => {
    const steps: JobStep[] = [
      {
        step_key: 'set_username',
        step_type: 'set_username',
        status: 'failed',
        verification_attempted: false,
        verification_result: null,
        uncertain_reason: null,
        error_code: 'tdlib_error',
        error_class: 'TdlibProfileQueryError',
        result_payload_json: { message: 'USERNAME_PURCHASE_AVAILABLE' },
        started_at: null,
        finished_at: null,
      },
    ]

    expect(buildJobStepItems(steps, null)[0]).toMatchObject({
      title: 'Юзернейм',
      detail: 'Юзернейм доступен только через покупку',
      tone: 'error',
    })
  })

  it('explains the old unsupported TDLib upload method error for profile audio', () => {
    const steps: JobStep[] = [
      {
        step_key: 'upload_profile_audio',
        step_type: 'upload_profile_audio',
        status: 'failed',
        verification_attempted: false,
        verification_result: null,
        uncertain_reason: null,
        error_code: 'tdlib_error',
        error_class: 'TdlibProfileQueryError',
        result_payload_json: {
          message: 'Failed to parse JSON object as TDLib request: Unknown class "uploadFile"',
        },
        started_at: null,
        finished_at: null,
      },
    ]

    expect(buildJobStepItems(steps, null)[0]).toMatchObject({
      title: 'Загрузка музыки',
      detail: 'Использовался неподдерживаемый способ загрузки музыки',
      tone: 'error',
    })
  })

  it('shows clear story and profile audio failure labels from backend error codes', () => {
    const steps: JobStep[] = [
      {
        step_key: 'add_profile_audio',
        step_type: 'add_profile_audio',
        status: 'failed',
        verification_attempted: false,
        verification_result: null,
        uncertain_reason: null,
        error_code: 'PROFILE_AUDIO_FILE_ID_MISSING',
        error_class: 'TdlibProfileQueryError',
        started_at: null,
        finished_at: null,
      },
      {
        step_key: 'story_1_post',
        step_type: 'post_story_image',
        status: 'failed',
        verification_attempted: false,
        verification_result: null,
        uncertain_reason: null,
        error_code: 'STORY_POST_FAILED',
        error_class: 'TdlibProfileQueryError',
        started_at: null,
        finished_at: null,
      },
    ]

    expect(buildJobStepItems(steps, null).map((item) => item.detail)).toEqual([
      'Telegram не вернул файл музыки',
      'Telegram не опубликовал историю',
    ])
  })

  it('specializes generic TDLib profile audio add and remove failures', () => {
    const steps: JobStep[] = [
      {
        step_key: 'add_profile_audio',
        step_type: 'add_profile_audio',
        status: 'failed',
        verification_attempted: false,
        verification_result: null,
        uncertain_reason: null,
        error_code: 'tdlib_profile_step_failed',
        error_class: 'TdlibProfileQueryError',
        started_at: null,
        finished_at: null,
      },
      {
        step_key: 'remove_profile_audio',
        step_type: 'remove_profile_audio',
        status: 'failed',
        verification_attempted: false,
        verification_result: null,
        uncertain_reason: null,
        error_code: 'tdlib_profile_step_failed',
        error_class: 'TdlibProfileQueryError',
        started_at: null,
        finished_at: null,
      },
    ]

    expect(buildJobStepItems(steps, null).map((item) => item.detail)).toEqual([
      'Telegram не добавил музыку в профиль',
      'Telegram не удалил музыку из профиля',
    ])
  })

  it('formats dynamic story step keys without leaking technical names', () => {
    const preview = {
      steps: [
        { step_key: 'story_1_validate_capabilities', step_type: 'validate_story_capabilities', order: 0, required: true, idempotency_class: 'idempotent', payload: {} },
        { step_key: 'story_1_prepare_media', step_type: 'prepare_story_media', order: 1, required: true, idempotency_class: 'idempotent', payload: {} },
        { step_key: 'story_1_post', step_type: 'post_story_image', order: 2, required: true, idempotency_class: 'story_post', payload: {} },
      ],
    } as ProfilePreview

    expect(buildJobStepItems([], preview).map((item) => item.title)).toEqual([
      'История 1 · Проверка',
      'История 1 · Подготовка',
      'История 1 · Публикация',
    ])
  })

  it('marks planned steps after a failed job as not started', () => {
    const preview = {
      steps: [
        { step_key: 'set_name', step_type: 'set_name', order: 0, required: true, idempotency_class: 'idempotent', payload: {} },
        { step_key: 'set_username', step_type: 'set_username', order: 1, required: true, idempotency_class: 'idempotent', payload: {} },
        { step_key: 'set_profile_photo', step_type: 'set_profile_photo', order: 2, required: true, idempotency_class: 'idempotent', payload: {} },
      ],
    } as ProfilePreview
    const steps: JobStep[] = [
      {
        step_key: 'set_name',
        step_type: 'set_name',
        status: 'succeeded',
        verification_attempted: false,
        verification_result: null,
        uncertain_reason: null,
        error_code: null,
        error_class: null,
        started_at: null,
        finished_at: null,
      },
      {
        step_key: 'set_username',
        step_type: 'set_username',
        status: 'failed',
        verification_attempted: false,
        verification_result: null,
        uncertain_reason: null,
        error_code: 'tdlib_error',
        error_class: 'TdlibProfileQueryError',
        started_at: null,
        finished_at: null,
      },
    ]

    expect(buildJobStepItems(steps, preview, 'failed').at(-1)).toMatchObject({
      key: 'set_profile_photo',
      status: 'not_started',
      statusLabel: 'Не запускалось',
      detail: 'Остановлено из-за ошибки выше',
      tone: 'neutral',
    })
  })

  it('does not show stale started steps as running after a terminal job', () => {
    const steps: JobStep[] = [
      {
        step_key: 'add_profile_audio',
        step_type: 'add_profile_audio',
        status: 'started',
        verification_attempted: false,
        verification_result: null,
        uncertain_reason: null,
        error_code: null,
        error_class: null,
        started_at: null,
        finished_at: null,
      },
    ]

    expect(buildJobStepItems(steps, null, 'failed')[0]).toMatchObject({
      key: 'add_profile_audio',
      status: 'uncertain',
      statusLabel: 'Проверить',
      detail: 'Выполнение оборвалось',
      tone: 'warning',
    })
  })
})

describe('buildJobResultSummary', () => {
  const job = {
    job_id: 'job-1',
    job_state: 'completed',
    account_id: 'account-1',
    execution_intent_hash: 'hash',
    started_at: null,
    finished_at: null,
    failure_reason: null,
    can_retry: false,
    can_refresh_runtime: true,
    step_counts: {},
  } satisfies JobDetail

  it('summarizes active jobs', () => {
    expect(buildJobResultSummary({ ...job, job_state: 'running' }, [])).toEqual({
      tone: 'active',
      title: 'Задача выполняется',
      description: 'Следим за шагами выполнения.',
      detail: null,
    })
  })

  it('summarizes completed jobs', () => {
    expect(buildJobResultSummary(job, [])).toEqual({
      tone: 'success',
      title: 'Всё применено',
      description: 'Профиль обновлён без ошибок.',
      detail: null,
    })
  })

  it('uses step error details for failed jobs', () => {
    expect(
      buildJobResultSummary(
        { ...job, job_state: 'failed', failure_reason: 'profile_runtime_failed' },
        [
          {
            step_key: 'set_username',
            step_type: 'set_username',
            status: 'failed',
            verification_attempted: false,
            verification_result: null,
            uncertain_reason: null,
            error_code: 'USERNAME_INVALID',
            error_class: 'validation',
            started_at: null,
            finished_at: null,
          },
        ],
      ),
    ).toEqual({
      tone: 'error',
      title: 'Ошибка выполнения',
      description: 'Проверьте проблемный шаг перед повторным запуском.',
      detail: 'Юзернейм некорректен',
    })
  })

  it('summarizes stale started steps on failed jobs as an interrupted execution', () => {
    expect(
      buildJobResultSummary(
        { ...job, job_state: 'failed', failure_reason: 'profile_runtime_failed' },
        [
          {
            step_key: 'add_profile_audio',
            step_type: 'add_profile_audio',
            status: 'started',
            verification_attempted: false,
            verification_result: null,
            uncertain_reason: null,
            error_code: null,
            error_class: null,
            started_at: null,
            finished_at: null,
          },
        ],
      ),
    ).toMatchObject({
      detail: 'Выполнение оборвалось',
    })
  })
})

describe('buildJobProgressSummary', () => {
  it('counts completed, failed, active, and not-started steps', () => {
    const items = [
      { key: 'set_name', title: 'Имя', status: 'succeeded', statusLabel: 'Готово', detail: 'Применено', tone: 'success' },
      { key: 'set_username', title: 'Юзернейм', status: 'failed', statusLabel: 'Ошибка', detail: 'TDLib ошибка', tone: 'error' },
      { key: 'set_photo', title: 'Фото', status: 'not_started', statusLabel: 'Не запускалось', detail: 'Остановлено', tone: 'neutral' },
    ] as const

    expect(buildJobProgressSummary(items)).toEqual({
      total: 3,
      completed: 1,
      failed: 1,
      active: 0,
      notStarted: 1,
      progressValue: 33,
      label: 'Применено 1 из 3',
    })
  })
})

describe('buildJobDisplayItems', () => {
  it('groups story steps into a single compact item with a mini pipeline', () => {
    const items = buildJobStepItems(
      [
        {
          step_key: 'story_1_validate_capabilities',
          step_type: 'validate_story_capabilities',
          status: 'succeeded',
          verification_attempted: false,
          verification_result: null,
          uncertain_reason: null,
          error_code: null,
          error_class: null,
          started_at: null,
          finished_at: null,
        },
        {
          step_key: 'story_1_prepare_media',
          step_type: 'prepare_story_media',
          status: 'failed',
          verification_attempted: false,
          verification_result: null,
          uncertain_reason: null,
          error_code: 'tdlib_error',
          error_class: 'TdlibProfileQueryError',
          started_at: null,
          finished_at: null,
        },
      ],
      {
        steps: [
          { step_key: 'set_name' },
          { step_key: 'story_1_validate_capabilities' },
          { step_key: 'story_1_prepare_media' },
          { step_key: 'story_1_post' },
        ],
      },
      'failed',
    )

    expect(buildJobDisplayItems(items)).toEqual([
      expect.objectContaining({ key: 'set_name', title: 'Имя', kind: 'step' }),
      expect.objectContaining({
        key: 'story_1',
        title: 'История 1',
        kind: 'story',
        status: 'failed',
        statusLabel: 'Ошибка',
        detail: 'Telegram не принял изменение',
        tone: 'error',
        children: [
          expect.objectContaining({ key: 'story_1_validate_capabilities', shortTitle: 'Проверка', tone: 'success' }),
          expect.objectContaining({ key: 'story_1_prepare_media', shortTitle: 'Подготовка', tone: 'error' }),
          expect.objectContaining({ key: 'story_1_post', shortTitle: 'Публикация', status: 'not_started' }),
        ],
      }),
    ])
  })
})

describe('shouldResetDraftAfterJobState', () => {
  it('keeps the editable draft after failed terminal jobs and clears it only after success', () => {
    expect(shouldResetDraftAfterJobState('completed')).toBe(true)
    expect(shouldResetDraftAfterJobState('failed')).toBe(false)
    expect(shouldResetDraftAfterJobState('partially_completed')).toBe(false)
    expect(shouldResetDraftAfterJobState('manual_intervention_needed')).toBe(false)
    expect(shouldResetDraftAfterJobState('dedup_blocked')).toBe(false)
  })
})
