import { useCallback, useEffect, useRef, useState } from 'react'
import {
  App as AntApp,
  Breadcrumb,
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  Progress,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Typography,
} from 'antd'
import type { TableProps } from 'antd'
import {
  CloudUploadOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  RocketOutlined,
} from '@ant-design/icons'
import {
  deployClone,
  deployUpload,
  deployUploadFiles,
  execCommand,
  monitorServer,
} from '../api'
import type { DiskInfo, GpuInfo, MonitorData, Server } from '../types'

const PRESET_COMMANDS = [
  { label: 'pip install -r requirements.txt', value: 'pip install -r requirements.txt' },
  { label: 'conda env list', value: 'conda env list' },
  { label: 'conda create -n openlab python=3.11 -y', value: 'conda create -n openlab python=3.11 -y' },
  { label: 'nvidia-smi', value: 'nvidia-smi' },
  { label: 'python --version', value: 'python --version' },
  { label: 'ls -la', value: 'ls -la' },
]

interface CloneFormValues {
  repo_url: string
  target_dir: string
}

interface LocalPathFormValues {
  local_path: string
  remote_path: string
}

function MonitorSection({ server }: { server: Server }) {
  const { message } = AntApp.useApp()
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<MonitorData | null>(null)

  const run = useCallback(async () => {
    setLoading(true)
    setData(null)
    try {
      setData(await monitorServer(server.id))
    } catch (e) {
      message.error(e instanceof Error ? e.message : '监控失败')
    } finally {
      setLoading(false)
    }
  }, [server.id, message])

  useEffect(() => {
    void run()
  }, [run])

  const gpuColumns: TableProps<GpuInfo>['columns'] = [
    { title: '序号', dataIndex: 'index', key: 'index', width: 70 },
    { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
    {
      title: '利用率',
      dataIndex: 'utilization',
      key: 'utilization',
      width: 220,
      render: (value: number) => <Progress percent={value} size="small" />,
    },
    {
      title: '显存 (MB)',
      key: 'memory',
      width: 180,
      render: (_: unknown, r) => `${r.memory_used_mb} / ${r.memory_total_mb}`,
    },
  ]

  const diskColumns: TableProps<DiskInfo>['columns'] = [
    { title: '文件系统', dataIndex: 'filesystem', key: 'filesystem', ellipsis: true },
    { title: '大小', dataIndex: 'size', key: 'size', width: 90 },
    { title: '已用', dataIndex: 'used', key: 'used', width: 90 },
    {
      title: '使用率',
      dataIndex: 'use_percent',
      key: 'use_percent',
      width: 200,
      render: (value: number | null | undefined) =>
        value == null ? '-' : <Progress percent={value} size="small" />,
    },
    { title: '挂载点', dataIndex: 'mount', key: 'mount', ellipsis: true },
  ]

  const memoryPercent =
    data?.memory && data.memory.total_mb > 0
      ? Math.round((data.memory.used_mb / data.memory.total_mb) * 100)
      : 0

  return (
    <Card
      title="监控"
      extra={
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void run()}>
          刷新
        </Button>
      }
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '24px 0' }}>
          <Spin tip="执行监控命令中..." />
        </div>
      ) : data ? (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Row gutter={16}>
            <Col xs={24} sm={8}>
              <Card size="small" title="CPU 负载">
                <Row gutter={8}>
                  <Col span={8}>
                    <Statistic title="1 分钟" value={data.load[0] ?? '-'} />
                  </Col>
                  <Col span={8}>
                    <Statistic title="5 分钟" value={data.load[1] ?? '-'} />
                  </Col>
                  <Col span={8}>
                    <Statistic title="15 分钟" value={data.load[2] ?? '-'} />
                  </Col>
                </Row>
              </Card>
            </Col>
            <Col xs={24} sm={8}>
              <Card size="small" title="内存">
                {data.memory ? (
                  <>
                    <Progress
                      percent={memoryPercent}
                      format={() =>
                        `${data.memory?.used_mb ?? 0} / ${data.memory?.total_mb ?? 0} MB`
                      }
                    />
                    <Typography.Text type="secondary">
                      已用 {data.memory.used_mb} MB / 共 {data.memory.total_mb} MB
                    </Typography.Text>
                  </>
                ) : (
                  <Typography.Text type="secondary">内存信息不可用</Typography.Text>
                )}
              </Card>
            </Col>
            <Col xs={24} sm={8}>
              <Card size="small" title="磁盘分区数">
                <Statistic value={data.disk.length} suffix="个" />
              </Card>
            </Col>
          </Row>

          <Card size="small" title="GPU">
            {data.gpu.length ? (
              <Table
                rowKey="index"
                columns={gpuColumns}
                dataSource={data.gpu}
                pagination={false}
                size="small"
              />
            ) : (
              <Typography.Text type="secondary">未检测到 GPU</Typography.Text>
            )}
          </Card>

          <Card size="small" title="磁盘">
            {data.disk.length ? (
              <Table
                rowKey={(r) => `${r.filesystem}-${r.mount}`}
                columns={diskColumns}
                dataSource={data.disk}
                pagination={false}
                size="small"
              />
            ) : (
              <Typography.Text type="secondary">磁盘信息不可用</Typography.Text>
            )}
          </Card>

          {data.processes.length > 0 && (
            <Card size="small" title="进程（按内存占用排序）">
              <pre
                style={{
                  margin: 0,
                  maxHeight: 240,
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap',
                  fontSize: 12,
                }}
              >
                {data.processes.join('\n')}
              </pre>
            </Card>
          )}

          {Object.keys(data.raw).length > 0 && (
            <Card size="small" title="原始输出（解析失败项）">
              {Object.entries(data.raw).map(([key, value]) => (
                <div key={key} style={{ marginBottom: 12 }}>
                  <Typography.Text strong>{key}</Typography.Text>
                  <pre
                    style={{
                      margin: '4px 0 0',
                      padding: 8,
                      background: '#f5f5f5',
                      maxHeight: 240,
                      overflow: 'auto',
                      whiteSpace: 'pre-wrap',
                      fontSize: 12,
                    }}
                  >
                    {value}
                  </pre>
                </div>
              ))}
            </Card>
          )}
        </Space>
      ) : (
        <Typography.Text type="secondary">暂无监控结果。</Typography.Text>
      )}
    </Card>
  )
}

