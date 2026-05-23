/**
 * AvatarBlock – avatar display with upload / delete interactions.
 */

import { Camera, Loader2, Trash2 } from 'lucide-react'
import { composeDisplayName, syncStateLabels, type CurrentProfile } from '@/lib/dashboard'
import { getApiBaseUrl } from '@/lib/config'

interface AvatarBlockProps {
  photoPreviewUrl: string | null
  hasSelectedPhoto: boolean
  isUploadingPhoto: boolean
  selectedPhotoName: string | null
  currentProfile: CurrentProfile
  onChoosePhoto: () => void
  onClearPhoto: () => void
}

function safePhotoPreviewUrl(photoPreviewUrl: string | null): string | null {
  const candidate = photoPreviewUrl?.trim()
  if (!candidate || candidate.startsWith('//') || /[<>\s]/.test(candidate)) return null
  if (candidate.startsWith('/')) return candidate

  try {
    const baseUrl = typeof window === 'undefined' ? 'http://localhost' : window.location.origin
    const parsed = new URL(candidate, baseUrl)
    if (parsed.protocol === 'blob:') return candidate
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null
    const allowedOrigins = new Set([baseUrl])
    const apiBaseUrl = getApiBaseUrl()
    if (apiBaseUrl) allowedOrigins.add(new URL(apiBaseUrl, baseUrl).origin)
    if (
      allowedOrigins.has(parsed.origin) &&
      (parsed.pathname.startsWith('/api/assets/') || parsed.origin === baseUrl)
    ) {
      return candidate
    }
  } catch {
    return null
  }

  return null
}

export function AvatarBlock({
  photoPreviewUrl,
  hasSelectedPhoto,
  isUploadingPhoto,
  selectedPhotoName,
  currentProfile,
  onChoosePhoto,
  onClearPhoto,
}: AvatarBlockProps) {
  const previewUrl = safePhotoPreviewUrl(photoPreviewUrl)

  return (
    <div className="flex-shrink-0 flex flex-col items-center">
      {/* ── Avatar ring ── */}
      <div className="relative mb-3 group cursor-pointer" onClick={onChoosePhoto}>
        <div className="rounded-full">
          {previewUrl ? (
            <img
              alt="Предпросмотр фото профиля"
              className="size-32 rounded-full object-cover shadow-sm border border-gray-100"
              src={previewUrl}
            />
          ) : (
            <div className="flex size-32 items-center justify-center rounded-full bg-gradient-to-br from-navy-400 via-navy-300 to-tangerine-300 text-5xl font-bold text-white shadow-sm">
              {composeDisplayName(
                currentProfile.first_name ?? '',
                currentProfile.last_name ?? '',
              )?.[0]?.toUpperCase() ?? 'A'}
            </div>
          )}

          {/* Hover overlay */}
          <div className="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
            <Camera className="text-white size-8" />
          </div>
        </div>

        {/* Camera badge */}
        <button
          aria-label="Изменить фото профиля"
          className="absolute bottom-0 right-0 flex size-10 items-center justify-center rounded-full border-[3px] border-white bg-navy-400 shadow-md transition-colors hover:bg-navy-500 z-10"
          onClick={(e) => { e.stopPropagation(); onChoosePhoto() }}
          type="button"
        >
          {isUploadingPhoto ? (
            <Loader2 className="size-4 text-white animate-spin" />
          ) : (
            <Camera className="size-4 text-white" />
          )}
        </button>

        {/* Delete badge – only when a photo is selected */}
        {hasSelectedPhoto && (
          <button
            aria-label="Удалить фото"
            className="absolute top-0 right-0 flex size-8 items-center justify-center rounded-full border-[2px] border-white bg-red-50 text-red-500 hover:bg-red-500 hover:text-white shadow-sm transition-all z-10"
            onClick={(e) => { e.stopPropagation(); onClearPhoto() }}
            type="button"
          >
            <Trash2 className="size-3.5" />
          </button>
        )}
      </div>

      {/* Caption */}
      <div className="text-center w-full max-w-[120px]">
        {hasSelectedPhoto ? (
          <p className="mb-1 text-[9px] font-semibold uppercase tracking-wider text-gray-400">
            {syncStateLabels.appKnown}
          </p>
        ) : null}
        <p className="text-[10px] text-gray-400 leading-tight">
          {selectedPhotoName ?? (!hasSelectedPhoto ? 'JPG, PNG до 5 МБ' : null)}
        </p>
      </div>
    </div>
  )
}
