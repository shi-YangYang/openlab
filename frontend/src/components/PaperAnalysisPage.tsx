import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert,
  Breadcrumb,
  Button,
  Card,
  Descriptions,
  Divider,
  Progress,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd'
import { App as AntApp } from 'antd'
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import {
  analyzePaper,
  ApiError,
  exportAnalysisMarkdown,
  getAnalysis,
  listPapers,
} from '../api'
import type { AnalysisLanguage, AnalysisRecord } from '../types'
import styles from './PaperAnalysisPage.module.css'

const STATUS_META: Record<string, { color: string; label: string }> = {
  pending: { color: 'gold', label: '待分析' },
  running: { color: 'processing', label: '分析中' },
  done: { color: 'success', label: '已完成' },
  failed: { color: 'error', label: '失败' },
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

export default function PaperAnalysisPage() {
  const { message } = AntApp.useApp()
  const navigate = useNavigate()
  const { arxivId = '' } = useParams()
  const [title, setTitle] = useState<string | null>(null)
  const [record, setRecord] = useState<AnalysisRecord | null>(null)
  const [loading, setLoading] = useState(false)
  const [language, setLanguage] = useState<AnalysisLanguage>('zh')
  const [analyzing, setAnalyzing] = useState(false)
  const [exporting, setExporting] = useState(false)
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    let active = true
    listPapers([arxivId])
      .then((list) => {
        if (active) setTitle(list[0]?.title ?? null)
      })
      .catch(() => {
        if (active) setTitle(null)
      })
    return () => {
      active = false
    }
  }, [arxivId])

  const load = useCallback(async () => {
    if (!arxivId) return
    setLoading(true)
    try {
      const rec = await getAnalysis(arxivId)
      setRecord(rec)
      if (rec.language === 'zh' || rec.language === 'en') setLanguage(rec.language)
    } catch {
      setRecord(null)
    } finally {
      setLoading(false)
    }
  }, [arxivId])

  const poll = useCallback(async () => {
    if (!arxivId) return
    try {
      const rec = await getAnalysis(arxivId)
      setRecord(rec)
      if (rec.status === 'pending' || rec.status === 'running') {
        timerRef.current = window.setTimeout(poll, 1500)
      }
    } catch {
      // ignore transient errors, keep polling
      timerRef.current = window.setTimeout(poll, 1500)
    }
  }, [arxivId])

  useEffect(() => {
    if (arxivId) void load()
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current)
    }
  }, [arxivId, load])

  const handleAnalyze = async () => {
    if (!arxivId) return
    setAnalyzing(true)
    try {
      await analyzePaper(arxivId, language)
      const running: AnalysisRecord = { arxiv_id: arxivId, content: null, language, status: 'running' }
      setRecord(running)
      if (timerRef.current) window.clearTimeout(timerRef.current)
      poll()
    } catch (e) {
      if (e instanceof ApiError && (e.status === 409 || e.status === 404)) {
        message.warning('该论文尚未下载，请先下载后再分析')
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
  const displayTitle = title ?? arxivId

  return (
    <Space direction="vertical" size={16} className={styles.fullWidth}>
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
          { title: displayTitle },
        ]}
      />
      <Card>
        <Space className={styles.toolbar}>
          <Select<AnalysisLanguage>
            value={language}
            className={styles.langSelect}
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

        <Divider className={styles.dividerTop} />

        {loading ? (
          <div className={styles.loadingCenter}>
            <Spin />
          </div>
        ) : !record ? (
          <Alert type="info" message="尚未分析" description="点击上方「分析」按钮生成结构化分析。" />
        ) : (
          <>
            <Space className={styles.statusToolbar}>
              <Tag color={(STATUS_META[record.status] ?? { color: 'default' }).color}>
                {(STATUS_META[record.status] ?? { label: record.status }).label}
              </Tag>
              <Typography.Text type="secondary">语言：{record.language === 'zh' ? '中文' : 'English'}</Typography.Text>
            </Space>

            {(record.status === 'pending' || record.status === 'running') && (
              <div className="page-center">
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
                action={
                  <Button
                    size="small"
                    icon={<ReloadOutlined />}
                    loading={analyzing}
                    onClick={() => void handleAnalyze()}
                  >
                    重试分析
                  </Button>
                }
              />
            )}

            {record.status === 'done' && content && (
              <>
                <Divider orientation="left">总结</Divider>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="研究问题">
                    <div className={styles.longText}>{content.summary.research_problem}</div>
                  </Descriptions.Item>
                  <Descriptions.Item label="方法">
                    <div className={styles.longText}>{content.summary.method}</div>
                  </Descriptions.Item>
                  <Descriptions.Item label="结论">
                    <div className={styles.longText}>{content.summary.conclusion}</div>
                  </Descriptions.Item>
                </Descriptions>
                <div className={`section-title ${styles.contribTitle}`}>贡献</div>
                <ul>{content.summary.contributions.map((x, i) => <li key={i}>{x}</li>)}</ul>

                <Divider orientation="left">实验与结果</Divider>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="关键结果">
                    <div className={styles.longText}>{content.experiments.key_results}</div>
                  </Descriptions.Item>
                </Descriptions>
                <div className="section-title">数据集</div>
                <Space wrap>{content.experiments.datasets.map((x, i) => <Tag key={i} className={styles.tagWrap}>{x}</Tag>)}</Space>
                <div className="section-title">基线</div>
                <Space wrap>{content.experiments.baselines.map((x, i) => <Tag key={i} className={styles.tagWrap}>{x}</Tag>)}</Space>
                <div className="section-title">评测指标</div>
                <Space wrap>{content.experiments.metrics.map((x, i) => <Tag key={i} className={styles.tagWrap}>{x}</Tag>)}</Space>

                <Divider orientation="left">局限与展望</Divider>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="局限性">
                    <div className={styles.longText}>{content.limitations}</div>
                  </Descriptions.Item>
                  <Descriptions.Item label="未来工作">
                    <div className={styles.longText}>{content.future_work}</div>
                  </Descriptions.Item>
                </Descriptions>

                <Divider orientation="left">关键词 / 标签</Divider>
                <div className="section-title">关键词</div>
                <Space wrap>{content.keywords.map((x, i) => <Tag color="blue" key={i} className={styles.tagWrap}>{x}</Tag>)}</Space>
                <div className="section-title">标签</div>
                <Space wrap>{content.tags.map((x, i) => <Tag color="green" key={i} className={styles.tagWrap}>{x}</Tag>)}</Space>
              </>
            )}
          </>
        )}
      </Card>
    </Space>
  )
}
