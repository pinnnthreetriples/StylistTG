import { ArrowRight, FileJson, FolderArchive, KeyRound, Loader2, Phone, RotateCcw, ShieldCheck, Upload, XCircle } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'

import { Button, Tabs, TabsList, TabsTrigger, Textarea } from '@stylisttg/ui'
import {
  cancelAccountOnboardingBatch,
  confirmAccountOnboardingBatch,
  createAccountOnboardingBatch,
  fetchAccountOnboardingBatch,
  retryAccountOnboardingItem,
  submitAccountOnboardingCode,
  submitAccountOnboardingPassword,
  validateAccountOnboardingBatch,
  uploadAccountOnboardingArtifact,
  type AccountOnboardingArtifact,
  type AccountOnboardingItem,
  type AccountOnboardingSnapshot,
  type AccountOnboardingSourceType,
} from '@stylisttg/api-client'

import { dashboardApiClient } from '@/lib/apiClient'
import { normalizeError } from '@/lib/appErrors'
import { makeOnboardingKey, parseOnboardingPhones } from '@/features/accounts/accountOnboardingWizard'

const DRAFT_KEY = 'stylisttg.account_onboarding_draft'
const ACTIVE_BATCH_KEY = 'stylisttg.account_onboarding_active_batch_id'
const CONSENT_VERSION = 'account-onboarding-v1'
type SupportLevel = 'full' | 'preview_only' | 'requires_reauth' | 'unsupported'

const sourceOptions: Array<{ type: AccountOnboardingSourceType; label: string; icon: typeof Phone }> = [
  { type: 'phone_bulk', label: 'Номера', icon: Phone },
  { type: 'json_metadata', label: 'JSON', icon: FileJson },
  { type: 'tdlib_directory', label: 'TDLib', icon: FolderArchive },
  { type: 'tdata_archive', label: 'tdata', icon: FolderArchive },
  { type: 'session_file', label: 'Session', icon: KeyRound },
]

const fallbackSupport: Partial<Record<AccountOnboardingSourceType, SupportLevel>> = {
  phone: 'full',
  phone_bulk: 'full',
  json_metadata: 'requires_reauth',
  tdlib_directory: 'preview_only',
  tdata_archive: 'requires_reauth',
  session_file: 'preview_only',
  reauth: 'requires_reauth',
}

type OnboardingDraft = {
  sourceType: AccountOnboardingSourceType
  label: string
  rawInput: string
  jsonInput: string
}

function readDraft(): OnboardingDraft {
  const fallback: OnboardingDraft = {
    sourceType: 'phone_bulk',
    label: '',
    rawInput: '',
    jsonInput: '{\n  "username": "demo"\n}',
  }
  if (typeof window === 'undefined') return fallback
  const saved = window.localStorage.getItem(DRAFT_KEY)
  if (!saved) return fallback
  try {
    const draft = JSON.parse(saved) as Partial<OnboardingDraft>
    return {
      sourceType: draft.sourceType ?? fallback.sourceType,
      label: draft.label ?? fallback.label,
      rawInput: draft.rawInput ?? fallback.rawInput,
      jsonInput: draft.jsonInput ?? fallback.jsonInput,
    }
  } catch {
    window.localStorage.removeItem(DRAFT_KEY)
    return fallback
  }
}

