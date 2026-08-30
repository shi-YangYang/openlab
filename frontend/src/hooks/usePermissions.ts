import { useCallback, useEffect, useSyncExternalStore } from 'react'
import { App as AntApp } from 'antd'
import {
  getAgentPermissions,
  resetAgentPermissions,
  updateAgentPermissions,
} from '../api'
import type {
  AgentPermissionMode,
  AgentPermissionsUpdate,
} from '../types'

// Global shared permission state (spec-032 FR-14): a single module-level
// store so the settings page and the Agent toolbar always see the same
// mode/whitelist and update each other in real time.
interface PermissionsState {
  loaded: boolean
  error: string | null
  mode: AgentPermissionMode
  commandWhitelist: string[]
}

let state: PermissionsState = {
  loaded: false,
  error: null,
  mode: 'standard',
  commandWhitelist: [],
}

let inflight: Promise<void> | null = null
const listeners = new Set<() => void>()

function emit(): void {
  for (const listener of listeners) listener()
}

function setState(next: PermissionsState): void {
  state = next
  emit()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function getSnapshot(): PermissionsState {
  return state
}

function fetchPermissions(): Promise<void> {
  if (inflight) return inflight
  inflight = (async () => {
    try {
      const data = await getAgentPermissions()
      setState({
        loaded: true,
        error: null,
        mode: data.mode,
        commandWhitelist: data.command_whitelist,
      })
    } catch (e) {
      setState({
        ...state,
        error: e instanceof Error ? e.message : '加载 Agent 权限失败',
      })
    } finally {
      inflight = null
    }
  })()
  return inflight
}

export function usePermissions() {
  const { message } = AntApp.useApp()
  const snapshot = useSyncExternalStore(subscribe, getSnapshot)

  useEffect(() => {
    if (!state.loaded) void fetchPermissions()
  }, [])

  const applyUpdate = useCallback(
    async (payload: AgentPermissionsUpdate): Promise<boolean> => {
      try {
        const data = await updateAgentPermissions(payload)
        setState({
          loaded: true,
          error: null,
          mode: data.mode,
          commandWhitelist: data.command_whitelist,
        })
        return true
      } catch (e) {
        message.error(e instanceof Error ? e.message : '保存 Agent 权限失败')
        return false
      }
    },
    [message],
  )

  const updateMode = useCallback(
    (mode: AgentPermissionMode): Promise<boolean> =>
      applyUpdate({ mode, command_whitelist: state.commandWhitelist }),
    [applyUpdate],
  )

  const updateWhitelist = useCallback(
    (commandWhitelist: string[]): Promise<boolean> =>
      applyUpdate({ mode: state.mode, command_whitelist: commandWhitelist }),
    [applyUpdate],
  )

  const resetAll = useCallback(async (): Promise<boolean> => {
    try {
      const data = await resetAgentPermissions()
      setState({
        loaded: true,
        error: null,
        mode: data.mode,
        commandWhitelist: data.command_whitelist,
      })
      return true
    } catch (e) {
      message.error(e instanceof Error ? e.message : '恢复默认失败')
      return false
    }
  }, [message])

  // Restore only the whitelist: reset returns default state, then re-apply
  // the current mode so the mode is preserved (FR-14b).
  const resetWhitelist = useCallback(async (): Promise<boolean> => {
    try {
      const defaults = await resetAgentPermissions()
      const data = await updateAgentPermissions({
        mode: state.mode,
        command_whitelist: defaults.command_whitelist,
      })
      setState({
        loaded: true,
        error: null,
        mode: data.mode,
        commandWhitelist: data.command_whitelist,
      })
      return true
    } catch (e) {
      message.error(e instanceof Error ? e.message : '恢复默认白名单失败')
      return false
    }
  }, [message])

  return {
    ...snapshot,
    updateMode,
    updateWhitelist,
    resetAll,
    resetWhitelist,
    reload: () => void fetchPermissions(),
  }
}
