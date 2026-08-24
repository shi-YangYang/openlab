import { useEffect, useState } from 'react'
import { App as AntApp, Button, Form, Input, Select, Space, Typography } from 'antd'
import { SaveOutlined } from '@ant-design/icons'
import { getLlmConfig, getLlmPresets, saveLlmConfig } from '../api'
import type { LlmPreset } from '../types'

interface FormValues {
  preset?: string
  base_url: string
  model: string
  api_key: string
}

const CUSTOM_PRESET = '__custom__'

export default function LlmConfigForm() {
  const { message } = AntApp.useApp()
  const [form] = Form.useForm<FormValues>()
  const [presets, setPresets] = useState<LlmPreset[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    Promise.all([getLlmPresets(), getLlmConfig()])
      .then(([ps, cfg]) => {
        if (cancelled) return
        setPresets(ps)
        form.setFieldsValue({
          preset: CUSTOM_PRESET,
          base_url: cfg.base_url,
          model: cfg.model,
          api_key: cfg.api_key,
        })
      })
      .catch(() => {
        message.error('加载 LLM 配置失败')
      })
    return () => {
      cancelled = true
    }
  }, [form])

  const handlePresetChange = (name: string) => {
    if (name === CUSTOM_PRESET) return
    const preset = presets.find((p) => p.name === name)
    if (preset) {
      form.setFieldsValue({ base_url: preset.base_url, model: preset.default_model })
    }
  }

  const handleSave = async (values: FormValues) => {
    setSaving(true)
    try {
      await saveLlmConfig({
        base_url: values.base_url,
        model: values.model,
        api_key: values.api_key,
      })
      message.success('LLM 配置已保存')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
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
        <Form.Item name="model" label="模型" rules={[{ required: true, message: '请输入模型名' }]}>
          <Input placeholder="gpt-4o-mini" />
        </Form.Item>
        <Form.Item name="api_key" label="API Key">
          <Input.Password placeholder="sk-..." autoComplete="off" />
        </Form.Item>
        <Space>
          <Button type="primary" htmlType="submit" loading={saving} icon={<SaveOutlined />}>
            保存配置
          </Button>
        </Space>
      </Form>
    </div>
  )
}