export function AddAccountsPage(_props: {
  testDcEnabled: boolean
  testDcPending: boolean
  onTestDcChange: (enabled: boolean) => void
}) {
  void _props
  const draft = useMemo(readDraft, [])
  const [sourceType, setSourceType] = useState<AccountOnboardingSourceType>(draft.sourceType)
  const [label, setLabel] = useState(draft.label)
  const [rawInput, setRawInput] = useState(draft.rawInput)
  const [jsonInput, setJsonInput] = useState(draft.jsonInput)
  const [artifact, setArtifact] = useState<AccountOnboardingArtifact | null>(null)
  const [artifactFilename, setArtifactFilename] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<AccountOnboardingSnapshot | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const parsedPhones = useMemo(() => parseOnboardingPhones(rawInput, label), [rawInput, label])
  const capability = snapshot?.capabilities.find((item) => item.source_type === sourceType)

  useEffect(() => {
    const activeBatchId = window.localStorage.getItem(ACTIVE_BATCH_KEY)
    if (activeBatchId) void run(() => fetchAccountOnboardingBatch(dashboardApiClient, activeBatchId), true)
  }, [])

  useEffect(() => {
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify({ sourceType, label, rawInput, jsonInput }))
  }, [sourceType, label, rawInput, jsonInput])

  useEffect(() => {
    if (!snapshot?.poll_again_in_ms) return undefined
    const timer = window.setTimeout(() => {
      void run(() => fetchAccountOnboardingBatch(dashboardApiClient, snapshot.batch.id), true)
    }, snapshot.poll_again_in_ms)
    return () => window.clearTimeout(timer)
  }, [snapshot?.batch.id, snapshot?.poll_again_in_ms])

  async function run<T>(action: () => Promise<T>, quiet = false): Promise<T | null> {
    if (!quiet) setBusy(true)
    setError(null)
    try {
      const result = await action()
      if (isSnapshot(result)) {
        setSnapshot(result)
        window.localStorage.setItem(ACTIVE_BATCH_KEY, result.batch.id)
      }
      return result
    } catch (err) {
      setError(normalizeError(err).message)
      return null
    } finally {
      if (!quiet) setBusy(false)
    }
  }

  async function createPreview() {
    let metadataJson: unknown = undefined
    if (sourceType === 'json_metadata') {
      try {
        metadataJson = JSON.parse(jsonInput)
      } catch {
        setError('JSON invalid')
        return
      }
    }
    const created = await run(() => createAccountOnboardingBatch(dashboardApiClient, {
      idempotency_key: makeOnboardingKey('batch'),
      source_type: sourceType,
      label: label || null,
      phone_items: sourceType === 'phone_bulk' ? parsedPhones : [],
      metadata_json: metadataJson,
      artifact_id: artifact?.id ?? null,
      filename: artifactFilename,
    }))
    if (created) await run(() => validateAccountOnboardingBatch(dashboardApiClient, created.batch.id, { idempotency_key: makeOnboardingKey('validate') }))
  }

  async function uploadFile(file: File) {
    const content = await fileToBase64(file)
    const uploaded = await run(() => uploadAccountOnboardingArtifact(dashboardApiClient, {
      idempotency_key: makeOnboardingKey('artifact'),
      source_type: sourceType,
      filename: file.name,
      content_base64: content,
    }))
    if (uploaded && 'sha256' in uploaded) {
      setArtifact(uploaded)
      setArtifactFilename(file.name)
    }
  }

  async function loadJsonFile(file: File) {
    if (!file.name.toLowerCase().endsWith('.json')) {
      setError('Нужен JSON file')
      return
    }
    setJsonInput(await file.text())
  }

  function onArtifactDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    const file = event.dataTransfer.files[0]
    if (file) void uploadFile(file)
  }

  function onJsonFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) void loadJsonFile(file)
  }

  const canCreate = sourceType === 'phone_bulk' ? parsedPhones.length > 0 : sourceType === 'json_metadata' ? jsonInput.trim().length > 0 : Boolean(artifact)

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <div className="mb-4 flex flex-col gap-1">
        <h1 className="font-sans text-2xl font-bold tracking-tight text-foreground">Добавление аккаунтов</h1>
      </div>

      <section className="border-b border-border py-4">
        <div className="mb-3 text-xs font-semibold uppercase text-muted-foreground">Способ</div>
        <Tabs value={sourceType} onValueChange={(value) => setSourceType(value as AccountOnboardingSourceType)}>
          <TabsList className="flex w-full flex-wrap items-stretch justify-start gap-1 bg-muted/70">
          {sourceOptions.map((option) => {
            const Icon = option.icon
            const level = snapshot?.capabilities.find((item) => item.source_type === option.type)?.user_facing_support_level ?? fallbackSupport[option.type] ?? 'unsupported'
            return <TabsTrigger className="min-h-14 flex-1 basis-[160px] justify-start gap-2 px-3 py-2 text-left" key={option.type} value={option.type}><Icon className="h-4 w-4 shrink-0" /><span className="min-w-0"><span className="block font-medium">{option.label}</span><span className="block truncate text-xs text-muted-foreground">{supportLabel(level)}</span></span></TabsTrigger>
          })}
          </TabsList>
        </Tabs>
        {capability ? <div className="mt-3 text-xs text-muted-foreground">{supportLabel(capability.user_facing_support_level)}</div> : null}
      </section>

      <section className="border-b border-border py-4">
        <div className="mb-3 text-xs font-semibold uppercase text-muted-foreground">Ввод или загрузка</div>
        <input className="mb-3 w-full rounded-md border border-border bg-background px-3 py-2 text-sm" placeholder="Label" value={label} onChange={(event) => setLabel(event.target.value)} />
        {sourceType === 'phone_bulk' ? (
          <>
            <Textarea value={rawInput} onChange={(event) => setRawInput(event.target.value)} placeholder={'+15550102000 Alice\n+15550102001; +15550102002'} rows={6} />
            <div className="mt-2 text-xs text-muted-foreground">{parsedPhones.length} номеров</div>
          </>
        ) : sourceType === 'json_metadata' ? (
          <div className="space-y-2">
            <Textarea value={jsonInput} onChange={(event) => setJsonInput(event.target.value)} rows={8} />
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground"><Upload className="h-4 w-4" />Загрузить JSON<input accept="application/json,.json" className="sr-only" type="file" onChange={onJsonFileChange} /></label>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex min-h-16 cursor-pointer items-center gap-2 rounded-md border border-dashed border-border p-4 text-sm text-foreground" onDragOver={(event) => event.preventDefault()} onDrop={onArtifactDrop}><Upload className="h-4 w-4" />{artifact ? `${artifactFilename ?? artifact.content_type_detected} · ${Math.round(artifact.size_bytes / 1024)} KB` : 'Выбрать или перетащить приватный artifact'}<input className="sr-only" type="file" onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadFile(file) }} /></label>
            {artifact ? <Button variant="secondary" onClick={() => { setArtifact(null); setArtifactFilename(null) }} type="button"><XCircle className="mr-2 h-4 w-4" />Remove</Button> : null}
          </div>
        )}
        <Button className="mt-4" disabled={!canCreate || busy} onClick={() => void createPreview()}>{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ArrowRight className="mr-2 h-4 w-4" />}Preview</Button>
      </section>

      {error ? <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
      {snapshot ? <Results snapshot={snapshot} busy={busy} run={run} setSnapshot={setSnapshot} /> : null}
    </div>
  )
}

