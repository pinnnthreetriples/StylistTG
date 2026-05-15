import type { ProfilePreview } from './api'
import { labelBlockingItem } from '@/lib/uiLabels'

export type PreviewStatus = {
  kind: 'empty' | 'ready' | 'warning' | 'blocked' | 'dedup'
  title: string
  description: string
  items: string[]
}

export function buildPreviewStatus(preview: ProfilePreview | null): PreviewStatus {
  if (!preview) {
    return {
      kind: 'empty',
      title: 'Предпросмотр не готов',
      description: 'Измените профиль, чтобы увидеть план применения.',
      items: [],
    }
  }

  if (preview.blocking_errors.length > 0 || !preview.can_create_job) {
    return {
      kind: 'blocked',
      title: 'Запуск заблокирован',
      description: 'Нужно устранить блокирующие условия перед созданием задачи.',
      items: preview.blocking_errors.map(labelBlockingItem),
    }
  }

  if (preview.dedup_would_block) {
    return {
      kind: 'dedup',
      title: 'Такая задача уже есть',
      description: 'Повторный запуск с тем же набором изменений не нужен.',
      items: preview.dedup_blocked_by_job_id ? [preview.dedup_blocked_by_job_id] : [],
    }
  }

  if (preview.warnings.length > 0) {
    return {
      kind: 'warning',
      title: 'Есть предупреждения',
      description: 'Проверьте предупреждения перед запуском.',
      items: preview.warnings.map(labelBlockingItem),
    }
  }

  return {
    kind: 'ready',
    title: 'Готово к запуску',
    description: `Будет применено ${preview.steps.length} ${operationWord(preview.steps.length)}.`,
    items: [],
  }
}

function operationWord(count: number): string {
  if (count === 1) {
    return 'операция'
  }
  if (count >= 2 && count <= 4) {
    return 'операции'
  }
  return 'операций'
}
