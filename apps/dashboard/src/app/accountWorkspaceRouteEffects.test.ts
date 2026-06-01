import { describe, expect, it } from 'vitest'

import accountWorkspaceSource from './AccountWorkspace.tsx?raw'
import {
  shouldResetWorkspaceSectionState,
  workspaceSectionIdForSection,
  type AccountRouteState,
} from './accountWorkspaceRouteEffects'

const jobsRoute = {
  screen: 'account',
  accountId: 'account-1',
  section: 'jobs',
} satisfies AccountRouteState

describe('AccountWorkspace route effects', () => {
  it('does not depend on the aggregate params object', () => {
    expect(accountWorkspaceSource).not.toContain('[params]')
  })

  it('keeps job panel hide state across unrelated rerenders on the same route', () => {
    const rerenderedRoute = {
      screen: 'account',
      accountId: 'account-1',
      section: 'jobs',
    } satisfies AccountRouteState

    expect(shouldResetWorkspaceSectionState(jobsRoute, rerenderedRoute)).toBe(false)
  })

  it('resets job panel visibility only across account or section transitions', () => {
    expect(
      shouldResetWorkspaceSectionState(jobsRoute, {
        screen: 'account',
        accountId: 'account-1',
        section: 'debug',
      }),
    ).toBe(true)
    expect(
      shouldResetWorkspaceSectionState(jobsRoute, {
        screen: 'account',
        accountId: 'account-2',
        section: 'jobs',
      }),
    ).toBe(true)
  })

  it('maps scroll targets by semantic route section', () => {
    expect(workspaceSectionIdForSection(jobsRoute.section)).toBe('account-workspace-jobs')
    expect(workspaceSectionIdForSection('debug')).toBe('account-workspace-debug')
    expect(workspaceSectionIdForSection('profile')).toBeNull()
  })
})
