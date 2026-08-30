import { useEffect, useState } from 'react'
import { App as AntApp, Form, Typography } from 'antd'
import { getLlmConfig, getLlmModels, getLlmPresets, saveLlmConfig, testLlmConnection } from '../../api'
import type { LlmGroup, LlmGroupsConfig, LlmModelInfo, LlmPreset, LlmTestResult } from '../../types'
import LlmConfigGroupForm from './LlmConfigGroupForm'
import type { GroupFormValues } from './LlmConfigGroupForm'
import LlmConfigGroupList from './LlmConfigGroupList'
import styles from './LlmConfigForm.module.css'

let groupSeq = 0

function newGroupId(): string {
  groupSeq += 1
  return `group-${Date.now().toString(36)}-${groupSeq}`
}

function emptyGroup(): LlmGroup {
  return { id: newGroupId(), name: '', base_url: '', api_key: '', models: [], default_model: '' }
}

function emptyModel(): LlmModelInfo {
  return { id: '', context_length: null, reasoning_efforts: [] }
}

function mergeFetchedModels(models: LlmModelInfo[], fetched: LlmModelInfo[]): LlmModelInfo[] {
  const merged = models.map((m) => ({ ...m }))
  for (const m of fetched) {
    if (!m.id) continue
    const existing = merged.find((x) => x.id === m.id)
    if (existing) {
      if (m.context_length != null) existing.context_length = m.context_length
      if (m.reasoning_efforts != null && m.reasoning_efforts.length > 0) {
        existing.reasoning_efforts = m.reasoning_efforts
      }
    } else {
      merged.push({ id: m.id, context_length: m.context_length ?? null, reasoning_efforts: m.reasoning_efforts ?? [] })
    }
  }
  return merged
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
      .catch(() => message.error('加载 LLM 配置失败'))
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
    form.setFieldsValue({ name: group.name, base_url: group.base_url, api_key: group.api_key })
    setTestResult(null)
  }

  const currentGroup = groups.find((g) => g.id === selectedId)

  const handleValuesChange = (values: GroupFormValues) => {
    if (!selectedId) return
    setGroups((prev) =>
      prev.map((g) =>
        g.id === selectedId
          ? { ...g, name: values.name ?? '', base_url: values.base_url ?? '', api_key: values.api_key ?? '' }
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
    if (activeGroup === id) setActiveGroup(remaining[0].id)
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

  const handleUpdateModel = (index: number, patch: Partial<LlmModelInfo>) => {
    if (!selectedId) return
    setGroups((prev) =>
      prev.map((g) =>
        g.id === selectedId
          ? { ...g, models: g.models.map((m, i) => (i === index ? { ...m, ...patch } : m)) }
          : g,
      ),
    )
  }

  const handleAddModel = () => {
    if (!selectedId) return
    setGroups((prev) =>
      prev.map((g) => (g.id === selectedId ? { ...g, models: [...g.models, emptyModel()] } : g)),
    )
  }

  const handleRemoveModel = (index: number) => {
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

  const handleSetDefaultModel = (id: string) => {
    if (!selectedId) return
    setGroups((prev) => prev.map((g) => (g.id === selectedId ? { ...g, default_model: id } : g)))
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
        prev.map((g) =>
          g.id === selectedId ? { ...g, models: mergeFetchedModels(g.models, fetched) } : g,
        ),
      )
      if (fetched.length) message.success(`已获取 ${fetched.length} 个模型`)
      else message.info('未获取到模型，可手动添加模型')
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
      if (result.ok) message.success('连通性测试通过')
      else message.error(result.message || '连通性测试失败')
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
      groups: groups.map((g) => ({ ...g, models: g.models.filter((m) => m.id) })),
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
      <Typography.Text type="secondary" className={styles.introText}>
        以「配置组」区分不同平台（OpenAI / 阿里云百炼 / DeepSeek 等）。每组可获取模型列表、测试连通性；
        「当前使用组」决定分析、实验、Agent 等默认使用的模型。每个模型可单独设置「上下文长度」与「思考强度」。
        思考强度为自由输入，按模型实际支持的取值填写（如 OpenAI 的 low/medium/high），可填多个。
      </Typography.Text>

      <div className={styles.layout}>
        <div className={styles.sideColumn}>
          <LlmConfigGroupList
            groups={groups}
            activeGroup={activeGroup}
            selectedId={selectedId}
            onSelect={handleSelectGroup}
            onAdd={handleAddGroup}
            onDelete={handleDeleteGroup}
            onActiveChange={setActiveGroup}
          />
        </div>
        <div className={styles.mainColumn}>
          {currentGroup ? (
            <LlmConfigGroupForm
              currentGroup={currentGroup}
              form={form}
              presets={presets}
              onValuesChange={handleValuesChange}
              onPresetFill={handlePresetFill}
              onUpdateModel={handleUpdateModel}
              onAddModel={handleAddModel}
              onRemoveModel={handleRemoveModel}
              onSetDefault={handleSetDefaultModel}
              onFetchModels={handleFetchModels}
              onTest={handleTest}
              onSave={handleSave}
              saving={saving}
              testing={testing}
              loadingModels={loadingModels}
              testResult={testResult}
              defaultModelOptions={defaultModelOptions}
            />
          ) : (
            <Typography.Text type="secondary">点击左侧「新增配置组」开始</Typography.Text>
          )}
        </div>
      </div>
    </div>
  )
}
