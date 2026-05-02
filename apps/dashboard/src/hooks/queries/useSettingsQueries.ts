import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { updateExecutionPolicy } from '@/lib/api'
import { updateAuthRuntimeMode } from '@/lib/auth'
import {
  settingsBundleQueryOptions,
  updateSettingsAuthModeInCache,
  updateSettingsPolicyInCache,
} from '@/lib/queries'

export function useSettingsBundleQuery() {
  return useQuery(settingsBundleQueryOptions())
}

export function useUpdateExecutionPolicyMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateExecutionPolicy,
    onSuccess: (policy) => updateSettingsPolicyInCache(queryClient, policy),
  })
}

export function useUpdateAuthRuntimeModeMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateAuthRuntimeMode,
    onSuccess: (authMode) => updateSettingsAuthModeInCache(queryClient, authMode),
  })
}