function DeploySection({ server }: { server: Server }) {
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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
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

  const totalSize = selectedFiles.reduce((sum, f) => sum + f.size, 0)

  return (
    <Card title="部署">
      <Typography.Title level={5}>git clone</Typography.Title>
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
      {cloneOutput && (
        <pre
          style={{
            marginTop: 12,
            padding: 8,
            background: '#f5f5f5',
            maxHeight: 240,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
          }}
        >
          {cloneOutput}
        </pre>
      )}

      <Divider />

      <Typography.Title level={5}>SFTP 上传（本地路径）</Typography.Title>
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

      <Typography.Title level={5}>SFTP 上传（文件 / 文件夹选择）</Typography.Title>
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
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
          <input
            ref={dirInputRef}
            type="file"
            {...({ webkitdirectory: '' } as Record<string, string>)}
            multiple
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
        </Form.Item>
        {selectedFiles.length > 0 && (
          <div
            style={{
              maxHeight: 180,
              overflow: 'auto',
              background: '#fafafa',
              padding: 8,
              borderRadius: 4,
            }}
          >
            <Typography.Text type="secondary">
              已选 {selectedFiles.length} 个文件，共 {(totalSize / 1024).toFixed(1)} KB
            </Typography.Text>
            {selectedFiles.map((f, i) => {
              const rel = (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name
              return (
                <div key={`${rel}-${i}`} style={{ fontSize: 12 }}>
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

function ExecSection({ server }: { server: Server }) {
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
    <Card title="环境配置">
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Select
          allowClear
          placeholder="选择预设命令"
          options={PRESET_COMMANDS}
          style={{ width: '100%' }}
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
        {output !== '' && (
          <pre
            style={{
              margin: 0,
              padding: 8,
              background: '#f5f5f5',
              maxHeight: 320,
              overflow: 'auto',
              whiteSpace: 'pre-wrap',
            }}
          >
            {output}
          </pre>
        )}
      </Space>
    </Card>
  )
}

interface ServerDetailPageProps {
  server: Server
  onBack: () => void
}

export default function ServerDetailPage({ server, onBack }: ServerDetailPageProps) {
  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
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
      <Typography.Title level={4} style={{ margin: 0 }}>
        {server.name}
      </Typography.Title>
      <MonitorSection server={server} />
      <DeploySection server={server} />
      <ExecSection server={server} />
    </Space>
  )
}
