import { unwrap } from './core'
import type { ExecutionPolicy, ExecutionPolicyUpdate, StylistTgClient, WorkspaceSafetyPolicy, WorkspaceSafetyPolicyUpdate } from './types'
export async function fetchExecutionPolicy(client: StylistTgClient): Promise<ExecutionPolicy> {
  return unwrap(client.openapi.GET('/api/settings/execution-policy'), 'execution policy')
}

export async function updateExecutionPolicy(
  client: StylistTgClient,
  update: ExecutionPolicyUpdate,
): Promise<ExecutionPolicy> {
  return unwrap(
    client.openapi.PATCH('/api/settings/execution-policy', {
      body: update,
    }),
    'update execution policy',
  )
}

export async function fetchWorkspaceSafetyPolicy(client: StylistTgClient): Promise<WorkspaceSafetyPolicy> {
  return unwrap(client.openapi.GET('/api/safety-policy'), 'workspace safety policy')
}

export async function updateWorkspaceSafetyPolicy(
  client: StylistTgClient,
  update: WorkspaceSafetyPolicyUpdate,
): Promise<WorkspaceSafetyPolicy> {
  return unwrap(client.openapi.PATCH('/api/safety-policy', { body: update }), 'update workspace safety policy')
}