function Results({ snapshot, busy, run, setSnapshot }: { snapshot: AccountOnboardingSnapshot; busy: boolean; run: <T>(action: () => Promise<T>, quiet?: boolean) => Promise<T | null>; setSnapshot: (snapshot: AccountOnboardingSnapshot) => void }) {
  const updateItem = (next: AccountOnboardingItem) => setSnapshot({ ...snapshot, items: snapshot.items.map((item) => item.id === next.id ? next : item) })
  return (
    <section className="rounded-lg border border-border bg-background p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div><div className="text-sm font-semibold text-foreground">3. Preview / Progress</div><div className="text-xs text-muted-foreground">{snapshot.batch.status} · ready {snapshot.batch.counters.ready_count}/{snapshot.batch.counters.total_count}</div></div>
        <div className="flex gap-2">
          <Button disabled={busy || snapshot.batch.status !== 'preview_ready'} onClick={() => void run(() => confirmAccountOnboardingBatch(dashboardApiClient, snapshot.batch.id, { idempotency_key: makeOnboardingKey('confirm'), confirmation: 'ADD_ACCOUNTS', consent_accepted: true, consent_version: CONSENT_VERSION }))}><ShieldCheck className="mr-2 h-4 w-4" />ADD_ACCOUNTS</Button>
          <Button disabled={busy} variant="secondary" onClick={() => void run(() => cancelAccountOnboardingBatch(dashboardApiClient, snapshot.batch.id, { idempotency_key: makeOnboardingKey('cancel') }))}><XCircle className="mr-2 h-4 w-4" />Cancel</Button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead className="border-b border-border text-left text-xs text-muted-foreground"><tr><th className="py-2">Hint</th><th>Status</th><th>Source</th><th>Risk</th><th>Message</th><th>Action</th></tr></thead>
          <tbody>{snapshot.items.map((item) => <tr className="border-b border-border/60" key={item.id}><td className="py-2">{item.phone_hint ?? item.username_hint ?? item.telegram_user_id_hint ?? item.label ?? 'metadata'}</td><td>{item.status}</td><td>{item.source_type}</td><td>{item.risk_level}</td><td>{itemMessage(item)}</td><td><ItemAction item={item} batchId={snapshot.batch.id} onAction={updateItem} /></td></tr>)}</tbody>
        </table>
      </div>
    </section>
  )
}

