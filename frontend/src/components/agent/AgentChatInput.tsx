import { useCallback, useRef } from 'react'
import type { ChangeEvent, DragEvent, KeyboardEvent, ReactNode } from 'react'
import { Button, Divider, Input, Popover, Space, Tag, Typography } from 'antd'
import { PlusOutlined, SendOutlined, StopOutlined } from '@ant-design/icons'
import type { AgentPendingApproval } from '../../types'
import type { ConnectionState } from '../../hooks/useAgentChannel'
import styles from './AgentPage.module.css'

interface AgentChatInputProps {
  input: string
  setInput: (value: string) => void
  onSend: () => void
  onStop: () => void
  onUploadFiles: (files: File[]) => void
  uploadedFiles: string[]
  onRemoveFile: (path: string) => void
  running: boolean
  loading: boolean
  offline: boolean
  pendingApproval: AgentPendingApproval | null
  uploading: boolean
  connectionState: ConnectionState
  dragOver: boolean
  onDragOver: (e: DragEvent<HTMLDivElement>) => void
  onDragLeave: (e: DragEvent<HTMLDivElement>) => void
  onDrop: (e: DragEvent<HTMLDivElement>) => void
  configBar: ReactNode
}

export default function AgentChatInput({
  input,
  setInput,
  onSend,
  onStop,
  onUploadFiles,
  uploadedFiles,
  onRemoveFile,
  running,
  loading,
  offline,
  pendingApproval,
  uploading,
  connectionState,
  dragOver,
  onDragOver,
  onDragLeave,
  onDrop,
  configBar,
}: AgentChatInputProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const dirInputRef = useRef<HTMLInputElement | null>(null)

  const attachDirectoryInput = useCallback((el: HTMLInputElement | null) => {
    dirInputRef.current = el
    if (el) el.setAttribute('webkitdirectory', '')
  }, [])

  const handleInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
  }

  const handleInputPressEnter = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (!e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  const handleFileInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    e.target.value = ''
    onUploadFiles(files)
  }

  const uploadMenu = (
    <div className={styles.uploadMenu}>
      <Button size="small" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
        添加文件 / 文件夹
      </Button>
      <Divider className={styles.uploadMenuDivider} />
      <Typography.Text type="secondary" className={styles.uploadMenuHint}>
        更多功能开发中…
      </Typography.Text>
    </div>
  )

  return (
    <div className={styles.inputArea}>
      {uploadedFiles.length > 0 && (
        <div className={styles.filesRow}>
          {uploadedFiles.map((p) => (
            <Tag
              key={p}
              closable
              color={/\.(png|jpe?g|gif|webp|bmp)$/i.test(p) ? 'cyan' : undefined}
              onClose={() => onRemoveFile(p)}
            >
              {p}
            </Tag>
          ))}
        </div>
      )}
      <div
        className={dragOver ? `${styles.dropZone} ${styles.dropZoneActive}` : styles.dropZone}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <Input.TextArea
          value={input}
          onChange={handleInputChange}
          onPressEnter={handleInputPressEnter}
          placeholder={
            connectionState === 'reconnecting' || connectionState === 'closed'
              ? '连接不可用，等待恢复…'
              : dragOver
                ? '松开鼠标即可添加文件'
                : '输入目标后按 Enter 发送（Shift+Enter 换行），也可拖入文件'
          }
          autoSize={{ minRows: 4, maxRows: 10 }}
          disabled={offline || running || !!pendingApproval}
        />
      </div>
      <div className={styles.toolbar}>
        <Popover content={uploadMenu} trigger="click">
          <Button size="small" icon={<PlusOutlined />} loading={uploading} />
        </Popover>
        {configBar}
        <div className={styles.toolbarSpacer} />
        {running && !offline ? (
          <Button danger icon={<StopOutlined />} onClick={onStop} disabled={uploading}>
            停止
          </Button>
        ) : (
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={onSend}
            loading={loading}
            disabled={offline || !!pendingApproval || uploading}
          >
            发送
          </Button>
        )}
      </div>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className={styles.hiddenInput}
        onChange={handleFileInputChange}
      />
      <input
        ref={attachDirectoryInput}
        type="file"
        multiple
        className={styles.hiddenInput}
        onChange={handleFileInputChange}
      />
    </div>
  )
}
