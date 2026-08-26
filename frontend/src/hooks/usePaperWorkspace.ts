import { useCallback, useState } from 'react'
import { App as AntApp } from 'antd'
import { analyzeBatch, ApiError, deletePaper, downloadPapers, listAnalyses, listPapers } from '../api'
import type { AnalysisRecord, AnalysisStatusInfo, Paper } from '../types'

interface Options {
  onAnalyzeOne?: (arxivId: string) => void
  onOpenReview?: (arxivIds: string[]) => void
  onOpenInnovation?: (arxivIds: string[]) => void
  onOpenExperiment?: (arxivIds: string[]) => void
}

export function usePaperWorkspace(options: Options = {}) {
  const { message } = AntApp.useApp()
  const [papers, setPapers] = useState<Paper[]>([])
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [statusMap, setStatusMap] = useState<Record<string, string>>({})
  const [errorMap, setErrorMap] = useState<Record<string, string>>({})
  const [downloadProgressMap, setDownloadProgressMap] = useState<Record<string, number>>({})
  const [analysisStatusMap, setAnalysisStatusMap] = useState<Record<string, AnalysisStatusInfo>>({})
  const [analyzingBatch, setAnalyzingBatch] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const refreshStatuses = useCallback(async (ids: string[]) => {
    try {
      const records = await listPapers(ids)
      const map: Record<string, string> = {}
      const err: Record<string, string> = {}
      const prog: Record<string, number> = {}
      for (const r of records) {
        map[r.arxiv_id] = r.status ?? ''
        if (r.error) err[r.arxiv_id] = r.error
        if (r.progress != null) prog[r.arxiv_id] = r.progress
      }
      setStatusMap((prev) => ({ ...prev, ...map }))
      setErrorMap((prev) => ({ ...prev, ...err }))
      setDownloadProgressMap((prev) => ({ ...prev, ...prog }))
    } catch {
      // ignore status refresh errors
    }
  }, [])

  const pollStatuses = useCallback(async (ids: string[]) => {
    const deadline = Date.now() + 180000
    while (Date.now() < deadline) {
      try {
        const records = await listPapers(ids)
        if (records.length > 0) {
          const map: Record<string, string> = {}
          const err: Record<string, string> = {}
          const prog: Record<string, number> = {}
          for (const r of records) {
            map[r.arxiv_id] = r.status ?? ''
            if (r.error) err[r.arxiv_id] = r.error
            if (r.progress != null) prog[r.arxiv_id] = r.progress
          }
          setStatusMap((prev) => ({ ...prev, ...map }))
          setErrorMap((prev) => ({ ...prev, ...err }))
          setDownloadProgressMap((prev) => ({ ...prev, ...prog }))
          const terminal = records.every(
            (r) => r.status === 'downloaded' || r.status === 'failed',
          )
          if (terminal) return
        }
      } catch {
        // ignore transient errors and keep polling
      }
      await new Promise((res) => setTimeout(res, 1500))
    }
  }, [])

  const refreshAnalysisStatuses = useCallback(async (ids: string[]) => {
    try {
      const records = await listAnalyses(ids)
      const map: Record<string, AnalysisStatusInfo> = {}
      for (const r of records) {
        map[r.arxiv_id] = { status: r.status ?? '', progress: r.progress, message: r.message }
      }
      setAnalysisStatusMap((prev) => ({ ...prev, ...map }))
    } catch {
      // ignore
    }
  }, [])

  const pollAnalysisStatuses = useCallback(async (ids: string[]) => {
    const deadline = Date.now() + 600000
    while (Date.now() < deadline) {
      let records: AnalysisRecord[] = []
      try {
        records = await listAnalyses(ids)
      } catch {
        records = []
      }
      if (records.length > 0) {
        const map: Record<string, AnalysisStatusInfo> = {}
        for (const r of records) {
          map[r.arxiv_id] = { status: r.status ?? '', progress: r.progress, message: r.message }
        }
        setAnalysisStatusMap((prev) => ({ ...prev, ...map }))
        const terminal = records.every(
          (r) => r.status === 'done' || r.status === 'failed',
        )
        if (terminal) return
      }
      await new Promise((res) => setTimeout(res, 1500))
    }
  }, [])

  const setResults = useCallback(
    (result: Paper[]) => {
      setPapers(result)
      setSelectedIds([])
      if (result.length) {
        void refreshStatuses(result.map((p) => p.arxiv_id))
        void refreshAnalysisStatuses(result.map((p) => p.arxiv_id))
      }
    },
    [refreshStatuses, refreshAnalysisStatuses],
  )

  const loadLibrary = useCallback(async () => {
    try {
      const records = await listPapers()
      setPapers(records)
      setSelectedIds([])
      const map: Record<string, string> = {}
      const err: Record<string, string> = {}
      const prog: Record<string, number> = {}
      for (const r of records) {
        map[r.arxiv_id] = r.status ?? ''
        if (r.error) err[r.arxiv_id] = r.error
        if (r.progress != null) prog[r.arxiv_id] = r.progress
      }
      setStatusMap(map)
      setErrorMap(err)
      setDownloadProgressMap(prog)
      if (records.length) {
        void refreshAnalysisStatuses(records.map((r) => r.arxiv_id))
      }
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载论文库失败')
    }
  }, [message, refreshAnalysisStatuses])

  const handleDownload = async () => {
    const selected = selectedIds.length
      ? papers.filter((p) => selectedIds.includes(p.arxiv_id))
      : papers
    const targets = selected.filter((p) => p.source !== 'baidu_xueshu')
    if (!targets.length) {
      message.warning('没有可下载的论文（百度学术论文请通过「查看原文」获取全文）')
      return
    }
    setDownloading(true)
    try {
      const res = await downloadPapers(targets)
      const next: Record<string, string> = {}
      for (const id of res.accepted) next[id] = 'downloading'
      for (const id of res.skipped) next[id] = 'downloaded'
      setStatusMap((prev) => ({ ...prev, ...next }))
      message.info(`下载已提交：新增 ${res.accepted.length} 篇，跳过已存在 ${res.skipped.length} 篇`)
      if (res.accepted.length) void pollStatuses(res.accepted)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '下载失败')
    } finally {
      setDownloading(false)
    }
  }

  const handleBatchAnalyze = async () => {
    const selected = selectedIds.length
      ? papers.filter((p) => selectedIds.includes(p.arxiv_id))
      : papers
    const targets = selected.filter((p) => p.source !== 'baidu_xueshu')
    if (!targets.length) {
      message.warning('没有可分析的论文（百度学术论文请通过「查看原文」获取全文）')
      return
    }
    setAnalyzingBatch(true)
    try {
      const ids = targets.map((p) => p.arxiv_id)
      await analyzeBatch(ids, 'zh')
      const next: Record<string, AnalysisStatusInfo> = {}
      for (const id of ids) next[id] = { status: 'pending', progress: 0 }
      setAnalysisStatusMap((prev) => ({ ...prev, ...next }))
      message.info(`已提交 ${ids.length} 篇论文分析`)
      void pollAnalysisStatuses(ids)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        message.warning('请先下载所选论文')
      } else {
        message.error(e instanceof Error ? e.message : '分析失败')
      }
    } finally {
      setAnalyzingBatch(false)
    }
  }

  const handleOpenReview = () => {
    const targets = selectedIds.length ? selectedIds : papers.map((p) => p.arxiv_id)
    if (targets.length < 2) {
      message.warning('请选择至少两篇论文进行对比综述')
      return
    }
    options.onOpenReview?.(targets)
  }

  const handleOpenInnovation = () => {
    if (selectedIds.length < 1) {
      message.warning('请选择至少一篇论文生成创新点')
      return
    }
    options.onOpenInnovation?.(selectedIds)
  }

  const handleOpenExperiment = () => {
    if (selectedIds.length < 1) {
      message.warning('请选择至少一篇论文生成实验方案')
      return
    }
    options.onOpenExperiment?.(selectedIds)
  }

  const handleAnalyzeOne = (arxivId: string) => {
    options.onAnalyzeOne?.(arxivId)
  }

  const handleDeleteOne = async (arxivId: string) => {
    try {
      await deletePaper(arxivId)
      message.success('已删除')
      setPapers((prev) => prev.filter((p) => p.arxiv_id !== arxivId))
      setSelectedIds((prev) => prev.filter((id) => id !== arxivId))
    } catch (e) {
      message.error(e instanceof Error ? e.message : '删除失败')
    }
  }

  const handleDeleteMany = async (ids: string[]) => {
    setDeleting(true)
    let removed = 0
    try {
      for (const id of ids) {
        try {
          await deletePaper(id)
          removed += 1
        } catch {
          // keep going; report failures below
        }
      }
      setPapers((prev) => prev.filter((p) => !ids.includes(p.arxiv_id)))
      setSelectedIds((prev) => prev.filter((id) => !ids.includes(id)))
      if (removed === ids.length) {
        message.success(`已删除 ${removed} 篇论文`)
      } else {
        message.warning(`已删除 ${removed}/${ids.length} 篇论文`)
      }
    } finally {
      setDeleting(false)
    }
  }

  const handleAnalysisStatus = useCallback((rec: AnalysisRecord) => {
    setAnalysisStatusMap((prev) => ({
      ...prev,
      [rec.arxiv_id]: { status: rec.status ?? '', progress: rec.progress, message: rec.message },
    }))
  }, [])

  return {
    papers,
    setPapers,
    loading,
    setLoading,
    downloading,
    selectedIds,
    setSelectedIds,
    statusMap,
    errorMap,
    downloadProgressMap,
    analysisStatusMap,
    analyzingBatch,
    deleting,
    setResults,
    loadLibrary,
    handleDownload,
    handleBatchAnalyze,
    handleOpenReview,
    handleOpenInnovation,
    handleOpenExperiment,
    handleAnalyzeOne,
    handleDeleteOne,
    handleDeleteMany,
    handleAnalysisStatus,
  }
}

export type PaperWorkspace = ReturnType<typeof usePaperWorkspace>
