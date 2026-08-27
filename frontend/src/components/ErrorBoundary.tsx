import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button, Card, Collapse, Typography } from 'antd'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  summary: string
  stack: string
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, summary: '', stack: '' }

  static getDerivedStateFromError(error: unknown): State {
    if (error instanceof Error) {
      return { hasError: true, summary: error.message, stack: error.stack ?? '' }
    }
    return { hasError: true, summary: String(error), stack: '' }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled render error:', error, info)
  }

  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          padding: 24,
          background: '#f5f5f5',
        }}
      >
        <Card style={{ maxWidth: 640, width: '100%' }}>
          <Typography.Title level={4} style={{ marginTop: 0 }}>
            页面出现异常
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            {this.state.summary || '未知错误'}
          </Typography.Paragraph>
          {this.state.stack && (
            <Collapse
              size="small"
              items={[
                {
                  key: 'stack',
                  label: '错误堆栈',
                  children: (
                    <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 12 }}>
                      {this.state.stack}
                    </pre>
                  ),
                },
              ]}
            />
          )}
          <Button
            type="primary"
            style={{ marginTop: 16 }}
            onClick={() => window.location.reload()}
          >
            重新加载
          </Button>
        </Card>
      </div>
    )
  }
}
