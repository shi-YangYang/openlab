import { useEffect, useState } from 'react'
import { App as AntApp, AutoComplete, Button, Form, Input, Select, Space, Typography } from 'antd'
import { ApiOutlined, CloudDownloadOutlined, SaveOutlined } from '@ant-design/icons'
import { getLlmConfig, getLlmModels, getLlmPresets, saveLlmConfig, testLlmConnection } from '../api'
import type { LlmPreset, LlmTestResult } from '../types'

interface FormValues {
  preset?: string
  base_url: string
  model: string[]
  api_key: string
  reasoning_effort?: string
}

const CUSTOM_PRESET = '__custom__'

const REASONING_EFFORT_OPTIONS = [
  { value: 'low', label: 'low（低）' },
  { value: 'medium', label: 'medium（中）' },
  { value: 'high', label: 'high（高）' },
]
export default function LlmConfigForm() {
  const { message } = AntApp.useApp()
  const [form] = Form.useForm<FormValues>()
  const [presets, setPresets] = useState<LlmPreset[]>([])
  const [modelOptions, setModelOptions] = useState<string[]>([])
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
        form.setFieldsValue({
          preset: CUSTOM_PRESET,
          base_url: cfg.base_url,
          model: cfg.model ? [cfg.model] : [],
          api_key: cfg.api_key,
          reasoning_effort: cfg.reasoning_effort || undefined,
        })
      })
      .catch(() => {
        message.error('加载 LLM 配置失败')
      })
    return () => {
      cancelled = true
    }
  }, [form])

  const modelValue = (raw: unknown): string => (Array.isArray(raw) ? raw[0] ?? '' : String(raw ?? ''))

  const handlePresetChange = (name: string) => {
    if (name === CUSTOM_PRESET) return
    const preset = presets.find((p) => p.name === name)
    if (preset) {
      form.setFieldsValue({ base_url: preset.base_url, model: [preset.default_model] })
    }
  }

  const handleSave = async (values: FormValues) => {
    setSaving(true)
    try {
      await saveLlmConfig({
        base_url: values.base_url,
        model: modelValue(values.model),
        api_key: values.api_key,
        reasoning_effort: values.reasoning_effort ?? '',
      })
      message.success('LLM 配置已保存')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    const values = form.getFieldsValue()
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testLlmConnection({
        base_url: values.base_url,
        model: modelValue(values.model),
        api_key: values.api_key,
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

  const handleFetchModels = async () => {
    const values = form.getFieldsValue()
    const base_url = (values.base_url || '').trim()
    if (!base_url) {
      message.warning('请先填写 Base URL')
      return
    }
    setLoadingModels(true)
    try {
      const models = await getLlmModels({ base_url, api_key: values.api_key ?? '' })
      setModelOptions(models)
      if (models.length) {
        message.success(`已获取 ${models.length} 个模型`)
      } else {
        message.info('未获取到模型，可手动输入模型名')
      }
    } catch (e) {
      message.error(e instanceof Error ? e.message : '获取模型列表失败')
    } finally {
      setLoadingModels(false)
    }
  }

  const presetOptions = [
    { value: CUSTOM_PRESET, label: '自定义' },
    ...presets.map((p) => ({ value: p.name, label: p.name })),
  ]

  return (
    <div>
      <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
        选择平台预设会自动填充 Base URL 与模型，可手动修改；配置保存到本地文件（不入 git）。
        「思考强度」仅部分模型支持，留空则沿用模型默认行为。
      </Typography.Text>
      <Form
        form={form}
        layout="vertical"
        initialValues={{ preset: CUSTOM_PRESET }}
        onFinish={handleSave}
      >
        <Form.Item name="preset" label="平台">
          <Select options={presetOptions} onChange={handlePresetChange} />
        </Form.Item>
        <Form.Item
          name="base_url"
          label="Base URL（OpenAI 兼容）"
          rules={[{ required: true, message: '请输入 Base URL' }]}
        >
          <Input placeholder="https://api.openai.com/v1" />
        </Form.Item>
        <Form.Item name="model" label="模型" rules={[{ required: true, message: '请选择或输入模型名' }]}>
          <Select
            mode="tags"
            maxCount={1}
            showSearch
            optionFilterProp="label"
            placeholder="选择或输入模型名"
            options={modelOptions.map((m) => ({ value: m, label: m }))}
            tokenSeparators={[',']}
          />
        </Form.Item>
        <Form.Item name="api_key" label="API Key">
          <Input.Password placeholder="sk-..." autoComplete="off" />
        </Form.Item>
        <Form.Item name="reasoning_effort" label="思考强度（可选）">
          <AutoComplete
            allowClear
            placeholder="默认（不设置），可输入任意值"
            options={REASONING_EFFORT_OPTIONS}
            filterOption={(input, option) =>
              ((option?.value ?? '') as string).toLowerCase().includes(input.toLowerCase())
            }
          />
        </Form.Item>
        <Space wrap style={{ marginBottom: 16 }}>
          <Button type="primary" htmlType="submit" loading={saving} icon={<SaveOutlined />}>
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
    </div>
  )
}
