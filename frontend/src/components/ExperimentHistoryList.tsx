import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  App as AntApp,
  Button,
  Card,
  Divider,
  Input,
  Modal,
  Popconfirm,
  Segmented,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { TableProps } from 'antd'
import {
  DeleteOutlined,
  DownloadOutlined,
  EyeOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SearchOutlined,
  SwapOutlined,
} from '@ant-design/icons'
import {
  compareExperimentRuns,
  deleteExperiment,
  exportExperimentMarkdown,
  extractRunMetrics,
  getExperiment,
  getExperimentRun,
  listExperimentRuns,
  listExperiments,
  updateRunMetrics,
} from '../api'
import type {
  ExperimentHistoryItem,
  ExperimentRecord,
  ExperimentRun,
  ExperimentRunCompareItem,
  ExperimentRunCompareResponse,
} from '../types'
import ExperimentRunPanel from './experiment-run/ExperimentRunPanel'

const STATUS_META: Record<string, { color: string; label: string }> = {
  pending: { color: 'processing', label: '生成中' },
  running: { color: 'processing', label: '生成中' },
  done: { color: 'success', label: '完成' },
  failed: { color: 'error', label: '失败' },
}

const LANGUAGE_LABEL: Record<string, string> = { zh: '中文', en: 'English' }

const RUN_STATUS_META: Record<string, { color: string; label: string }> = {
  pending: { color: 'default', label: '待执行' },
  preparing: { color: 'processing', label: '准备中' },
  running: { color: 'processing', label: '运行中' },
  paused: { color: 'error', label: '已暂停' },
  succeeded: { color: 'success', label: '成功' },
  failed: { color: 'error', label: '失败' },
  stopped: { color: 'orange', label: '已终止' },
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

function formatMetricValue(v: number): string {
  if (!Number.isFinite(v)) return '-'
  return String(Math.round(v * 10000) / 10000)
}

function formatDuration(seconds: number | null): string {
  if (seconds == null || !Number.isFinite(seconds)) return '-'
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s} 秒`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m} 分 ${s % 60} 秒`
  return `${Math.floor(m / 60)} 时 ${m % 60} 分`
}

interface CompareRow {
  key: string
  label: string
  isMetric: boolean
  metricKey?: string
  values: Record<number, string | number | null>
}

