import { useEffect, useRef, useState } from 'react'
import { App as AntApp, Button, Space, Table, Tag, Typography } from 'antd'
import { LoginOutlined, LogoutOutlined } from '@ant-design/icons'
import { cancelPlatformLogin, completePlatformLogin, getPlatformStatus, listPlatforms, loginPlatform, logoutPlatform } from '../api'
import type { PlatformState, PlatformStatus } from '../types'

const PLATFORM_LABELS: Record<string, string> = {
  cnki: '知网 CNKI',
  baidu_xueshu: '百度学术',
}

const STATE_META: Record<PlatformState, { text: string; color: string }> = {
  not_logged_in: { text: '未登录', color: 'default' },
  logging_in: { text: '登录中', color: 'processing' },
  logged_in: { text: '已登录', color: 'success' },
  expired: { text: '已过期', color: 'warning' },
}

export default function PlatformLogin() {
  const { message } = AntApp.useApp()
  const [platforms, setPlatforms] = useState<PlatformStatus[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const timersRef = useRef<Record<string, number>>({})

  const load = async () => {
    try {
      setPlatforms(await listPlatforms())
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载平台登录状态失败')
    }
  }

  useEffect(() => {
    void load()
    const timers = timersRef.current
    return () => {
      Object.values(timers).forEach((t) => window.clearInterval(t))
    }
  }, [])

  const updateOne = (status: PlatformStatus) => {
    setPlatforms((prev) =>
      prev.map((p) => (p.platform === status.platform ? status : p)),
    )
  }

  const stopPolling = (platform: string) => {
    const timer = timersRef.current[platform]
    if (timer != null) {
      window.clearInterval(timer)
      delete timersRef.current[platform]
    }
  }

  const poll = (platform: string) => {
    stopPolling(platform)
    timersRef.current[platform] = window.setInterval(async () => {
      try {
        const status = await getPlatformStatus(platform)
        updateOne(status)
        if (status.state === 'logged_in') {
          stopPolling(platform)
          message.success(`${PLATFORM_LABELS[platform] ?? platform} 登录成功`)
        } else if (status.state === 'not_logged_in') {
          stopPolling(platform)
          message.warning(`${PLATFORM_LABELS[platform] ?? platform} 登录未完成或已超时`)
        }
      } catch {
        stopPolling(platform)
      }
    }, 2000)
  }

  const handleLogin = async (platform: string) => {
    setBusy(platform)
    try {
      await loginPlatform(platform)
      message.info('已打开浏览器，请在浏览器中完成验证')
      poll(platform)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '登录失败')
    } finally {
      setBusy(null)
    }
  }

  const handleLogout = async (platform: string) => {
    setBusy(platform)
    try {
      const status = await logoutPlatform(platform)
      updateOne(status)
      stopPolling(platform)
      message.success('已退出登录')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '退出失败')
    } finally {
      setBusy(null)
    }
  }

  const handleComplete = async (platform: string) => {
    setBusy(platform)
    try {
      const status = await completePlatformLogin(platform)
      updateOne(status)
      stopPolling(platform)
      message.success('登录完成，已保存登录态')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '操作失败')
    } finally {
      setBusy(null)
    }
  }

  const handleCancel = async (platform: string) => {
    setBusy(platform)
    try {
      const status = await cancelPlatformLogin(platform)
      updateOne(status)
      stopPolling(platform)
      message.info('已取消登录')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '操作失败')
    } finally {
      setBusy(null)
    }
  }

  const columns = [
    {
      title: '平台',
      dataIndex: 'platform',
      key: 'platform',
      render: (platform: string) => PLATFORM_LABELS[platform] ?? platform,
    },
    {
      title: '状态',
      dataIndex: 'state',
      key: 'state',
      render: (state: PlatformState) => (
        <Tag color={STATE_META[state]?.color}>{STATE_META[state]?.text ?? state}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: PlatformStatus) => {
        const loggingIn = record.state === 'logging_in'
        if (loggingIn) {
          return (
            <Space>
              <Button
                size="small"
                type="primary"
                loading={busy === record.platform}
                onClick={() => void handleComplete(record.platform)}
              >
                我已完成登录
              </Button>
              <Button
                size="small"
                disabled={busy === record.platform}
                onClick={() => void handleCancel(record.platform)}
              >
                取消
              </Button>
            </Space>
          )
        }
        return (
          <Space>
            <Button
              size="small"
              type="primary"
              icon={<LoginOutlined />}
              loading={busy === record.platform}
              onClick={() => void handleLogin(record.platform)}
            >
              登录
            </Button>
            <Button
              size="small"
              icon={<LogoutOutlined />}
              disabled={record.state === 'not_logged_in'}
              onClick={() => void handleLogout(record.platform)}
            >
              退出
            </Button>
          </Space>
        )
      },
    },
  ]

  return (
    <div>
      <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
        登录会打开真实浏览器，请手动完成平台验证；登录态保存到本地文件（不入 git）。
      </Typography.Text>
      <Table
        rowKey="platform"
        columns={columns}
        dataSource={platforms}
        pagination={false}
        size="small"
      />
    </div>
  )
}
