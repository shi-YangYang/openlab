import { Button, Form, Input, InputNumber, Select, Space, Typography } from 'antd'
import type { FormInstance } from 'antd'
import {
  ApiOutlined,
  CloudDownloadOutlined,
  DeleteOutlined,
  PlusOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import type { LlmGroup, LlmModelInfo, LlmPreset, LlmTestResult } from '../../types'
import styles from './LlmConfigForm.module.css'

export interface GroupFormValues {
  name?: string
  base_url?: string
  api_key?: string
}

interface LlmConfigGroupFormProps {
  currentGroup: LlmGroup
  form: FormInstance<GroupFormValues>
  presets: LlmPreset[]
  onValuesChange: (values: GroupFormValues) => void
  onPresetFill: (presetName: string) => void
  onUpdateModel: (index: number, patch: Partial<LlmModelInfo>) => void
  onAddModel: () => void
  onRemoveModel: (index: number) => void
  onSetDefault: (id: string) => void
  onFetchModels: () => void
  onTest: () => void
  onSave: () => void
  saving: boolean
  testing: boolean
  loadingModels: boolean
  testResult: LlmTestResult | null
  defaultModelOptions: { value: string; label: string }[]
}

export default function LlmConfigGroupForm({
  currentGroup,
  form,
  presets,
  onValuesChange,
  onPresetFill,
  onUpdateModel,
  onAddModel,
  onRemoveModel,
  onSetDefault,
  onFetchModels,
  onTest,
  onSave,
  saving,
  testing,
  loadingModels,
  testResult,
  defaultModelOptions,
}: LlmConfigGroupFormProps) {
  const presetOptions = presets.map((p) => ({ value: p.name, label: p.name }))

  const handleValuesChange = (_changed: unknown, all: GroupFormValues) => {
    onValuesChange(all)
  }

  const handlePresetSelect = (presetName?: string) => {
    if (presetName) onPresetFill(presetName)
  }

  return (
    <Form form={form} layout="vertical" onValuesChange={handleValuesChange}>
      <Form.Item label="从预设填充（可选）">
        <Select
          allowClear
          placeholder="选择平台预设自动填充 Base URL 与模型"
          options={presetOptions}
          onChange={handlePresetSelect}
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

      <div className={styles.modelsSection}>
        <div className={styles.modelsHeader}>
          <Typography.Text strong>模型列表</Typography.Text>
          <Button size="small" icon={<PlusOutlined />} onClick={onAddModel}>
            新增模型
          </Button>
        </div>
        {currentGroup.models.length === 0 ? (
          <Typography.Text type="secondary">
            暂无模型，点击「新增模型」或「获取模型」添加
          </Typography.Text>
        ) : (
          <Space direction="vertical" size={8} className={styles.fullWidth}>
            {currentGroup.models.map((m, i) => (
              <div key={i} className={styles.modelRow}>
                <Input
                  value={m.id}
                  placeholder="模型 id"
                  className={styles.modelIdInput}
                  onChange={(e) => onUpdateModel(i, { id: e.target.value })}
                />
                <InputNumber
                  value={m.context_length ?? undefined}
                  placeholder="上下文长度"
                  min={1}
                  className={styles.contextLengthInput}
                  onChange={(v) =>
                    onUpdateModel(i, { context_length: v == null ? null : Number(v) })
                  }
                />
                <div className={styles.effortsField}>
                  <Select
                    mode="tags"
                    value={m.reasoning_efforts ?? []}
                    placeholder="输入强度值，回车添加多个"
                    className={styles.fullWidth}
                    onChange={(v) =>
                      onUpdateModel(i, { reasoning_efforts: Array.isArray(v) ? v : [] })
                    }
                  />
                </div>
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  className={styles.modelDeleteButton}
                  onClick={() => onRemoveModel(i)}
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
          onChange={onSetDefault}
        />
      </Form.Item>

      <Space wrap className={styles.actionsRow}>
        <Button type="primary" loading={saving} icon={<SaveOutlined />} onClick={() => void onSave()}>
          保存配置
        </Button>
        <Button loading={testing} icon={<ApiOutlined />} onClick={() => void onTest()}>
          连通性测试
        </Button>
        <Button
          loading={loadingModels}
          icon={<CloudDownloadOutlined />}
          onClick={() => void onFetchModels()}
        >
          获取模型
        </Button>
      </Space>
      {testResult && (
        <Typography.Text type={testResult.ok ? 'success' : 'danger'} className={styles.testResult}>
          {testResult.ok
            ? `连接成功，耗时 ${testResult.latency_ms ?? '-'} ms`
            : testResult.message}
        </Typography.Text>
      )}
    </Form>
  )
}
