import { useCallback, useEffect, useState } from 'react'
import {
  App as AntApp,
  Button,
  Card,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { TableProps } from 'antd'
import {
  ApiOutlined,
  DeleteOutlined,
  EditOutlined,
  MonitorOutlined,
  PlusOutlined,
  ReloadOutlined,
  RocketOutlined,
} from '@ant-design/icons'
import {
  createServer,
  deleteServer,
  deployClone,
  deployUpload,
  listServers,
  monitorServer,
  testServer,
  updateServer,
} from '../api'
import type { MonitorResult, Server, ServerAuthType, ServerInput } from '../types'

interface ServerFormValues {
  name: string
  host: string
  username: string
  port: number
  auth_type: ServerAuthType
  password?: string
  private_key?: string
}

interface CloneFormValues {
  repo_url: string
  target_dir: string
}

interface UploadFormValues {
  local_path: string
  remote_path: string
}

const AUTH_META: Record<string, { color: string; label: string }> = {
  password: { color: 'blue', label: '密码' },
  key: { color: 'green', label: '密钥' },
}

function DeployModal({ server, onClose }: { server: Server; onClose: () => void }) {
  const { message } = AntApp.useApp()
  const [cloneForm] = Form.useForm<CloneFormValues>()
  const [uploadForm] = Form.useForm<UploadFormValues>()
  const [cloning, setCloning] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [cloneOutput, setCloneOutput] = useState('')
  const [uploadResult, setUploadResult] = useState('')

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

  const handleUpload = async (values: UploadFormValues) => {
    setUploading(true)
    setUploadResult('')
    try {
      const res = await deployUpload(server.id, values)
      setUploadResult(`上传完成，共 ${res.files} 个文件`)
      message.success('上传完成')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }

  return (
    <Modal title={`部署到 ${server.name}`} open onCancel={onClose} footer={null} width={720}>
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
        <Button type="primary" htmlType="submit" loading={cloning}>
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

      <Typography.Title level={5}>SFTP 上传</Typography.Title>
      <Form form={uploadForm} layout="vertical" onFinish={handleUpload}>
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
        <Button type="primary" htmlType="submit" loading={uploading}>
          开始上传
        </Button>
      </Form>
      {uploadResult && (
        <Typography.Text style={{ display: 'block', marginTop: 12 }}>
          {uploadResult}
        </Typography.Text>
      )}
    </Modal>
  )
}

function MonitorModal({ server, onClose }: { server: Server; onClose: () => void }) {
  const { message } = AntApp.useApp()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<MonitorResult | null>(null)

  const run = useCallback(async () => {
    setLoading(true)
    setResult(null)
    try {
      setResult(await monitorServer(server.id))
    } catch (e) {
      message.error(e instanceof Error ? e.message : '监控失败')
    } finally {
      setLoading(false)
    }
  }, [server.id, message])

  useEffect(() => {
    void run()
  }, [run])

  return (
    <Modal
      title={`监控 ${server.name}`}
      open
      onCancel={onClose}
      footer={
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void run()}>
          重新执行
        </Button>
      }
      width={860}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '24px 0' }}>
          <Spin tip="执行监控命令中..." />
        </div>
      ) : result ? (
        Object.entries(result).map(([name, output]) => (
          <Card key={name} size="small" title={name} style={{ marginBottom: 12 }}>
            <pre
              style={{
                margin: 0,
                maxHeight: 240,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
              }}
            >
              {output}
            </pre>
          </Card>
        ))
      ) : (
        <Typography.Text type="secondary">暂无监控结果。</Typography.Text>
      )}
    </Modal>
  )
}

