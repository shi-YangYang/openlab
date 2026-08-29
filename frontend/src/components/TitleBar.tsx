import { useState } from 'react'
import type { CSSProperties } from 'react'
import { Button, Space, Typography } from 'antd'
import { MinusOutlined, CloseOutlined, BorderOutlined, SwitcherOutlined, RobotOutlined } from '@ant-design/icons'

export default function TitleBar() {
  const isElectron = !!window.electronAPI
  const [isMaximized, setIsMaximized] = useState(false)
  if (!isElectron) return null

  const handleMaximize = () => {
    window.electronAPI?.maximize()
    // Toggle state optimistically; actual state syncs on next render
    setIsMaximized((prev) => !prev)
  }

  return (
    <div
      className="titlebar-drag"
      style={{
        height: 36,
        background: '#001529',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 12px',
        WebkitAppRegion: 'drag',
      } as CSSProperties}
    >
      <Space size={8} style={{ WebkitAppRegion: 'no-drag' } as CSSProperties}>
        <RobotOutlined style={{ color: '#fff', fontSize: 18 }} />
        <Typography.Text strong style={{ color: '#fff', fontSize: 13 }}>
          openlab
        </Typography.Text>
      </Space>
      <Space size={0} style={{ WebkitAppRegion: 'no-drag' } as CSSProperties}>
        <Button
          type="text"
          size="small"
          icon={<MinusOutlined style={{ color: '#fff' }} />}
          onClick={() => window.electronAPI?.minimize()}
          style={{ minWidth: 36 }}
        />
        <Button
          type="text"
          size="small"
          icon={
            isMaximized ? (
              <SwitcherOutlined style={{ color: '#fff' }} />
            ) : (
              <BorderOutlined style={{ color: '#fff' }} />
            )
          }
          onClick={handleMaximize}
          style={{ minWidth: 36 }}
        />
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined style={{ color: '#fff' }} />}
          onClick={() => window.electronAPI?.quit()}
          style={{ minWidth: 36 }}
        />
      </Space>
    </div>
  )
}
