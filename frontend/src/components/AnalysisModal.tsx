import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Descriptions,
  Divider,
  Modal,
  Progress,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd'
import { App as AntApp } from 'antd'
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons'
import {
  analyzePaper,
  ApiError,
  exportAnalysisMarkdown,
  getAnalysis,
} from '../api'
import type { AnalysisLanguage, AnalysisRecord } from '../types'

const STATUS_META: Record<string, { color: string; label: string }> = {
  pending: { color: 'gold', label: '待分析' },
  running: { color: 'processing', label: '分析中' },
  done: { color: 'success', label: '已完成' },
  failed: { color: 'error', label: '失败' },
}

interface Props {
  arxivId: string | null
  open: boolean
  onClose: () => void
  onStatusChange?: (record: AnalysisRecord) => void
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

export default function AnalysisModal({ arxivId, open, onClose, onStatusChange }: Props) {
  const { message } = AntApp.useApp()
  const [record, setRecord] = useState<AnalysisRecord | null>(null)
  const [loading, setLoading] = useState(false)
  const [language, setLanguage] = useState<AnalysisLanguage>('zh')
  const [analyzing, setAnalyzing] = useState(false)
  const [exporting, setExporting] = useState(false)
  const timerRef = useRef<number | null>(null)

  const load = useCallback(async () => {
    if (!arxivId) return
    setLoading(true)
    try {
      const rec = await getAnalysis(arxivId)
      setRecord(rec)
      if (rec.language === 'zh' || rec.language === 'en') setLanguage(rec.language)
      onStatusChange?.(rec)
    } catch {
      setRecord(null)
    } finally {
      setLoading(false)
    }
  }, [arxivId, onStatusChange])

  const poll = useCallback(async () => {
    if (!arxivId) return
    try {
      const rec = await getAnalysis(arxivId)
      setRecord(rec)
      onStatusChange?.(rec)
      if (rec.status === 'pending' || rec.status === 'running') {
        timerRef.current = window.setTimeout(poll, 1500)
      }
    } catch {
      // ignore transient errors, keep polling
      timerRef.current = window.setTimeout(poll, 1500)
    }
  }, [arxivId, onStatusChange])

  useEffect(() => {
    if (open && arxivId) {
      void load()
    }
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current)
    }
  }, [open, arxivId, load])

  const handleAnalyze = async () => {
    if (!arxivId) return
    setAnalyzing(true)
    try {
      await analyzePaper(arxivId, language)
      const running: AnalysisRecord = { arxiv_id: arxivId, content: null, language, status: 'running' }
      setRecord(running)
      onStatusChange?.(running)
      if (timerRef.current) window.clearTimeout(timerRef.current)
      poll()
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        message.warning('请先下载该论文')
      } else {
        message.error(e instanceof Error ? e.message : '分析失败')
      }
    } finally {
      setAnalyzing(false)
    }
  }

  const handleExport = async () => {
    if (!arxivId) return
    setExporting(true)
    try {
      const text = await exportAnalysisMarkdown(arxivId)
      downloadText(text, `${arxivId}-analysis.md`)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '导出失败')
    } finally {
      setExporting(false)
    }
  }

  const content = record?.content

  return (
    <Modal
      title={`论文分析：${arxivId ?? ''}`}
      open={open}
      onCancel={onClose}
      footer={null}
      width={640}
    >
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
        <Button icon={<ReloadOutlined />} loading={analyzing} onClick={handleAnalyze}>
          分析
        </Button>
        <Button
          icon={<DownloadOutlined />}
          loading={exporting}
          disabled={record?.status !== 'done'}
          onClick={handleExport}
        >
          导出
        </Button>
      </Space>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin />
        </div>
      ) : !record ? (
        <Alert type="info" message="尚未分析" description="点击上方「分析」按钮生成结构化分析。" />
      ) : (
        <>
          <Space style={{ marginBottom: 16 }}>
            <Tag color={(STATUS_META[record.status] ?? { color: 'default' }).color}>
              {(STATUS_META[record.status] ?? { label: record.status }).label}
            </Tag>
            <Typography.Text type="secondary">语言：{record.language === 'zh' ? '中文' : 'English'}</Typography.Text>
          </Space>

          {(record.status === 'pending' || record.status === 'running') && (
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <Progress percent={record.progress ?? 0} status="active" />
              {record.message && (
                <Typography.Text type="secondary">{record.message}</Typography.Text>
              )}
            </div>
          )}

          {record.status === 'failed' && (
            <Alert
              type="error"
              showIcon
              message="分析失败"
              description={
                record.error ||
                '可能原因：PDF 未下载或解析失败、LLM 未配置或返回格式错误。可调整语言后重新分析。'
              }
            />
          )}

          {record.status === 'done' && content && (
            <>
              <Divider orientation="left">总结</Divider>
              <Descriptions column={1} size="small">
                <Descriptions.Item label="研究问题">{content.summary.research_problem}</Descriptions.Item>
                <Descriptions.Item label="方法">{content.summary.method}</Descriptions.Item>
                <Descriptions.Item label="结论">{content.summary.conclusion}</Descriptions.Item>
              </Descriptions>
              <Typography.Title level={5} style={{ marginTop: 8 }}>贡献</Typography.Title>
              <ul>{content.summary.contributions.map((x, i) => <li key={i}>{x}</li>)}</ul>

              <Divider orientation="left">实验与结果</Divider>
              <Descriptions column={1} size="small">
                <Descriptions.Item label="关键结果">{content.experiments.key_results}</Descriptions.Item>
              </Descriptions>
              <Typography.Title level={5}>数据集</Typography.Title>
              <Space wrap>{content.experiments.datasets.map((x, i) => <Tag key={i}>{x}</Tag>)}</Space>
              <Typography.Title level={5}>基线</Typography.Title>
              <Space wrap>{content.experiments.baselines.map((x, i) => <Tag key={i}>{x}</Tag>)}</Space>
              <Typography.Title level={5}>评测指标</Typography.Title>
              <Space wrap>{content.experiments.metrics.map((x, i) => <Tag key={i}>{x}</Tag>)}</Space>

              <Divider orientation="left">局限与展望</Divider>
              <Descriptions column={1} size="small">
                <Descriptions.Item label="局限性">{content.limitations}</Descriptions.Item>
                <Descriptions.Item label="未来工作">{content.future_work}</Descriptions.Item>
              </Descriptions>

              <Divider orientation="left">关键词 / 标签</Divider>
              <Typography.Title level={5}>关键词</Typography.Title>
              <Space wrap>{content.keywords.map((x, i) => <Tag color="blue" key={i}>{x}</Tag>)}</Space>
              <Typography.Title level={5}>标签</Typography.Title>
              <Space wrap>{content.tags.map((x, i) => <Tag color="green" key={i}>{x}</Tag>)}</Space>
            </>
          )}
        </>
      )}
    </Modal>
  )
}
