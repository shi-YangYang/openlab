import { useEffect, useState } from 'react'
import { Alert, Button, Form, Input, Modal, Progress, Select, Space, Typography, Upload } from 'antd'
import { App as AntApp } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import { confirmUpload, uploadPdf } from '../api'
import type { PaperMetadata } from '../types'

interface Props {
  open: boolean
  onClose: () => void
  onSaved: () => void
}

interface MetadataFormValues {
  title: string
  authors: string[]
  abstract: string
  published: string
}

export default function UploadPdfModal({ open, onClose, onSaved }: Props) {
  const { message } = AntApp.useApp()
  const [form] = Form.useForm<MetadataFormValues>()
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [pdfToken, setPdfToken] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setPdfToken(null)
    setError(null)
    form.resetFields()
  }, [open, form])

  const handleUpload = async (file: File) => {
    setUploading(true)
    setError(null)
    try {
      const res = await uploadPdf(file)
      setPdfToken(res.pdf_token)
      form.setFieldsValue({
        title: res.paper.title,
        authors: res.paper.authors,
        abstract: res.paper.abstract,
        published: res.paper.published,
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }

  const handleSave = async () => {
    if (!pdfToken) return
    const values = await form.validateFields()
    setSaving(true)
    try {
      await confirmUpload(pdfToken, values as PaperMetadata)
      message.success('已保存到论文库')
      onSaved()
      onClose()
    } catch (e) {
      message.error(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="上传 PDF 到论文库"
      open={open}
      onCancel={onClose}
      onOk={pdfToken ? handleSave : undefined}
      okText="保存"
      confirmLoading={saving}
      okButtonProps={{ disabled: !pdfToken }}
      width={640}
    >
      {uploading ? (
        <div style={{ textAlign: 'center', padding: '24px 0' }}>
          <Progress
            percent={100}
            status="active"
            showInfo={false}
            style={{ maxWidth: 480, margin: '0 auto 12px' }}
          />
          <Typography.Text type="secondary">正在解析 PDF 并提取元数据…</Typography.Text>
        </div>
      ) : error ? (
        <Alert type="error" showIcon message="上传失败" description={error} />
      ) : !pdfToken ? (
        <Upload.Dragger
          accept=".pdf"
          maxCount={1}
          showUploadList={false}
          beforeUpload={(file) => {
            void handleUpload(file)
            return false
          }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽 PDF 文件到此处上传</p>
          <p className="ant-upload-hint">上传后将用 LLM 自动提取标题、作者、摘要与日期，请确认后再保存。</p>
        </Upload.Dragger>
      ) : (
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="authors" label="作者">
            <Select mode="tags" tokenSeparators={[',', '，']} placeholder="输入作者后回车" open={false} />
          </Form.Item>
          <Form.Item name="abstract" label="摘要">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="published" label="日期">
            <Input placeholder="例如 2024-05-01" />
          </Form.Item>
          <Space>
            <Typography.Text type="secondary">确认无误后点击「保存」入库。</Typography.Text>
          </Space>
        </Form>
      )}
    </Modal>
  )
}
