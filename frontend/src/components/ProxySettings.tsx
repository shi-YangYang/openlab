import { useEffect, useState } from 'react'
import { App as AntApp, Button, Input, Typography } from 'antd'
import { SaveOutlined } from '@ant-design/icons'
import { getLlmConfig, saveLlmConfig } from '../api'
import type { LlmGroupsConfig } from '../types'

export default function ProxySettings() {
  const { message } = AntApp.useApp()
  const [proxy, setProxy] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    getLlmConfig()
      .then((cfg) => {
        if (cancelled) return
        setProxy(cfg.proxy ?? '')
      })
      .catch(() => {
        message.error('加载代理配置失败')
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      // The proxy lives in the same config file; fetch the current groups and
      // persist them unchanged so only the proxy value changes.
      const cfg = await getLlmConfig()
      const next: LlmGroupsConfig = {
        active_group: cfg.active_group,
        groups: cfg.groups,
        proxy: proxy.trim(),
      }
      await saveLlmConfig(next)
      message.success('代理已保存')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
        访问 arXiv、Semantic Scholar 等外部站点进行搜索与论文下载时使用的 HTTP 代理；
        LLM 调用与 SSH 连接不受影响。修改保存后重新发起下载即生效。
      </Typography.Text>
      <Input
        value={proxy}
        onChange={(e) => setProxy(e.target.value)}
        allowClear
        placeholder="留空 = 直连；例如 http://127.0.0.1:7897 或 127.0.0.1:7897"
        style={{ maxWidth: 480 }}
      />
      <div style={{ marginTop: 12 }}>
        <Button type="primary" loading={saving} icon={<SaveOutlined />} onClick={() => void handleSave()}>
          保存代理
        </Button>
      </div>
    </div>
  )
}
