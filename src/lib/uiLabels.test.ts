import { describe, expect, it } from 'vitest'

import { labelBlockingItem, labelIssue, labelStoryCapabilityWarning } from '@/lib/uiLabels'

describe('ui labels', () => {
  it('explains story capability blockers in Russian', () => {
    expect(labelBlockingItem('stories are disabled')).toBe('Истории выключены в настройках приложения')
    expect(labelStoryCapabilityWarning('stories live TDLib publishing requires TDLib profile execution')).toBe(
      'Публикация историй будет доступна после включения TDLib-исполнения профиля',
    )
    expect(labelStoryCapabilityWarning('stories live TDLib publishing is disabled')).toBe(
      'Публикация историй пока выключена',
    )
  })

  it('keeps clear music and story execution failure labels', () => {
    expect(labelIssue('PROFILE_AUDIO_UNSUPPORTED_FORMAT')).toBe('Для музыки профиля нужен MP3 или M4A')
    expect(labelIssue('PROFILE_AUDIO_FILE_ID_MISSING')).toBe('Telegram не вернул файл музыки')
    expect(labelIssue('PROFILE_AUDIO_ADD_FAILED')).toBe('Telegram не добавил музыку в профиль')
    expect(labelIssue('PROFILE_AUDIO_REMOVE_FAILED')).toBe('Telegram не удалил музыку из профиля')
    expect(labelIssue('STORY_POST_FAILED')).toBe('Telegram не опубликовал историю')
    expect(labelIssue('STORY_TELEGRAM_REJECTED')).toBe('Telegram отклонил публикацию истории')
    expect(labelIssue('story_post_confirmation_timeout')).toBe('Telegram не подтвердил публикацию истории')
    expect(labelIssue('tdlib_profile_step_failed')).toBe('Telegram не применил шаг профиля')
  })
})
