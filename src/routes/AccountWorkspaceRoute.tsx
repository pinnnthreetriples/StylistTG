import { useParams } from '@tanstack/react-router'

import App from '@/App'
import type { AccountWorkspaceSection } from '@/lib/routes'

export function AccountWorkspaceRoute({ section }: { section: AccountWorkspaceSection }) {
  const { accountId } = useParams({ strict: false }) as { accountId: string }
  return <App key={`account:${accountId}`} route={{ screen: 'account', accountId, section }} />
}
