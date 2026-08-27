import { useEffect, useState } from 'react'
import {
  App as AntApp,
  Button,
  Form,
  Input,
  InputNumber,
  List,
  Select,
  Space,
  Tag,
  Typography,
} from 'antd'
import {
  ApiOutlined,
  CloudDownloadOutlined,
  DeleteOutlined,
  PlusOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import {
  getLlmConfig,
  getLlmModels,
  getLlmPresets,
  saveLlmConfig,
  testLlmConnection,
} from '../api'
import type {
  LlmGroup,
  LlmGroupsConfig,
  LlmModelInfo,
  LlmPreset,
  LlmTestResult,
} from '../types'

interface GroupFormValues {
  name?: string
  base_url?: string
  api_key?: string
}

let groupSeq = 0
function newGroupId(): string {
  groupSeq += 1
  return `group-${Date.now().toString(36)}-${groupSeq}`
}

function emptyGroup(): LlmGroup {
  return {
    id: newGroupId(),
    name: '',
    base_url: '',
    api_key: '',
    models: [],
    default_model: '',
  }
}

function emptyModel(): LlmModelInfo {
  return { id: '', context_length: null, reasoning_efforts: [] }
}

export default function LlmConfigForm() {
  const { message } = AntApp.useApp()
  const [form] = Form.useForm<GroupFormValues>()
  const [presets, setPresets] = useState<LlmPreset[]>([])
  const [groups, setGroups] = useState<LlmGroup[]>([])
  const [activeGroup, setActiveGroup] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [loadingModels, setLoadingModels] = useState(false)
  const [testResult, setTestResult] = useState<LlmTestResult | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([getLlmPresets(), getLlmConfig()])
      .then(([ps, cfg]) => {
        if (cancelled) return
        setPresets(ps)
        setGroups(cfg.groups)
        setActiveGroup(cfg.active_group)
        const target = cfg.active_group || cfg.groups[0]?.id || null
        setSelectedId(target)
        loadGroupIntoForm(cfg.groups.find((g) => g.id === target) ?? cfg.groups[0])
      })
      .catch(() => {
        message.error('加载 LLM 配置失败')
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadGroupIntoForm = (group?: LlmGroup) => {
    if (!group) {
      form.resetFields()
      return
    }
    form.setFieldsValue({
      name: group.name,
      base_url: group.base_url,
      api_key: group.api_key,
    })
    setTestResult(null)
  }

  const currentGroup = groups.find((g) => g.id === selectedId)

  const handleValuesChange = (_changed: unknown, all: GroupFormValues) => {
    if (!selectedId) return
    setGroups((prev) =>
      prev.map((g) =>
        g.id === selectedId
          ? {
              ...g,
              name: all.name ?? '',
              base_url: all.base_url ?? '',
              api_key: all.api_key ?? '',
            }
          : g,
      ),
    )
  }

  const handleSelectGroup = (id: string) => {
    setSelectedId(id)
    loadGroupIntoForm(groups.find((g) => g.id === id))
  }

  const handleAddGroup = () => {
    const group = emptyGroup()
    setGroups((prev) => [...prev, group])
    setSelectedId(group.id)
    loadGroupIntoForm(group)
  }

  const handleDeleteGroup = (id: string) => {
    const remaining = groups.filter((g) => g.id !== id)
    if (remaining.length === 0) {
      message.warning('至少保留一个配置组')
      return
    }
    setGroups(remaining)
    if (activeGroup === id) {
      setActiveGroup(remaining[0].id)
    }
    if (selectedId === id) {
      setSelectedId(remaining[0].id)
      loadGroupIntoForm(remaining[0])
    }
  }

  const handlePresetFill = (presetName: string) => {
    const preset = presets.find((p) => p.name === presetName)
    if (!preset) return
    form.setFieldsValue({ base_url: preset.base_url })
    setGroups((prev) =>
      prev.map((g) =>
        g.id === selectedId
          ? {
              ...g,
              base_url: preset.base_url,
              models: g.models.length
                ? g.models
                : [{ id: preset.default_model, context_length: null, reasoning_efforts: [] }],
              default_model: g.default_model || preset.default_model,
            }
          : g,
      ),
    )
  }

  const updateModel = (index: number, patch: Partial<LlmModelInfo>) => {
    if (!selectedId) return
    setGroups((prev) =>
      prev.map((g) =>
        g.id === selectedId
          ? {
              ...g,
              models: g.models.map((m, i) => (i === index ? { ...m, ...patch } : m)),
            }
          : g,
      ),
    )
  }

  const addModel = () => {
    if (!selectedId) return
    setGroups((prev) =>
      prev.map((g) =>
        g.id === selectedId ? { ...g, models: [...g.models, emptyModel()] } : g,
      ),
    )
  }

  const removeModel = (index: number) => {
    if (!selectedId) return
    setGroups((prev) =>
      prev.map((g) => {
        if (g.id !== selectedId) return g
        const removed = g.models[index]
        const models = g.models.filter((_, i) => i !== index)
        const defaultModel =
          g.default_model === removed?.id ? (models[0]?.id ?? '') : g.default_model
        return { ...g, models, default_model: defaultModel }
      }),
    )
  }

  const setDefaultModel = (id: string) => {
    if (!selectedId) return
    setGroups((prev) =>
      prev.map((g) => (g.id === selectedId ? { ...g, default_model: id } : g)),
    )
  }

  const handleFetchModels = async () => {
    const group = groups.find((g) => g.id === selectedId)
    if (!group) return
    const baseUrl = (group.base_url || '').trim()
    if (!baseUrl) {
      message.warning('请先填写 Base URL')
      return
    }
    setLoadingModels(true)
    try {
      const fetched = await getLlmModels({ base_url: baseUrl, api_key: group.api_key ?? '' })
      setGroups((prev) =>
        prev.map((g) => {
          if (g.id !== selectedId) return g
          const merged = g.models.map((m) => ({ ...m }))
          for (const m of fetched) {
            if (!m.id) continue
            const existing = merged.find((x) => x.id === m.id)
            if (existing) {
              if (m.context_length != null) existing.context_length = m.context_length
              if (m.reasoning_efforts != null && m.reasoning_efforts.length > 0) {
                existing.reasoning_efforts = m.reasoning_efforts
              }
            } else {
              merged.push({
                id: m.id,
                context_length: m.context_length ?? null,
                reasoning_efforts: m.reasoning_efforts ?? [],
              })
            }
          }
          return { ...g, models: merged }
        }),
      )
      if (fetched.length) {
        message.success(`已获取 ${fetched.length} 个模型`)
      } else {
        message.info('未获取到模型，可手动添加模型')
      }
    } catch (e) {
      message.error(e instanceof Error ? e.message : '获取模型列表失败')
    } finally {
      setLoadingModels(false)
    }
  }

  const handleTest = async () => {
    const group = groups.find((g) => g.id === selectedId)
    if (!group) return
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testLlmConnection({
        base_url: group.base_url,
        api_key: group.api_key,
        model: group.default_model || group.models[0]?.id,
      })
      setTestResult(result)
      if (result.ok) {
        message.success('连通性测试通过')
      } else {
        message.error(result.message || '连通性测试失败')
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : '连通性测试失败'
      setTestResult({ ok: false, message: msg })
      message.error(msg)
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    if (!activeGroup) {
      message.warning('请选择当前使用组')
      return
    }
    const config: LlmGroupsConfig = {
      active_group: activeGroup,
      groups: groups.map((g) => ({
        ...g,
        models: g.models.filter((m) => m.id),
      })),
    }
    setSaving(true)
    try {
      await saveLlmConfig(config)
      window.localStorage.setItem('openlab.llm.updated', String(Date.now()))
      window.dispatchEvent(new Event('openlab:llm-updated'))
      message.success('LLM 配置已保存')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const defaultModelOptions = (currentGroup?.models ?? [])
    .filter((m) => m.id)
    .map((m) => ({ value: m.id, label: m.id }))

  return (
    <div>
      <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
        以「配置组」区分不同平台（OpenAI / 阿里云百炼 / DeepSeek 等）。每组可获取模型列表、测试连通性；
        「当前使用组」决定分析、实验、Agent 等默认使用的模型。每个模型可单独设置「上下文长度」与「思考强度」。
        思考强度为自由输入，按模型实际支持的取值填写（如 OpenAI 的 low/medium/high），可填多个。
      </Typography.Text>

      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        <div style={{ width: 260, flexShrink: 0 }}>
          <Space direction="vertical" style={{ width: '100%' }} size={8}>
            <Typography.Text strong>配置组</Typography.Text>
            <Button block icon={<PlusOutlined />} onClick={handleAddGroup}>
              新增配置组
            </Button>
            <List
              size="small"
              dataSource={groups}
              renderItem={(group) => (
                <List.Item
                  onClick={() => handleSelectGroup(group.id)}
                  style={{
                    cursor: 'pointer',
                    background: group.id === selectedId ? '#e6f4ff' : 'transparent',
                    borderRadius: 4,
                    paddingLeft: 8,
                    paddingRight: 8,
                  }}
                  actions={[
                    <Button
                      key="del"
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteGroup(group.id)
                      }}
                    />,
                  ]}
                >
                  <Space size={4} direction="vertical" style={{ width: '100%' }}>
                    <Space size={4}>
                      <Typography.Text ellipsis strong={group.id === activeGroup}>
                        {group.name || group.id}
                      </Typography.Text>
                      {group.id === activeGroup && <Tag color="blue">当前使用</Tag>}
                    </Space>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                      {group.default_model || '未设置默认模型'}
                    </Typography.Text>
                  </Space>
                </List.Item>
              )}
            />
          </Space>
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          {currentGroup ? (
            <Form
              form={form}
              layout="vertical"
              onValuesChange={handleValuesChange}
            >
              <Form.Item label="当前使用组">
                <Select
                  value={activeGroup}
                  onChange={(v) => setActiveGroup(v)}
                  options={groups.map((g) => ({ value: g.id, label: g.name || g.id }))}
                />
              </Form.Item>
              <Form.Item label="从预设填充（可选）">
                <Select
                  allowClear
                  placeholder="选择平台预设自动填充 Base URL 与模型"
                  options={presets.map((p) => ({ value: p.name, label: p.name }))}
                  onChange={(v) => v && handlePresetFill(v)}
                  value={undefined}
                />
              </Form.Item>
              <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
                <Input placeholder="例如：OpenAI / 阿里云百炼" />
              </Form.Item>
              <Form.Item
                name="base_url"
                label="Base URL（OpenAI 兼容）"
                rules={[{ required: true, message: '请输入 Base URL' }]}
              >
                <Input placeholder="https://api.openai.com/v1" />
              </Form.Item>
              <Form.Item name="api_key" label="API Key">
                <Input.Password placeholder="sk-..." autoComplete="off" />
              </Form.Item>

              <div style={{ marginBottom: 16 }}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 8,
                  }}
                >
                  <Typography.Text strong>模型列表</Typography.Text>
                  <Button size="small" icon={<PlusOutlined />} onClick={addModel}>
                    新增模型
                  </Button>
                </div>
                {currentGroup.models.length === 0 ? (
                  <Typography.Text type="secondary">
                    暂无模型，点击「新增模型」或「获取模型」添加
                  </Typography.Text>
                ) : (
                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    {currentGroup.models.map((m, i) => (
                      <div
                        key={i}
                        style={{ display: 'flex', alignItems: 'flex-start', gap: 8, width: '100%' }}
                      >
                        <Input
                          value={m.id}
                          placeholder="模型 id"
                          style={{ width: 220 }}
                          onChange={(e) => updateModel(i, { id: e.target.value })}
                        />
                        <InputNumber
                          value={m.context_length ?? undefined}
                          placeholder="上下文长度"
                          min={1}
                          style={{ width: 140 }}
                          onChange={(v) =>
                            updateModel(i, { context_length: v == null ? null : Number(v) })
                          }
                        />
                        <div style={{ flex: 1, minWidth: 300 }}>
                          <Select
                            mode="tags"
                            value={m.reasoning_efforts ?? []}
                            placeholder="输入强度值，回车添加多个"
                            style={{ width: '100%' }}
                            onChange={(v) =>
                              updateModel(i, { reasoning_efforts: Array.isArray(v) ? v : [] })
                            }
                          />
                        </div>
                        <Button
                          type="text"
                          danger
                          icon={<DeleteOutlined />}
                          style={{ flexShrink: 0 }}
                          onClick={() => removeModel(i)}
                        />
                      </div>
                    ))}
                  </Space>
                )}
              </div>

              <Form.Item label="默认模型">
                <Select
                  value={currentGroup.default_model || undefined}
                  placeholder="选择默认模型"
                  options={defaultModelOptions}
                  onChange={setDefaultModel}
                />
              </Form.Item>

              <Space wrap style={{ marginBottom: 16 }}>
                <Button type="primary" loading={saving} icon={<SaveOutlined />} onClick={() => void handleSave()}>
                  保存配置
                </Button>
                <Button loading={testing} icon={<ApiOutlined />} onClick={() => void handleTest()}>
                  连通性测试
                </Button>
                <Button
                  loading={loadingModels}
                  icon={<CloudDownloadOutlined />}
                  onClick={() => void handleFetchModels()}
                >
                  获取模型
                </Button>
              </Space>
              {testResult && (
                <Typography.Text
                  type={testResult.ok ? 'success' : 'danger'}
                  style={{ display: 'block', marginTop: 12 }}
                >
                  {testResult.ok
                    ? `连接成功，耗时 ${testResult.latency_ms ?? '-'} ms`
                    : testResult.message}
                </Typography.Text>
              )}
            </Form>
          ) : (
            <Typography.Text type="secondary">点击左侧「新增配置组」开始</Typography.Text>
          )}
        </div>
      </div>
    </div>
  )
}
