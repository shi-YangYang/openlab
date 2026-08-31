import { App as AntApp, Select, Tooltip } from 'antd'
import { usePermissions } from '../../hooks/usePermissions'
import type { AgentPermissionMode } from '../../types'
import styles from './AgentPage.module.css'

const MODE_OPTIONS: { value: AgentPermissionMode; label: string }[] = [
  { value: 'conservative', label: '保守模式' },
  { value: 'standard', label: '标准模式' },
  { value: 'full', label: '完全访问' },
]

const MODE_HINTS: Record<AgentPermissionMode, string> = {
  conservative: '保守模式：每一步危险操作都需要确认',
  standard: '标准模式：本地沙箱代码与只读命令自动执行，其余逐次确认',
  full: '完全访问：全部工具自动执行，仅破坏性命令黑名单仍需确认',
}

export default function AgentPermissionSelect() {
  const { modal } = AntApp.useApp()
  const { mode, loaded, error, updateMode, reload } = usePermissions()

  const handleChange = (value: AgentPermissionMode) => {
    if (value === mode) return
    if (value === 'full') {
      modal.confirm({
        title: '开启完全访问模式？',
        content:
          '开启后所有工具（含远程命令、部署与实验操作）将自动执行、不再逐次询问；仅破坏性命令黑名单仍会要求确认。确定继续？',
        okText: '开启完全访问',
        okButtonProps: { danger: true },
        cancelText: '取消',
        onOk: () => updateMode('full'),
      })
      return
    }
    void updateMode(value)
  }

  if (!loaded && error) {
    return (
      <Tooltip title={`权限加载失败：${error}，点击重试`}>
        <span
          onClick={() => reload()}
          style={{ cursor: 'pointer', display: 'inline-flex' }}
          role="button"
        >
          <Select
            size="small"
            disabled
            className={`${styles.permissionSelect} ${styles.permissionSelectDanger}`}
            value={undefined}
            placeholder="权限加载失败，点击重试"
            style={{ minWidth: 168 }}
            options={MODE_OPTIONS}
            popupMatchSelectWidth={false}
          />
        </span>
      </Tooltip>
    )
  }

  return (
    <Tooltip title={MODE_HINTS[mode]}>
      <Select
        size="small"
        className={
          mode === 'full'
            ? `${styles.permissionSelect} ${styles.permissionSelectDanger}`
            : styles.permissionSelect
        }
        value={mode}
        onChange={handleChange}
        loading={!loaded && !error}
        options={MODE_OPTIONS}
        popupMatchSelectWidth={false}
      />
    </Tooltip>
  )
}
