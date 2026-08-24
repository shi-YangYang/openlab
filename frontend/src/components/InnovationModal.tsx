import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Button, Card, Divider, InputNumber, Modal, Progress, Select, Space, Spin, Typography } from 'antd'
import { App as AntApp } from 'antd'
import { DownloadOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { createInnovations, exportInnovationMarkdown, getInnovation } from '../api'
import type { AnalysisLanguage, InnovationRecord } from '../types'

interface Props {
  arxivIds: string[]
  open: boolean
  onClose: () => void
}

function downloadText(text: string, filename: string) {
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function InnovationModal({ arxivIds, open, onClose }: Props) {
  const { message } = AntApp.useApp()
  const [record, setRecord] = useState<InnovationRecord | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [language, setLanguage] = useState<AnalysisLanguage>('zh')
  const [count, setCount] = useState<number>(3)
  const [exporting, setExporting] = useState(false)
  const timerRef = useRef<number | null>(null)

  const poll = useCallback(async (id: number) => {
    try {
      const rec = await getInnovation(id)
      setRecord(rec)
      if (rec.status === 'pending' || rec.status === 'running') {
        timerRef.current = window.setTimeout(() => void poll(id), 1500)
      }
    } catch {
      timerRef.current = window.setTimeout(() => void poll(id), 1500)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    setRecord(null)
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current)
    }
  }, [open, arxivIds])

  const handleGenerate = async () => {
    setSubmitting(true)
    try {
      const rec = await createInnovations(arxivIds, count, language)
      setRecord(rec)
      if (rec.id != null) void poll(rec.id)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '创新点生成失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleExport = async () => {
    if (!record?.id) return
    setExporting(true)
    try {
      const text = await exportInnovationMarkdown(record.id)
      downloadText(text, `innovations-${record.id}.md`)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '导出失败')
    } finally {
      setExporting(false)
    }
  }

  const content = record?.content
  const busy = submitting || record?.status === 'pending' || record?.status === 'running'

  return (
    <Modal
      title="创新点设计"
      open={open}
      onCancel={onClose}
      footer={null}
      width={720}
    >
      <Space wrap style={{ marginBottom: 16 }}>
        <Typography.Text type="secondary">数量</Typography.Text>
        <InputNumber min={1} max={10} value={count} onChange={(v) => setCount(v ?? 3)} />
        <Select<AnalysisLanguage>
          value={language}
          style={{ width: 110 }}
          onChange={setLanguage}
          options={[
            { value: 'zh', label: '中文' },
            { value: 'en', label: 'English' },
          ]}
        />
        <Typography.Text type="secondary">已选 {arxivIds.length} 篇</Typography.Text>
        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          loading={submitting}
          onClick={handleGenerate}
        >
          生成创新点
        </Button>
        {record?.id != null && record?.status === 'done' && (
          <Button icon={<DownloadOutlined />} loading={exporting} onClick={handleExport}>
            导出 Markdown
          </Button>
        )}
      </Space>

      {busy ? (
        <div style={{ textAlign: 'center', padding: '24px 0' }}>
          <Spin tip="生成创新点中..." />
          <Progress percent={record?.progress ?? 0} status="active" />
        </div>
      ) : record?.status === 'failed' || (record && !content) ? (
        <Alert
          type="error"
          showIcon
          message="创新点生成失败"
          description={record?.error || '请确认已配置 LLM 且所选论文可分析。'}
        />
      ) : !record ? (
        <Alert
          type="info"
          message="尚未生成"
          description="选择数量与语言后，点击「生成创新点」。"
        />
      ) : (
        <>
          {content?.map((point, i) => (
            <Card
              key={i}
              size="small"
              title={`创新点 ${i + 1}：${point.title}`}
              style={{ marginBottom: 12 }}
            >
              <Typography.Paragraph>{point.description}</Typography.Paragraph>
              <Divider orientation="left" plain style={{ margin: '8px 0' }}>
                创新依据
              </Divider>
              <ul>{point.basis.map((b, j) => <li key={j}>{b}</li>)}</ul>
              <Divider orientation="left" plain style={{ margin: '8px 0' }}>
                预期贡献
              </Divider>
              <Typography.Paragraph>{point.expected_contribution}</Typography.Paragraph>
            </Card>
          ))}
        </>
      )}
    </Modal>
  )
}
