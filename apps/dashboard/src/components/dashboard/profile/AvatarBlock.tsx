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

type SafePhotoPreviewUrl = string & { readonly __safePhotoPreviewUrl: unique symbol }

const ASSET_CONTENT_PATH_PATTERN = /^\/api\/assets\/([^/]+)\/content$/
const ASSET_ID_PATTERN = /^[A-Za-z0-9._~-]+$/

function safePhotoPreviewUrl(photoPreviewUrl: string | null): SafePhotoPreviewUrl | null {
  const candidate = photoPreviewUrl?.trim()
  if (!candidate || candidate.startsWith('//') || /[<>\s]/.test(candidate)) return null

  try {
    const baseOrigin = typeof window === 'undefined' ? 'http://localhost' : window.location.origin
    const blobUrl = safeBlobPreviewUrl(candidate, baseOrigin)
    if (blobUrl) return blobUrl

    const parsed = new URL(candidate, baseOrigin)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null
    const assetPath = safeAssetContentPath(parsed.pathname)
    if (!assetPath) return null

    const allowedOrigins = new Set([baseOrigin])
    const apiBaseUrl = getApiBaseUrl()
    if (apiBaseUrl) allowedOrigins.add(new URL(apiBaseUrl, baseOrigin).origin)
    if (!allowedOrigins.has(parsed.origin)) return null
    return (candidate.startsWith('/') ? assetPath : `${parsed.origin}${assetPath}`) as SafePhotoPreviewUrl
  } catch {
    return null
  }
}

function safeAssetContentPath(pathname: string): string | null {
  const match = ASSET_CONTENT_PATH_PATTERN.exec(pathname)
  if (!match) return null
  const assetId = decodeURIComponent(match[1])
  if (!ASSET_ID_PATTERN.test(assetId)) return null
  return `/api/assets/${encodeURIComponent(assetId)}/content`
}

function safeBlobPreviewUrl(candidate: string, baseOrigin: string): SafePhotoPreviewUrl | null {
  if (!candidate.startsWith('blob:')) return null
  const parsed = new URL(candidate)
  if (parsed.protocol !== 'blob:') return null
  const innerUrl = new URL(parsed.pathname)
  if (innerUrl.origin !== baseOrigin) return null

  const blobId = decodeURIComponent(innerUrl.pathname.replace(/^\/+/, ''))
  if (!ASSET_ID_PATTERN.test(blobId)) return null
  return `blob:${innerUrl.origin}/${encodeURIComponent(blobId)}` as SafePhotoPreviewUrl
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
      <div className="relative mb-3 group">
        <button
          aria-label="Изменить фото профиля"
          className="block rounded-full border-0 bg-transparent p-0 cursor-pointer"
          onClick={onChoosePhoto}
          type="button"
        >
          {previewUrl ? (
            <img
              alt="Предпросмотр фото профиля"
              className="size-32 rounded-full object-cover shadow-sm border border-border"
              src={previewUrl}
            />
          ) : (
            <div className="flex size-32 items-center justify-center rounded-full bg-muted text-5xl font-bold text-primary-foreground shadow-sm">
              {composeDisplayName(
                currentProfile.first_name ?? '',
                currentProfile.last_name ?? '',
              )?.[0]?.toUpperCase() ?? 'A'}
            </div>
          )}

          {/* Hover overlay */}
          <div className="absolute inset-0 rounded-full bg-foreground/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
            <Camera className="text-primary-foreground size-8" />
          </div>
        </button>

        {/* Camera badge */}
        <button
          aria-label="Изменить фото профиля"
          className="absolute bottom-0 right-0 flex size-10 items-center justify-center rounded-full border-[3px] border-background bg-primary shadow-md transition-colors hover:bg-primary z-10"
          onClick={(e) => { e.stopPropagation(); onChoosePhoto() }}
          type="button"
        >
          {isUploadingPhoto ? (
            <Loader2 className="size-4 text-primary-foreground animate-spin" />
          ) : (
            <Camera className="size-4 text-primary-foreground" />
          )}
        </button>

        {/* Delete badge – only when a photo is selected */}
        {hasSelectedPhoto && (
          <button
            aria-label="Удалить фото"
            className="absolute top-0 right-0 flex size-8 items-center justify-center rounded-full border-[2px] border-background bg-destructive/10 text-destructive hover:bg-destructive hover:text-primary-foreground shadow-sm transition-all z-10"
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
          <p className="mb-1 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
            {syncStateLabels.appKnown}
          </p>
        ) : null}
        <p className="text-[10px] text-muted-foreground leading-tight">
          {selectedPhotoName ?? (!hasSelectedPhoto ? 'JPG, PNG до 5 МБ' : null)}
        </p>
      </div>
    </div>
  )
}
