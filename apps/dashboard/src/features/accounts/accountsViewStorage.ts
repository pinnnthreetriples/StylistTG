export function accountsViewStorageKey({
  appEnv = import.meta.env.VITE_APP_ENV || 'local',
  workspaceId = 'local',
  userId = 'local',
}: {
  appEnv?: string
  workspaceId?: string
  userId?: string
} = {}): string {
  return `stylisttg:${appEnv || 'local'}:${workspaceId || 'local'}:${userId || 'local'}:accounts:view`
}
