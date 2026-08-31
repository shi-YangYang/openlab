import { Button, Collapse, Modal, Typography } from 'antd'
import type { AgentApprovalScope, AgentPendingApproval } from '../../types'
import { formatValue } from './AgentChatMessages'
import styles from './AgentPage.module.css'

interface AgentApprovalModalProps {
  pendingApproval: AgentPendingApproval | null
  onApprove: (approve: boolean, scope: AgentApprovalScope) => void
  offline: boolean
}

function extractCommand(args: unknown): string | null {
  if (!args || typeof args !== 'object') return null
  const obj = args as Record<string, unknown>
  if (typeof obj.command === 'string' && obj.command.trim()) return obj.command
  const nested = obj.args
  if (nested && typeof nested === 'object') {
    const command = (nested as Record<string, unknown>).command
    if (typeof command === 'string' && command.trim()) return command
  }
  return null
}

export default function AgentApprovalModal({
  pendingApproval,
  onApprove,
  offline,
}: AgentApprovalModalProps) {
  const forbidden = !!pendingApproval?.forbidden
  const approvalCommand = pendingApproval ? extractCommand(pendingApproval.args) : null
  const argsText = pendingApproval ? formatValue(pendingApproval.args) : ''

  const footer = [
    <Button key="reject" danger disabled={offline} onClick={() => onApprove(false, 'once')}>
      拒绝
    </Button>,
  ]
  if (!forbidden) {
    footer.push(
      <Button
        key="session"
        disabled={offline}
        onClick={() => onApprove(true, 'session')}
        title="本次会话内该工具不再询问（破坏性命令黑名单除外）"
      >
        本会话允许
      </Button>,
    )
  }
  footer.push(
    <Button key="once" type="primary" disabled={offline} onClick={() => onApprove(true, 'once')}>
      允许一次
    </Button>,
  )

  return (
    <Modal
      title="危险命令确认"
      open={!!pendingApproval}
      closable={false}
      maskClosable={false}
      footer={footer}
    >
      <Typography.Paragraph>
        Agent 想执行危险操作
        <Typography.Text code>{pendingApproval?.tool}</Typography.Text>
        ，请确认以下参数：
      </Typography.Paragraph>
      {approvalCommand ? (
        <>
          <pre className="code-block">{approvalCommand}</pre>
          <Collapse
            ghost
            size="small"
            items={[
              {
                key: 'full-args',
                label: '完整参数',
                children: <pre className={styles.argsPre}>{argsText}</pre>,
              },
            ]}
          />
        </>
      ) : (
        <pre className={styles.argsPre}>{argsText}</pre>
      )}
      {forbidden ? (
        <Typography.Text type="warning" style={{ display: 'block', marginTop: 12, fontSize: 12 }}>
          该操作命中安全底线，每次都需确认
        </Typography.Text>
      ) : (
        <Typography.Text type="secondary" style={{ display: 'block', marginTop: 12, fontSize: 12 }}>
          不想再被询问？可在设置或工具栏切换为完全访问模式
        </Typography.Text>
      )}
    </Modal>
  )
}
