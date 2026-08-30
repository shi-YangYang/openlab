import { useState } from 'react'
import { Button, Space, Typography } from 'antd'
import { MinusOutlined, CloseOutlined, BorderOutlined, SwitcherOutlined, RobotOutlined } from '@ant-design/icons'
import styles from './TitleBar.module.css'

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
    <div className={`titlebar-drag ${styles.bar}`}>
      <Space size={8} className={styles.noDrag}>
        <RobotOutlined className={styles.brandIcon} />
        <Typography.Text strong className={styles.brandText}>
          openlab
        </Typography.Text>
      </Space>
      <Space size={0} className={styles.noDrag}>
        <Button
          type="text"
          size="small"
          icon={<MinusOutlined className={styles.btnIcon} />}
          onClick={() => window.electronAPI?.minimize()}
          className={styles.winBtn}
        />
        <Button
          type="text"
          size="small"
          icon={
            isMaximized ? (
              <SwitcherOutlined className={styles.btnIcon} />
            ) : (
              <BorderOutlined className={styles.btnIcon} />
            )
          }
          onClick={handleMaximize}
          className={styles.winBtn}
        />
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined className={styles.btnIcon} />}
          onClick={() => window.electronAPI?.quit()}
          className={styles.winBtn}
        />
      </Space>
    </div>
  )
}