export default function ExperimentHistoryList() {
  const { message } = AntApp.useApp()
  const [items, setItems] = useState<ExperimentHistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [detail, setDetail] = useState<ExperimentRecord | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [exportingId, setExportingId] = useState<number | null>(null)
  const [keyword, setKeyword] = useState('')
  const [view, setView] = useState<'plans' | 'runs'>('plans')
  const [runs, setRuns] = useState<ExperimentRun[]>([])
  const [runsLoading, setRunsLoading] = useState(false)
  const [runDetail, setRunDetail] = useState<ExperimentRun | null>(null)
  const [runPanelOpen, setRunPanelOpen] = useState(false)
  const [panelExperiment, setPanelExperiment] = useState<ExperimentRecord | null>(null)
  const panelRecord = panelExperiment as ExperimentRecord | null
  const [selectedRunIds, setSelectedRunIds] = useState<number[]>([])
  const [compareOpen, setCompareOpen] = useState(false)
  const [compareLoading, setCompareLoading] = useState(false)
  const [compareData, setCompareData] = useState<ExperimentRunCompareResponse | null>(null)
  const [editingCell, setEditingCell] = useState<{ runId: number; key: string } | null>(null)
  const [editingValue, setEditingValue] = useState('')
  const [reextracting, setReextracting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await listExperiments())
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载实验方案历史失败')
    } finally {
      setLoading(false)
    }
  }, [message])

  const loadRuns = useCallback(async () => {
    setRunsLoading(true)
    try {
      setRuns(await listExperimentRuns())
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载运行记录失败')
    } finally {
      setRunsLoading(false)
    }
  }, [message])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (view === 'runs') void loadRuns()
  }, [view, loadRuns])

  const handleView = async (item: ExperimentHistoryItem) => {
    setDetailLoading(true)
    setDetail(null)
    try {
      setDetail(await getExperiment(item.id))
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载实验方案快照失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const handleExport = async (item: ExperimentHistoryItem) => {
    setExportingId(item.id)
    try {
      const text = await exportExperimentMarkdown(item.id)
      downloadText(text, `experiments-${item.id}.md`)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '导出失败')
    } finally {
      setExportingId(null)
    }
  }

  const handleDelete = async (item: ExperimentHistoryItem) => {
    try {
      await deleteExperiment(item.id)
      message.success('已删除')
      void load()
    } catch (e) {
      message.error(e instanceof Error ? e.message : '删除失败')
    }
  }

  const handleExecute = async (item: ExperimentHistoryItem) => {
    setPanelExperiment(null)
    setRunPanelOpen(true)
    try {
      const record = await getExperiment(item.id)
      setPanelExperiment(record)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载实验方案失败')
      setRunPanelOpen(false)
    }
  }

  const handleViewRun = async (run: ExperimentRun) => {
    try {
      setRunDetail(await getExperimentRun(run.id))
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载运行详情失败')
    }
  }

  const handleCompare = async () => {
    setCompareOpen(true)
    setEditingCell(null)
    setCompareLoading(true)
    try {
      setCompareData(await compareExperimentRuns(selectedRunIds))
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载对比数据失败')
      setCompareOpen(false)
    } finally {
      setCompareLoading(false)
    }
  }

  const commitMetricEdit = async (run: ExperimentRunCompareItem, metricKey: string) => {
    const raw = editingValue.trim()
    const prev = run.metrics ?? {}
    let next: Record<string, number>
    if (raw === '') {
      if (!(metricKey in prev)) {
        setEditingCell(null)
        return
      }
      next = { ...prev }
      delete next[metricKey]
    } else {
      const num = Number(raw)
      if (!Number.isFinite(num)) {
        message.error(`「${raw}」不是有效数字`)
        return
      }
      next = { ...prev, [metricKey]: num }
    }
    try {
      const updated = await updateRunMetrics(run.id, next)
      setEditingCell(null)
      setCompareData((cd) => {
        if (!cd) return cd
        const runs = cd.runs.map((r) =>
          r.id === run.id ? { ...r, metrics: updated.metrics ?? null } : r,
        )
        const keys = new Set<string>()
        for (const r of runs) Object.keys(r.metrics ?? {}).forEach((k) => keys.add(k))
        return { runs, metric_keys: Array.from(keys).sort() }
      })
      message.success('指标已保存')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '保存指标失败')
      setEditingCell(null)
    }
  }

  const handleReextract = async (runId: number) => {
    setReextracting(true)
    try {
      const run = await extractRunMetrics(runId)
      setRunDetail((prev) =>
        prev && prev.id === run.id ? { ...prev, metrics: run.metrics ?? null } : prev,
      )
      const count = Object.keys(run.metrics ?? {}).length
      message.success(count ? `已重新解析，提取到 ${count} 个指标` : '重新解析完成，未提取到指标')
      void loadRuns()
    } catch (e) {
      message.error(e instanceof Error ? e.message : '重新解析失败')
    } finally {
      setReextracting(false)
    }
  }

  const runsColumns: TableProps<ExperimentRun>['columns'] = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '方案', dataIndex: 'experiment_id', key: 'experiment_id', width: 70 },
    { title: '模式', dataIndex: 'mode', key: 'mode', width: 80 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (s: string) => {
        const meta = RUN_STATUS_META[s] ?? { color: 'default', label: s }
        return <Tag color={meta.color}>{meta.label}</Tag>
      },
    },
    { title: '当前步骤', dataIndex: 'current_step', key: 'current_step', ellipsis: true },
    {
      title: '错误',
      dataIndex: 'error',
      key: 'error',
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170 },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: unknown, r) => (
        <Button size="small" onClick={() => void handleViewRun(r)}>
          详情
        </Button>
      ),
    },
  ]

  const filteredItems = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    if (!kw) return items
    return items.filter((item) => {
      const source = (item.source_label || '').toLowerCase()
      const lang = LANGUAGE_LABEL[item.language] || item.language || ''
      return source.includes(kw) || String(lang).toLowerCase().includes(kw)
    })
  }, [items, keyword])

  const filteredRuns = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    if (!kw) return runs
    return runs.filter(
      (r) =>
        (r.status || '').toLowerCase().includes(kw) ||
        (r.current_step || '').toLowerCase().includes(kw),
    )
  }, [runs, keyword])

  const compareRows: CompareRow[] = useMemo(() => {
    if (!compareData) return []
    const rows: CompareRow[] = []
    const infoRows: [string, (r: ExperimentRunCompareItem) => string][] = [
      ['状态', (r) => RUN_STATUS_META[r.status]?.label ?? r.status],
      ['耗时', (r) => formatDuration(r.duration_seconds)],
      ['服务器', (r) => r.server_id || '-'],
      ['创建时间', (r) => r.created_at || '-'],
      ['错误', (r) => r.error || '-'],
    ]
    for (const [label, get] of infoRows) {
      const values: Record<number, string> = {}
      for (const r of compareData.runs) values[r.id] = get(r)
      rows.push({ key: `info_${label}`, label, isMetric: false, values })
    }
    for (const mk of compareData.metric_keys) {
      const values: Record<number, number | null> = {}
      for (const r of compareData.runs) {
        const v = r.metrics?.[mk]
        values[r.id] = typeof v === 'number' ? v : null
      }
      rows.push({ key: `metric_${mk}`, label: mk, isMetric: true, metricKey: mk, values })
    }
    return rows
  }, [compareData])

  const renderCompareCell = (run: ExperimentRunCompareItem, row: CompareRow) => {
    if (!row.isMetric || row.metricKey == null) {
      const v = row.values[run.id]
      return v == null || v === '' ? '-' : String(v)
    }
    if (editingCell && editingCell.runId === run.id && editingCell.key === row.metricKey) {
      return (
        <Input
          size="small"
          autoFocus
          value={editingValue}
          onChange={(e) => setEditingValue(e.target.value)}
          onBlur={() => setEditingCell(null)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void commitMetricEdit(run, row.metricKey!)
            else if (e.key === 'Escape') setEditingCell(null)
          }}
          style={{ width: 110 }}
        />
      )
    }
    const v = row.values[run.id]
    return (
      <span
        style={{ cursor: 'text' }}
        title="双击编辑"
        onDoubleClick={() => {
          setEditingCell({ runId: run.id, key: row.metricKey! })
          setEditingValue(typeof v === 'number' ? String(v) : '')
        }}
      >
        {typeof v === 'number' ? formatMetricValue(v) : '-'}
      </span>
    )
  }

  const compareColumns: TableProps<CompareRow>['columns'] = [
    { title: '项目', dataIndex: 'label', key: 'label', fixed: 'left', width: 130 },
    ...(compareData?.runs ?? []).map((run) => ({
      title: (
        <div>
          <div style={{ fontWeight: 600 }}>{run.experiment_title || `实验对比 ${run.id}`}</div>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            #{run.id} · {RUN_STATUS_META[run.status]?.label ?? run.status}
          </Typography.Text>
        </div>
      ),
      key: `run_${run.id}`,
      render: (_: unknown, row: CompareRow) => renderCompareCell(run, row),
    })),
  ]

  const columns: TableProps<ExperimentHistoryItem>['columns'] = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 190,
    },
    {
      title: '来源',
      dataIndex: 'source_label',
      key: 'source_label',
      width: 180,
      ellipsis: true,
    },
    {
      title: '语言',
      dataIndex: 'language',
      key: 'language',
      width: 90,
      render: (l: string) => LANGUAGE_LABEL[l] ?? l,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: string) => {
        const meta = STATUS_META[s] ?? { color: 'default', label: s }
        return <Tag color={meta.color}>{meta.label}</Tag>
      },
    },
    {
      title: '方案数',
      dataIndex: 'plan_count',
      key: 'plan_count',
      width: 90,
    },
    {
      title: '操作',
      key: 'actions',
      width: 220,
      render: (_: unknown, r) => (
        <Space size={4}>
          <Button
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={() => void handleExecute(r)}
          >
            执行
          </Button>
          <Button size="small" icon={<EyeOutlined />} onClick={() => void handleView(r)}>
            查看
          </Button>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            disabled={r.status !== 'done'}
            loading={exportingId === r.id}
            onClick={() => void handleExport(r)}
          >
            导出
          </Button>
          <Popconfirm title="确定删除该条实验方案？" onConfirm={() => void handleDelete(r)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const content = detail?.content

  return (
    <Card
      title="实验方案历史"
      extra={
        <Space wrap>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder={view === 'plans' ? '按来源/语言过滤' : '按状态/步骤过滤'}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 200 }}
          />
          <Segmented
            value={view}
            onChange={(v) => setView(v as 'plans' | 'runs')}
            options={[
              { value: 'plans', label: '实验方案' },
              { value: 'runs', label: '运行记录' },
            ]}
          />
          {view === 'runs' && (
            <Button
              icon={<SwapOutlined />}
              disabled={selectedRunIds.length < 2 || selectedRunIds.length > 10}
              onClick={() => void handleCompare()}
            >
              对比{selectedRunIds.length ? `（${selectedRunIds.length}）` : ''}
            </Button>
          )}
        </Space>
      }
    >
      {view === 'plans' ? (
        <>
          <Table
            rowKey="id"
            dataSource={filteredItems}
            columns={columns}
            loading={loading}
            pagination={{ pageSize: 10, showSizeChanger: false }}
            size="middle"
          />

          <Modal
            title="实验方案快照"
            open={detailLoading || detail != null}
            onCancel={() => setDetail(null)}
            footer={null}
            width={720}
          >
            {detailLoading ? (
              <div className="page-center">
                <Spin tip="加载中..." />
              </div>
            ) : detail == null ? null : content && content.length ? (
              content.map((plan, i) => (
                <Card key={i} size="small" title={`方案 ${i + 1}`} style={{ marginBottom: 12 }}>
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
              ))
            ) : (
              <Typography.Text type="secondary">该实验方案暂无内容快照。</Typography.Text>
            )}
          </Modal>

          {runPanelOpen && panelRecord != null && (
            <ExperimentRunPanel
              open={runPanelOpen}
              onClose={() => {
                setRunPanelOpen(false)
                setPanelExperiment(null)
                void loadRuns()
              }}
              experiment={panelRecord}
            />
          )}
        </>
      ) : (
        <>
          <Table
            rowKey="id"
            dataSource={filteredRuns}
            columns={runsColumns}
            loading={runsLoading}
            rowSelection={{
              selectedRowKeys: selectedRunIds,
              onChange: (keys) => setSelectedRunIds(keys.map(Number)),
            }}
            pagination={{ pageSize: 10, showSizeChanger: false }}
            size="middle"
          />
          <Modal
            title="实验结果对比"
            open={compareOpen}
            onCancel={() => {
              setCompareOpen(false)
              setEditingCell(null)
            }}
            footer={null}
            width="80%"
          >
            <Table
              rowKey="key"
              dataSource={compareRows}
              columns={compareColumns}
              loading={compareLoading}
              pagination={false}
              size="small"
              scroll={{ x: 'max-content' }}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              双击指标单元格可编辑数值：回车保存，Esc 取消；清空回车删除该指标。
            </Typography.Text>
          </Modal>
          <Modal
            title={`运行详情 #${runDetail?.id ?? ''}`}
            open={runDetail != null}
            onCancel={() => setRunDetail(null)}
            footer={null}
            width={900}
          >
            {runDetail == null ? null : (
              <>
                <Typography.Paragraph>
                  <Typography.Text strong>状态：</Typography.Text>
                  {RUN_STATUS_META[runDetail.status]?.label ?? runDetail.status}
                  {runDetail.error ? ` — ${runDetail.error}` : ''}
                </Typography.Paragraph>
                <Divider orientation="left" plain style={{ margin: '8px 0' }}>
                  指标
                </Divider>
                <div style={{ marginBottom: 12 }}>
                  {runDetail.metrics && Object.keys(runDetail.metrics).length > 0 ? (
                    <Space size={[4, 4]} wrap>
                      {Object.entries(runDetail.metrics).map(([k, v]) => (
                        <Tag key={k}>{`${k}=${formatMetricValue(v)}`}</Tag>
                      ))}
                    </Space>
                  ) : (
                    <Typography.Text type="secondary">未提取</Typography.Text>
                  )}
                </div>
                <Button
                  size="small"
                  icon={<ReloadOutlined />}
                  loading={reextracting}
                  onClick={() => void handleReextract(runDetail.id)}
                >
                  重新解析
                </Button>
                <pre className="log-area" style={{ maxHeight: 420, overflow: 'auto' }}>
                  {runDetail.log_tail || '（无日志）'}
                </pre>
              </>
            )}
          </Modal>
        </>
      )}
    </Card>
  )
}
