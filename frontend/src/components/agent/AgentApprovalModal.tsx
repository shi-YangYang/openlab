import { Button, Collapse, Modal, Typography } from 'antd'
import type { AgentPendingApproval } from '../../types'
import { formatValue } from './AgentChatMessages'
import styles from './AgentPage.module.css'

interface AgentApprovalModalProps {
  pendingApproval: AgentPendingApproval | null
  onApprove: (approve: boolean) => void
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
  const approvalCommand = pendingApproval ? extractCommand(pendingApproval.args) : null
  const argsText = pendingApproval ? formatValue(pendingApproval.args) : ''

  return (
    <Modal
      title="危险命令确认"
      open={!!pendingApproval}
      closable={false}
      maskClosable={false}
      footer={[
        <Button key="reject" danger disabled={offline} onClick={() => onApprove(false)}>
          拒绝
        </Button>,
        <Button key="allow" type="primary" disabled={offline} onClick={() => onApprove(true)}>
          允许执行
        </Button>,
      ]}
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
    </Modal>
  )
}
