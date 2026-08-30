import { useState } from 'react'
import { App as AntApp, Button, Card, Input, Select, Space } from 'antd'
import { PlayCircleOutlined } from '@ant-design/icons'
import { execCommand } from '../../api'
import type { Server } from '../../types'
import styles from './ServerDetailPage.module.css'

const PRESET_COMMANDS = [
  { label: 'pip install -r requirements.txt', value: 'pip install -r requirements.txt' },
  { label: 'conda env list', value: 'conda env list' },
  { label: 'conda create -n openlab python=3.11 -y', value: 'conda create -n openlab python=3.11 -y' },
  { label: 'nvidia-smi', value: 'nvidia-smi' },
  { label: 'python --version', value: 'python --version' },
  { label: 'ls -la', value: 'ls -la' },
]

interface ExecSectionProps {
  server: Server
}

export default function ExecSection({ server }: ExecSectionProps) {
  const { message } = AntApp.useApp()
  const [command, setCommand] = useState('')
  const [output, setOutput] = useState('')
  const [running, setRunning] = useState(false)

  const handleExec = async () => {
    if (!command.trim()) {
      message.error('请输入命令')
      return
    }
    setRunning(true)
    setOutput('')
    try {
      const res = await execCommand(server.id, command)
      setOutput(res.output || '（命令执行成功，无输出）')
    } catch (e) {
      setOutput(`执行失败：${e instanceof Error ? e.message : '未知错误'}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <Card>
      <Space direction="vertical" size={12} className={styles.fullWidth}>
        <Select
          allowClear
          placeholder="选择预设命令"
          options={PRESET_COMMANDS}
          className={styles.fullWidth}
          onChange={(value) => {
            if (value) setCommand(value)
          }}
        />
        <Input.TextArea
          rows={3}
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          placeholder="自定义命令，例如：pip install torch"
        />
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          loading={running}
          onClick={() => void handleExec()}
        >
          执行命令
        </Button>
        {output !== '' && <pre className={styles.outputPre}>{output}</pre>}
      </Space>
    </Card>
  )
}
