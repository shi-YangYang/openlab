import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Breadcrumb, Button, Card, Divider, InputNumber, Progress, Select, Space, Spin, Typography } from 'antd'
import { App as AntApp } from 'antd'
import { DownloadOutlined, ExperimentOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { createExperiment, exportExperimentMarkdown, getExperiment } from '../api'
import type { AnalysisLanguage, ExperimentRecord } from '../types'

function downloadText(text: string, filename: string) {
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function ExperimentPage() {
  const { message } = AntApp.useApp()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const innovationIdParam = searchParams.get('innovation_id')
  const sourceType: 'innovation' | 'papers' = innovationIdParam ? 'innovation' : 'papers'
  const innovationId = innovationIdParam ? Number(innovationIdParam) : null
  const arxivIds = useMemo(
    () =>
      (searchParams.get('ids') ?? '')
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    [searchParams],
  )
  const [record, setRecord] = useState<ExperimentRecord | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [language, setLanguage] = useState<AnalysisLanguage>('zh')
  const [count, setCount] = useState<number>(1)
  const [exporting, setExporting] = useState(false)
  const timerRef = useRef<number | null>(null)

  const poll = useCallback(async (id: number) => {
    try {
      const rec = await getExperiment(id)
      setRecord(rec)
      if (rec.status === 'pending' || rec.status === 'running') {
        timerRef.current = window.setTimeout(() => void poll(id), 1500)
      }
    } catch {
      timerRef.current = window.setTimeout(() => void poll(id), 1500)
    }
  }, [])

  useEffect(() => {
    setRecord(null)
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current)
    }
  }, [arxivIds, innovationId])

  const handleGenerate = async () => {
    setSubmitting(true)
    try {
      const rec = await createExperiment({
        source_type: sourceType,
        innovation_id: sourceType === 'innovation' ? innovationId : null,
        arxiv_ids: arxivIds,
        count,
        language,
      })
      setRecord(rec)
      if (rec.id != null) void poll(rec.id)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '实验方案生成失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleExport = async () => {
    if (!record?.id) return
    setExporting(true)
    try {
      const text = await exportExperimentMarkdown(record.id)
      downloadText(text, `experiments-${record.id}.md`)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '导出失败')
    } finally {
      setExporting(false)
    }
  }

  const content = record?.content
  const busy = submitting || record?.status === 'pending' || record?.status === 'running'

  const crumbRoot = sourceType === 'innovation'
    ? { label: '创新点历史', path: '/history/innovation' }
    : { label: '论文库', path: '/library' }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Breadcrumb
        items={[
          {
            title: (
              <a
                onClick={(e) => {
                  e.preventDefault()
                  navigate(crumbRoot.path)
                }}
              >
                {crumbRoot.label}
              </a>
            ),
          },
          { title: '生成实验方案' },
        ]}
      />
      <Card>
        <Space wrap style={{ marginBottom: 16 }}>
          <Typography.Text type="secondary">数量</Typography.Text>
          <InputNumber min={1} max={3} value={count} onChange={(v) => setCount(v ?? 1)} />
          <Select<AnalysisLanguage>
            value={language}
            style={{ width: 110 }}
            onChange={setLanguage}
            options={[
              { value: 'zh', label: '中文' },
              { value: 'en', label: 'English' },
            ]}
          />
          {sourceType === 'papers' && (
            <Typography.Text type="secondary">已选 {arxivIds.length} 篇</Typography.Text>
          )}
          <Button
            type="primary"
            icon={<ExperimentOutlined />}
            loading={submitting}
            onClick={handleGenerate}
          >
            生成实验方案
          </Button>
          {record?.id != null && record?.status === 'done' && (
            <Button icon={<DownloadOutlined />} loading={exporting} onClick={handleExport}>
              导出 Markdown
            </Button>
          )}
        </Space>

        {busy ? (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <Spin tip="生成实验方案中..." />
            <Progress percent={record?.progress ?? 0} status="active" />
          </div>
        ) : record?.status === 'failed' || (record && !content) ? (
          <Alert
            type="error"
            showIcon
            message="实验方案生成失败"
            description={record?.error || '请确认已配置 LLM 且输入有效。'}
          />
        ) : !record ? (
          <Alert
            type="info"
            message="尚未生成"
            description="选择数量与语言后，点击「生成实验方案」。"
          />
        ) : (
          <>
            {content?.map((plan, i) => (
              <Card
                key={i}
                size="small"
                title={`方案 ${i + 1}`}
                style={{ marginBottom: 12 }}
              >
                <Typography.Paragraph>
                  <Typography.Text strong>假设：</Typography.Text>
                  {plan.hypothesis}
                </Typography.Paragraph>
                <Typography.Paragraph>
                  <Typography.Text strong>目标：</Typography.Text>
                  {plan.goal}
                </Typography.Paragraph>
                <Divider orientation="left" plain style={{ margin: '8px 0' }}>
                  数据集
                </Divider>
                <ul>{plan.datasets.map((d, j) => <li key={j}>{d}</li>)}</ul>
                <Divider orientation="left" plain style={{ margin: '8px 0' }}>
                  基线
                </Divider>
                <ul>{plan.baselines.map((b, j) => <li key={j}>{b}</li>)}</ul>
                <Divider orientation="left" plain style={{ margin: '8px 0' }}>
                  评价指标
                </Divider>
                <ul>{plan.metrics.map((m, j) => <li key={j}>{m}</li>)}</ul>
              </Card>
            ))}
          </>
        )}
      </Card>
    </Space>
  )
}
