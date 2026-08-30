import { useRef, useState, type ChangeEvent } from 'react'
import { App as AntApp, Button, Card, Divider, Form, Input, Space, Typography } from 'antd'
import { CloudUploadOutlined, RocketOutlined } from '@ant-design/icons'
import { deployClone, deployUpload, deployUploadFiles } from '../../api'
import type { Server } from '../../types'
import styles from './ServerDetailPage.module.css'

interface CloneFormValues {
  repo_url: string
  target_dir: string
}

interface LocalPathFormValues {
  local_path: string
  remote_path: string
}

interface DeploySectionProps {
  server: Server
}

export default function DeploySection({ server }: DeploySectionProps) {
  const { message } = AntApp.useApp()
  const [cloneForm] = Form.useForm<CloneFormValues>()
  const [pathForm] = Form.useForm<LocalPathFormValues>()
  const [cloning, setCloning] = useState(false)
  const [uploadingPath, setUploadingPath] = useState(false)
  const [cloneOutput, setCloneOutput] = useState('')
  const [remotePath, setRemotePath] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [uploadingFiles, setUploadingFiles] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const dirInputRef = useRef<HTMLInputElement>(null)

  const totalSize = selectedFiles.reduce((sum, f) => sum + f.size, 0)

  const handleClone = async (values: CloneFormValues) => {
    setCloning(true)
    setCloneOutput('')
    try {
      const res = await deployClone(server.id, values)
      setCloneOutput(res.output)
      message.success('git clone 已执行')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '部署失败')
    } finally {
      setCloning(false)
    }
  }

  const handlePathUpload = async (values: LocalPathFormValues) => {
    setUploadingPath(true)
    try {
      const res = await deployUpload(server.id, values)
      message.success(`上传完成，共 ${res.files} 个文件`)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '上传失败')
    } finally {
      setUploadingPath(false)
    }
  }

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setSelectedFiles(Array.from(e.target.files ?? []))
  }

  const handleFilesUpload = async () => {
    if (!remotePath.trim()) {
      message.error('请输入远程路径')
      return
    }
    if (selectedFiles.length === 0) {
      message.error('请先选择要上传的文件或文件夹')
      return
    }
    setUploadingFiles(true)
    try {
      const res = await deployUploadFiles(server.id, selectedFiles, remotePath.trim())
      message.success(`上传完成，共 ${res.files} 个文件`)
      setSelectedFiles([])
      if (fileInputRef.current) fileInputRef.current.value = ''
      if (dirInputRef.current) dirInputRef.current.value = ''
    } catch (err) {
      message.error(err instanceof Error ? err.message : '上传失败')
    } finally {
      setUploadingFiles(false)
    }
  }

  return (
    <Card>
      <div className="section-title">git clone</div>
      <Form form={cloneForm} layout="vertical" onFinish={handleClone}>
        <Form.Item
          name="repo_url"
          label="仓库地址"
          rules={[{ required: true, message: '请输入仓库地址' }]}
        >
          <Input placeholder="https://github.com/org/repo.git" />
        </Form.Item>
        <Form.Item
          name="target_dir"
          label="目标目录"
          rules={[{ required: true, message: '请输入目标目录' }]}
        >
          <Input placeholder="/home/user/project" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={cloning} icon={<RocketOutlined />}>
          执行 git clone
        </Button>
      </Form>
      {cloneOutput && <pre className={styles.clonePre}>{cloneOutput}</pre>}

      <Divider />

      <div className="section-title">SFTP 上传（本地路径）</div>
      <Form form={pathForm} layout="vertical" onFinish={handlePathUpload}>
        <Form.Item
          name="local_path"
          label="本地路径（文件或目录）"
          rules={[{ required: true, message: '请输入本地路径' }]}
        >
          <Input placeholder="E:\\gitTools\\openlab\\backend" />
        </Form.Item>
        <Form.Item
          name="remote_path"
          label="远程路径"
          rules={[{ required: true, message: '请输入远程路径' }]}
        >
          <Input placeholder="/home/user/project" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={uploadingPath}>
          开始上传
        </Button>
      </Form>

      <Divider />

      <div className="section-title">SFTP 上传（文件 / 文件夹选择）</div>
      <Form layout="vertical">
        <Form.Item label="远程路径" required>
          <Input
            value={remotePath}
            onChange={(e) => setRemotePath(e.target.value)}
            placeholder="/home/user/project"
          />
        </Form.Item>
        <Form.Item label="选择文件 / 文件夹">
          <Space wrap>
            <Button icon={<CloudUploadOutlined />} onClick={() => fileInputRef.current?.click()}>
              选择文件
            </Button>
            <Button icon={<CloudUploadOutlined />} onClick={() => dirInputRef.current?.click()}>
              选择文件夹
            </Button>
            <Button type="primary" loading={uploadingFiles} onClick={() => void handleFilesUpload()}>
              上传选中内容
            </Button>
          </Space>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className={styles.hiddenInput}
            onChange={handleFileChange}
          />
          <input
            ref={dirInputRef}
            type="file"
            {...({ webkitdirectory: '' } as Record<string, string>)}
            multiple
            className={styles.hiddenInput}
            onChange={handleFileChange}
          />
        </Form.Item>
        {selectedFiles.length > 0 && (
          <div className={styles.fileListBox}>
            <Typography.Text type="secondary">
              已选 {selectedFiles.length} 个文件，共 {(totalSize / 1024).toFixed(1)} KB
            </Typography.Text>
            {selectedFiles.map((f, i) => {
              const rel = (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name
              return (
                <div key={`${rel}-${i}`} className={styles.fileItem}>
                  {rel}
                </div>
              )
            })}
          </div>
        )}
      </Form>
    </Card>
  )
}
