import { Breadcrumb, Collapse, Space, Typography } from 'antd'
import type { Server } from '../../types'
import MonitorSection from './MonitorSection'
import DeploySection from './DeploySection'
import ExecSection from './ExecSection'
import TerminalView from '../Terminal'
import styles from './ServerDetailPage.module.css'

interface ServerDetailPageProps {
  server: Server
  onBack: () => void
}

export default function ServerDetailPage({ server, onBack }: ServerDetailPageProps) {
  return (
    <Space direction="vertical" size={16} className={styles.fullWidth}>
      <Breadcrumb
        items={[
          {
            title: (
              <a
                onClick={(e) => {
                  e.preventDefault()
                  onBack()
                }}
              >
                服务器列表
              </a>
            ),
          },
          { title: server.name },
        ]}
      />
      <Typography.Title level={4} className={styles.pageTitle}>
        {server.name}
      </Typography.Title>
      <Collapse
        defaultActiveKey={[]}
        items={[
          { key: 'monitor', label: '监控', children: <MonitorSection server={server} /> },
          { key: 'deploy', label: '部署', children: <DeploySection server={server} /> },
          { key: 'exec', label: '环境配置', children: <ExecSection server={server} /> },
          {
            key: 'terminal',
            label: '终端',
            children: <TerminalView path={`/api/servers/${server.id}/terminal`} />,
          },
        ]}
      />
    </Space>
  )
}
