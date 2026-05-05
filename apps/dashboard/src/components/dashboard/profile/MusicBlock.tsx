/**
 * MusicBlock – profile audio display with upload / keep / remove actions.
 */

import { Loader2, Music2, Play, RotateCcw, Trash2, UploadCloud } from 'lucide-react'
import { appKnownMediaSyncNote, syncStateLabels } from '@/lib/dashboard'

interface MusicBlockProps {
  profileAudio: {
    title: string | null
    performer: string | null
    duration_seconds: number | null
    source_asset_id: string | null
  } | null
  profileAudioAction: 'keep' | 'add' | 'remove'
  selectedAudioName: string | null
  isUploadingAudio: boolean
  onChooseAudio: () => void
  onKeepAudio: () => void
  onRemoveAudio: () => void
}

export function MusicBlock({
  profileAudio,
  profileAudioAction,
  selectedAudioName,
  isUploadingAudio,
  onChooseAudio,
  onKeepAudio,
  onRemoveAudio,
}: MusicBlockProps) {
  const isEmpty =
    !profileAudio?.source_asset_id &&
    !selectedAudioName &&
    profileAudioAction !== 'add'

  return (
    <div className="section-card bg-white rounded-xl border border-gray-200 p-4 mb-4 delay-2">
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Music2 className="text-navy-400 size-4" />
          <h2 className="font-display font-bold text-sm tracking-tight text-gray-900">
            Музыка профиля
          </h2>
        </div>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
          {profileAudioAction === 'keep' ? syncStateLabels.appKnown : syncStateLabels.draft}
        </span>
      </div>

      {isEmpty ? (
        /* ── Empty state ── */
        <div className="rounded-lg bg-gray-50 px-3 py-6 text-center border border-dashed border-gray-200 flex flex-col items-center justify-center">
          <p className="text-sm font-semibold text-gray-900">Музыка профиля не выбрана</p>
          <p className="mb-3 mt-1 text-xs text-gray-500">Загрузите MP3/M4A, чтобы подготовить задачу на добавление музыки.</p>
          <button
            onClick={onChooseAudio}
            disabled={isUploadingAudio}
            className="flex items-center gap-1.5 px-3 py-2 bg-white shadow-sm hover:bg-gray-50 text-gray-700 rounded-lg text-xs font-semibold transition-colors disabled:opacity-50 border border-gray-200"
          >
            {isUploadingAudio ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <UploadCloud className="size-3.5" />
            )}
            Загрузить MP3/M4A
          </button>
        </div>
      ) : (
        /* ── Active track row ── */
        <div className="flex flex-col gap-2">
          <div
            className={`flex items-center justify-between p-2.5 rounded-lg border group transition-all ${
              profileAudioAction === 'remove'
                ? 'bg-red-50/50 border-red-100'
                : profileAudioAction === 'add'
                  ? 'bg-tangerine-50/30 border-tangerine-100'
                  : 'bg-white border-gray-200 hover:border-gray-300'
            }`}
          >
            {/* Track info */}
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 rounded-full bg-navy-50 flex items-center justify-center flex-shrink-0 text-navy-400">
                <Play className="size-4 ml-0.5" />
              </div>
              <div className="min-w-0">
                <p
                  className={`text-sm font-semibold truncate ${
                    profileAudioAction === 'remove' ? 'text-gray-500 line-through' : 'text-gray-800'
                  }`}
                >
                  {selectedAudioName ?? profileAudio?.title ?? 'Аудиофайл'}
                </p>
                <p className="text-[11px] text-gray-400 truncate mt-0.5">
                  {profileAudioAction === 'remove'
                    ? 'Будет удалено'
                    : selectedAudioName
                      ? 'Новый файл готов к задаче'
                      : profileAudio?.performer ?? 'Музыка профиля'}
                </p>
                {profileAudioAction === 'keep' && profileAudio?.source_asset_id ? (
                  <p className="mt-0.5 text-[10px] leading-snug text-gray-400">
                    {appKnownMediaSyncNote}
                  </p>
                ) : null}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 flex-shrink-0">
              {/* Replace */}
              <button
                onClick={onChooseAudio}
                disabled={isUploadingAudio}
                className="p-2 text-gray-400 hover:text-navy-600 hover:bg-navy-50 rounded-md transition-colors"
                title="Заменить музыку"
              >
                <UploadCloud className="size-4" />
              </button>

              {/* Undo / Delete */}
              {profileAudioAction === 'remove' || profileAudioAction === 'add' ? (
                <button
                  onClick={onKeepAudio}
                  className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
                  title="Отменить действие"
                >
                  <RotateCcw className="size-4" />
                </button>
              ) : (
                <button
                  onClick={onRemoveAudio}
                  className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
                  title="Удалить музыку"
                >
                  <Trash2 className="size-4" />
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
