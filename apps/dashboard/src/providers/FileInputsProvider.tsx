/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useRef } from 'react'

type FileInputsContextValue = {
  triggerPhotoInput: () => void
  triggerAudioInput: () => void
  triggerStoryInput: () => void
}

const FileInputsContext = createContext<FileInputsContextValue | null>(null)

export function useFileInputs(): FileInputsContextValue {
  const ctx = useContext(FileInputsContext)
  if (!ctx) throw new Error('useFileInputs must be used within FileInputsProvider')
  return ctx
}

type FileInputsProviderProps = {
  children: React.ReactNode
  onPhotoChange: (file: File | null) => void
  onAudioChange: (file: File | null) => void
  onStoryChange: (file: File, kind: 'image' | 'video') => void
}

export function FileInputsProvider({
  children,
  onPhotoChange,
  onAudioChange,
  onStoryChange,
}: FileInputsProviderProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const audioInputRef = useRef<HTMLInputElement | null>(null)
  const storyImageInputRef = useRef<HTMLInputElement | null>(null)

  const triggerPhotoInput = useCallback(() => fileInputRef.current?.click(), [])
  const triggerAudioInput = useCallback(() => audioInputRef.current?.click(), [])
  const triggerStoryInput = useCallback(() => storyImageInputRef.current?.click(), [])

  return (
    <FileInputsContext.Provider value={{ triggerPhotoInput, triggerAudioInput, triggerStoryInput }}>
      {children}
      <input
        accept="image/png,image/jpeg"
        className="hidden"
        onChange={(e) => onPhotoChange(e.target.files?.[0] ?? null)}
        ref={fileInputRef}
        type="file"
      />
      <input
        accept="image/png,image/jpeg,image/webp,video/mp4,video/quicktime,video/webm"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0] ?? null
          if (!file) return
          const kind = file.type.startsWith('video/') ? 'video' : 'image'
          onStoryChange(file, kind)
        }}
        ref={storyImageInputRef}
        type="file"
      />
      <input
        accept="audio/mpeg,audio/mp4,.mp3,.m4a"
        className="hidden"
        onChange={(e) => onAudioChange(e.target.files?.[0] ?? null)}
        ref={audioInputRef}
        type="file"
      />
    </FileInputsContext.Provider>
  )
}
