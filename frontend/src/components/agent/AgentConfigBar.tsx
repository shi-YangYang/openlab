import { Button, Progress, Select, Space, Tag, Tooltip } from 'antd'
import type { AgentSessionUsage, LlmModelInfo } from '../../types'
import styles from './AgentPage.module.css'

interface AgentConfigBarProps {
  models: LlmModelInfo[]
  model: string | undefined
  onModelChange: (value: string | undefined) => void
  reasoningEffort: string | undefined
  onEffortChange: (value: string | undefined) => void
  reasoningEffortOptions: { value: string; label: string }[]
  usage: AgentSessionUsage | null
  contextLength: number | null
  compactedVisible: boolean
  offline: boolean
}

export default function AgentConfigBar({
  models,
  model,
  onModelChange,
  reasoningEffort,
  onEffortChange,
  reasoningEffortOptions,
  usage,
  contextLength,
  compactedVisible,
  offline,
}: AgentConfigBarProps) {
  const lastInput = usage?.last_input_tokens ?? 0

  const handleEffortChange = (value: string) => {
    onEffortChange(value || undefined)
  }

  return (
    <>
      {compactedVisible && <Tag color="geekblue">已压缩早期历史</Tag>}
      <Space size={4} wrap>
        <Select
          size="small"
          className={styles.modelSelect}
          value={model}
          onChange={onModelChange}
          showSearch
          optionFilterProp="label"
          placeholder="选择模型"
          options={models.map((m) => ({ value: m.id, label: m.id }))}
        />
        <Select
          size="small"
          className={styles.effortSelect}
          placeholder="思考强度"
          value={reasoningEffort ?? ''}
          onChange={handleEffortChange}
          options={reasoningEffortOptions}
        />
      </Space>
      <div className={styles.ringWrap}>
        <Tooltip
          title={
            usage
              ? contextLength
                ? `上下文 ${lastInput.toLocaleString()} / ${contextLength.toLocaleString()} tokens（${Math.round(
                    (lastInput / contextLength) * 100,
                  )}%）`
                : `已用 ${lastInput.toLocaleString()} tokens`
              : '暂无用量统计'
          }
        >
          {usage ? (
            <Progress
              type="circle"
              size={22}
              percent={
                contextLength ? Math.min(100, Math.round((lastInput / contextLength) * 100)) : 100
              }
              showInfo={false}
              strokeColor={
                contextLength && lastInput / contextLength > 0.8 ? '#faad14' : '#1677ff'
              }
            />
          ) : (
            <Progress type="circle" size={22} percent={0} showInfo={false} />
          )}
        </Tooltip>
      </div>
    </>
  )
}
