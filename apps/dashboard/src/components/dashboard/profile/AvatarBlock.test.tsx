import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { AvatarBlock } from './AvatarBlock'

const currentProfile = {
  first_name: 'Ada',
  last_name: 'Lovelace',
  bio: null,
  username: null,
  profile_photo_asset_id: null,
}

function renderAvatar(photoPreviewUrl: string | null): string {
  return renderToStaticMarkup(
    <AvatarBlock
      currentProfile={currentProfile}
      hasSelectedPhoto={Boolean(photoPreviewUrl)}
      isUploadingPhoto={false}
      onChoosePhoto={vi.fn()}
      onClearPhoto={vi.fn()}
      photoPreviewUrl={photoPreviewUrl}
      selectedPhotoName={null}
    />,
  )
}

describe('AvatarBlock', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  test('renders image for safe preview URLs', () => {
    expect(renderAvatar('blob:http://localhost/avatar')).toContain(
      'src="blob:http://localhost/avatar"',
    )
    expect(renderAvatar('/api/assets/avatar/content')).toContain(
      'src="/api/assets/avatar/content"',
    )
  })

  test('renders image for configured API asset URLs', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8002')

    expect(renderAvatar('http://localhost:8002/api/assets/avatar/content')).toContain(
      'src="http://localhost:8002/api/assets/avatar/content"',
    )
  })

  test('falls back to initials for unsafe preview URLs', () => {
    for (const unsafeUrl of [
      'javascript:alert(1)',
      'http://localhost/settings',
      'blob:http://evil.test/avatar',
    ]) {
      const html = renderAvatar(unsafeUrl)

      expect(html).not.toContain('<img')
      expect(html).not.toContain(unsafeUrl)
      expect(html).toContain('A')
    }
  })
})