function ItemAction({ item, batchId, onAction }: { item: AccountOnboardingItem; batchId: string; onAction: (item: AccountOnboardingItem) => void }) {
  const [value, setValue] = useState('')
  if (item.next_action === 'submit_code') {
    return <InlineSubmit label="Code" value={value} setValue={setValue} onSubmit={() => void submitAccountOnboardingCode(dashboardApiClient, batchId, item.id, { idempotency_key: makeOnboardingKey('code'), code: value }).then(onAction)} />
  }
  if (item.next_action === 'submit_password') {
    return <InlineSubmit label="2FA" value={value} setValue={setValue} onSubmit={() => void submitAccountOnboardingPassword(dashboardApiClient, batchId, item.id, { idempotency_key: makeOnboardingKey('password'), password: value }).then(onAction)} />
  }
  if (item.next_action === 'retry') {
    return <Button size="sm" variant="secondary" onClick={() => void retryAccountOnboardingItem(dashboardApiClient, batchId, item.id, { idempotency_key: makeOnboardingKey('retry') }).then(onAction)}><RotateCcw className="mr-2 h-4 w-4" />Retry</Button>
  }
  return <span className="text-xs text-muted-foreground">{item.next_action ?? ''}</span>
}

function InlineSubmit({ label, value, setValue, onSubmit }: { label: string; value: string; setValue: (value: string) => void; onSubmit: () => void }) {
  return <span className="flex gap-2"><input className="w-28 rounded-md border border-border px-2 py-1 text-sm" placeholder={label} value={value} onChange={(event) => setValue(event.target.value)} /><Button size="sm" onClick={onSubmit}>Send</Button></span>
}

function supportLabel(level: string): string {
  return ({ full: 'Полная поддержка', preview_only: 'Только предпросмотр', requires_reauth: 'Требуется ручная авторизация', unsupported: 'Неподдерживаемый формат' } as Record<string, string>)[level] ?? level
}

function itemMessage(item: AccountOnboardingItem): string {
  const base = item.validation_message ?? item.last_error_message ?? ''
  return item.next_retry_at ? `${base} Retry after ${new Date(item.next_retry_at).toLocaleString()}` : base
}

function isSnapshot(value: unknown): value is AccountOnboardingSnapshot {
  return typeof value === 'object' && value !== null && 'batch' in value && 'items' in value
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '')
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}
