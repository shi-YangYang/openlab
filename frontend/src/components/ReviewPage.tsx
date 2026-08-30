import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Breadcrumb, Button, Card, Divider, Progress, Select, Space, Spin, Tag, Typography } from 'antd'
import { App as AntApp } from 'antd'
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { createReview, exportReviewMarkdown, getReview } from '../api'
import type { AnalysisLanguage, ReviewRecord } from '../types'

function downloadText(text: string, filename: string) {
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function ReviewPage() {
  const { message } = AntApp.useApp()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const arxivIds = useMemo(
    () =>
      (searchParams.get('ids') ?? '')
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    [searchParams],
  )
  const [record, setRecord] = useState<ReviewRecord | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [language, setLanguage] = useState<AnalysisLanguage>('zh')
  const [exporting, setExporting] = useState(false)
  const timerRef = useRef<number | null>(null)

  const poll = useCallback(async (id: number) => {
    try {
      const rec = await getReview(id)
      setRecord(rec)
      if (rec.status === 'pending' || rec.status === 'running') {
        timerRef.current = window.setTimeout(() => void poll(id), 1500)
      }
    } catch {
      timerRef.current = window.setTimeout(() => void poll(id), 1500)
    }
  }, [])

  const launchReview = useCallback(() => {
    setRecord(null)
    setSubmitting(true)
    createReview(arxivIds, language)
      .then((rec) => {
        setRecord(rec)
        if (rec.id != null) void poll(rec.id)
      })
      .catch((e) => message.error(e instanceof Error ? e.message : '综述生成失败'))
      .finally(() => setSubmitting(false))
  }, [arxivIds, language, poll, message])

  useEffect(() => {
    if (arxivIds.length < 2) return
    launchReview()
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current)
    }
  }, [arxivIds, launchReview])

  const handleExport = async () => {
    if (!record?.id) return
    setExporting(true)
    try {
      const text = await exportReviewMarkdown(record.id)
      downloadText(text, `review-${record.id}.md`)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '导出失败')
    } finally {
      setExporting(false)
    }
  }

  const content = record?.content

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Breadcrumb
        items={[
          {
            title: (
              <a
                onClick={(e) => {
                  e.preventDefault()
                  navigate('/library')
                }}
              >
                论文库
              </a>
            ),
          },
          { title: '对比综述' },
        ]}
      />
      <Card>
        {arxivIds.length < 2 ? (
          <Alert
            type="warning"
            showIcon
            message="参数无效"
            description="请从论文库选择至少两篇论文后再进行对比综述。"
          />
        ) : (
          <>
            <Space style={{ marginBottom: 16 }}>
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
              {record?.id != null && record?.status === 'done' && (
                <Button icon={<DownloadOutlined />} loading={exporting} onClick={handleExport}>
                  导出 Markdown
                </Button>
              )}
            </Space>

            {submitting || record?.status === 'pending' || record?.status === 'running' ? (
              <div className="page-center">
                <Spin tip="生成综述中..." />
                <Progress percent={record?.progress ?? 0} status="active" />
              </div>
            ) : record?.status === 'failed' || !content ? (
              <Alert
                type="error"
                showIcon
                message="综述生成失败"
                description={record?.error || '请确认已配置 LLM 且所选论文可分析。'}
                action={
                  <Button
                    size="small"
                    icon={<ReloadOutlined />}
                    loading={submitting}
                    onClick={() => void launchReview()}
                  >
                    重试综述
                  </Button>
                }
              />
            ) : (
              <>
                <Divider orientation="left">共同主题</Divider>
                <Space wrap>{content.common_themes.map((x, i) => <Tag key={i} color="blue">{x}</Tag>)}</Space>
                <Divider orientation="left">差异</Divider>
                <ul>{content.differences.map((x, i) => <li key={i}>{x}</li>)}</ul>
                <Divider orientation="left">研究空白</Divider>
                <ul>{content.research_gaps.map((x, i) => <li key={i}>{x}</li>)}</ul>
                <Divider orientation="left">总结</Divider>
                <Typography.Paragraph>{content.summary}</Typography.Paragraph>
              </>
            )}
          </>
        )}
      </Card>
    </Space>
  )
}