export default function ServersPage() {
  const { message } = AntApp.useApp()
  const [items, setItems] = useState<Server[]>([])
  const [loading, setLoading] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Server | null>(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm<ServerFormValues>()
  const [testingId, setTestingId] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<string>('')
  const [deployTarget, setDeployTarget] = useState<Server | null>(null)
  const [monitorTarget, setMonitorTarget] = useState<Server | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await listServers())
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载服务器列表失败')
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => {
    void load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ port: 22, auth_type: 'password' })
    setFormOpen(true)
  }

  const openEdit = (server: Server) => {
    setEditing(server)
    form.resetFields()
    form.setFieldsValue({
      name: server.name,
      host: server.host,
      username: server.username,
      port: server.port,
      auth_type: server.auth_type,
      password: '',
      private_key: '',
    })
    setFormOpen(true)
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      const payload: ServerInput = {
        name: values.name,
        host: values.host,
        username: values.username,
        port: values.port,
        auth_type: values.auth_type,
      }
      if (values.password) payload.password = values.password
      if (values.private_key) payload.private_key = values.private_key
      if (editing) {
        await updateServer(editing.id, payload)
        message.success('服务器已更新')
      } else {
        await createServer(payload)
        message.success('服务器已添加')
      }
      setFormOpen(false)
      void load()
    } catch (e) {
      if (e instanceof Error) message.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (server: Server) => {
    try {
      await deleteServer(server.id)
      message.success('已删除')
      void load()
    } catch (e) {
      message.error(e instanceof Error ? e.message : '删除失败')
    }
  }

  const handleTest = async (server: Server) => {
    setTestingId(server.id)
    setTestResult('')
    try {
      const result = await testServer(server.id)
      if (result.ok) {
        setTestResult(`${server.name}：连接成功，耗时 ${result.latency_ms ?? '-'} ms`)
        message.success(`${server.name} 连接成功`)
      } else {
        setTestResult(`${server.name}：${result.message}`)
        message.error(result.message || '连接失败')
      }
    } catch (e) {
      message.error(e instanceof Error ? e.message : '测试连接失败')
    } finally {
      setTestingId(null)
    }
  }

  const columns: TableProps<Server>['columns'] = [
    { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
    { title: '主机', dataIndex: 'host', key: 'host', ellipsis: true },
    { title: '端口', dataIndex: 'port', key: 'port', width: 80 },
    { title: '用户', dataIndex: 'username', key: 'username', width: 120 },
    {
      title: '认证方式',
      dataIndex: 'auth_type',
      key: 'auth_type',
      width: 110,
      render: (auth: string) => {
        const meta = AUTH_META[auth] ?? { color: 'default', label: auth }
        return <Tag color={meta.color}>{meta.label}</Tag>
      },
    },
    {
      title: '凭据',
      key: 'credential',
      width: 150,
      render: (_: unknown, r) => (
        <Space size={4}>
          {r.has_password && <Tag>密码已配置</Tag>}
          {r.has_key && <Tag>私钥已配置</Tag>}
          {!r.has_password && !r.has_key && (
            <Typography.Text type="secondary">未配置</Typography.Text>
          )}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 320,
      render: (_: unknown, r) => (
        <Space size={4} wrap>
          <Button
            size="small"
            loading={testingId === r.id}
            icon={<ApiOutlined />}
            onClick={() => void handleTest(r)}
          >
            测试
          </Button>
          <Button size="small" icon={<RocketOutlined />} onClick={() => setDeployTarget(r)}>
            部署
          </Button>
          <Button size="small" icon={<MonitorOutlined />} onClick={() => setMonitorTarget(r)}>
            监控
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>
            编辑
          </Button>
          <Popconfirm title="确认删除该服务器？" onConfirm={() => void handleDelete(r)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Card
      title="服务器"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          添加服务器
        </Button>
      }
    >
      <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
        服务器凭据（密码/私钥）保存在本地文件中，列表展示已脱敏，不会返回明文。
      </Typography.Text>
      {testResult && (
        <Typography.Text style={{ display: 'block', marginBottom: 12 }}>
          {testResult}
        </Typography.Text>
      )}
      <Table
        rowKey="id"
        dataSource={items}
        columns={columns}
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: false }}
        size="middle"
      />

      <Modal
        title={editing ? '编辑服务器' : '添加服务器'}
        open={formOpen}
        onCancel={() => setFormOpen(false)}
        onOk={() => void handleSave()}
        confirmLoading={saving}
        width={640}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="gpu-01" />
          </Form.Item>
          <Form.Item
            name="host"
            label="主机"
            rules={[{ required: true, message: '请输入主机地址' }]}
          >
            <Input placeholder="10.0.0.1 或 example.com" />
          </Form.Item>
          <Space size={12} style={{ display: 'flex' }}>
            <Form.Item name="port" label="端口" rules={[{ required: true, message: '端口' }]}>
              <InputNumber min={1} max={65535} style={{ width: 140 }} />
            </Form.Item>
            <Form.Item
              name="username"
              label="用户名"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input placeholder="root" />
            </Form.Item>
          </Space>
          <Form.Item
            name="auth_type"
            label="认证方式"
            rules={[{ required: true, message: '请选择认证方式' }]}
          >
            <Select
              options={[
                { value: 'password', label: '密码' },
                { value: 'key', label: '私钥' },
              ]}
            />
          </Form.Item>
          <Form.Item noStyle shouldUpdate>
            {() =>
              form.getFieldValue('auth_type') === 'key' ? (
                <Form.Item name="private_key" label="私钥内容">
                  <Input.TextArea
                    rows={4}
                    autoComplete="off"
                    placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                  />
                </Form.Item>
              ) : (
                <Form.Item name="password" label="密码">
                  <Input.Password autoComplete="off" placeholder="留空表示不修改" />
                </Form.Item>
              )
            }
          </Form.Item>
        </Form>
      </Modal>

      {deployTarget && (
        <DeployModal server={deployTarget} onClose={() => setDeployTarget(null)} />
      )}
      {monitorTarget && (
        <MonitorModal server={monitorTarget} onClose={() => setMonitorTarget(null)} />
      )}
    </Card>
  )
}
