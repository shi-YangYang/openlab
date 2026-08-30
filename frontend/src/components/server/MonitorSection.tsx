import { useCallback, useEffect, useState } from 'react'
import {
  App as AntApp,
  Button,
  Card,
  Col,
  Progress,
  Row,
  Space,
  Spin,
  Statistic,
  Table,
  Typography,
} from 'antd'
import type { TableProps } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { monitorServer } from '../../api'
import type { DiskInfo, GpuInfo, MonitorData, Server } from '../../types'
import styles from './ServerDetailPage.module.css'

const GPU_COLUMNS: TableProps<GpuInfo>['columns'] = [
  { title: '序号', dataIndex: 'index', key: 'index', width: 70 },
  { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
  {
    title: '利用率',
    dataIndex: 'utilization',
    key: 'utilization',
    width: 220,
    render: (value: number) => <Progress percent={value} size="small" />,
  },
  {
    title: '显存 (MB)',
    key: 'memory',
    width: 180,
    render: (_: unknown, r) => `${r.memory_used_mb} / ${r.memory_total_mb}`,
  },
]

const DISK_COLUMNS: TableProps<DiskInfo>['columns'] = [
  { title: '文件系统', dataIndex: 'filesystem', key: 'filesystem', ellipsis: true },
  { title: '大小', dataIndex: 'size', key: 'size', width: 90 },
  { title: '已用', dataIndex: 'used', key: 'used', width: 90 },
  {
    title: '使用率',
    dataIndex: 'use_percent',
    key: 'use_percent',
    width: 200,
    render: (value: number | null | undefined) =>
      value == null ? '-' : <Progress percent={value} size="small" />,
  },
  { title: '挂载点', dataIndex: 'mount', key: 'mount', ellipsis: true },
]

interface MonitorSectionProps {
  server: Server
}

export default function MonitorSection({ server }: MonitorSectionProps) {
  const { message } = AntApp.useApp()
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<MonitorData | null>(null)

  const run = useCallback(async () => {
    setLoading(true)
    setData(null)
    try {
      setData(await monitorServer(server.id))
    } catch (e) {
      message.error(e instanceof Error ? e.message : '监控失败')
    } finally {
      setLoading(false)
    }
  }, [server.id, message])

  useEffect(() => {
    void run()
  }, [run])

  const memoryPercent =
    data?.memory && data.memory.total_mb > 0
      ? Math.round((data.memory.used_mb / data.memory.total_mb) * 100)
      : 0

  return (
    <Card>
      <div className={styles.toolbar}>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void run()}>
          刷新
        </Button>
      </div>
      {loading ? (
        <div className={styles.loadingCenter}>
          <Spin tip="执行监控命令中..." />
        </div>
      ) : data ? (
        <Space direction="vertical" size={16} className={styles.fullWidth}>
          <Row gutter={16}>
            <Col xs={24} sm={8}>
              <Card size="small" title="CPU 负载">
                <Row gutter={8}>
                  <Col span={8}>
                    <Statistic title="1 分钟" value={data.load[0] ?? '-'} />
                  </Col>
                  <Col span={8}>
                    <Statistic title="5 分钟" value={data.load[1] ?? '-'} />
                  </Col>
                  <Col span={8}>
                    <Statistic title="15 分钟" value={data.load[2] ?? '-'} />
                  </Col>
                </Row>
              </Card>
            </Col>
            <Col xs={24} sm={8}>
              <Card size="small" title="内存">
                {data.memory ? (
                  <>
                    <Progress
                      percent={memoryPercent}
                      format={() =>
                        `${data.memory?.used_mb ?? 0} / ${data.memory?.total_mb ?? 0} MB`
                      }
                    />
                    <Typography.Text type="secondary">
                      已用 {data.memory.used_mb} MB / 共 {data.memory.total_mb} MB
                    </Typography.Text>
                  </>
                ) : (
                  <Typography.Text type="secondary">内存信息不可用</Typography.Text>
                )}
              </Card>
            </Col>
            <Col xs={24} sm={8}>
              <Card size="small" title="磁盘分区数">
                <Statistic value={data.disk.length} suffix="个" />
              </Card>
            </Col>
          </Row>

          <Card size="small" title="GPU">
            {data.gpu.length ? (
              <Table
                rowKey="index"
                columns={GPU_COLUMNS}
                dataSource={data.gpu}
                pagination={false}
                size="small"
              />
            ) : (
              <Typography.Text type="secondary">未检测到 GPU</Typography.Text>
            )}
          </Card>

          <Card size="small" title="磁盘">
            {data.disk.length ? (
              <Table
                rowKey={(r) => `${r.filesystem}-${r.mount}`}
                columns={DISK_COLUMNS}
                dataSource={data.disk}
                pagination={false}
                size="small"
              />
            ) : (
              <Typography.Text type="secondary">磁盘信息不可用</Typography.Text>
            )}
          </Card>

          {data.processes.length > 0 && (
            <Card size="small" title="进程（按内存占用排序）">
              <pre className={styles.processesPre}>{data.processes.join('\n')}</pre>
            </Card>
          )}

          {Object.keys(data.raw).length > 0 && (
            <Card size="small" title="原始输出（解析失败项）">
              {Object.entries(data.raw).map(([key, value]) => (
                <div key={key} className={styles.rawItem}>
                  <Typography.Text strong>{key}</Typography.Text>
                  <pre className={styles.rawPre}>{value}</pre>
                </div>
              ))}
            </Card>
          )}
        </Space>
      ) : (
        <Typography.Text type="secondary">暂无监控结果。</Typography.Text>
      )}
    </Card>
  )
}
