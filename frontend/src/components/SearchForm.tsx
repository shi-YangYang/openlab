import { Button, DatePicker, Form, Input, InputNumber, Radio, Space } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import type { Dayjs } from 'dayjs'

export type SearchMode = 'keyword' | 'topic'

export interface SearchFormValues {
  mode: SearchMode
  query: string
  max_results: number
  date_range?: [Dayjs, Dayjs] | null
}

interface Props {
  loading: boolean
  onSubmit: (values: SearchFormValues) => void
}

export default function SearchForm({ loading, onSubmit }: Props) {
  const [form] = Form.useForm<SearchFormValues>()
  const mode = Form.useWatch('mode', form)

  return (
    <Form
      form={form}
      layout="vertical"
      initialValues={{ mode: 'keyword', max_results: 10 }}
      onFinish={onSubmit}
    >
      <Form.Item name="mode" label="搜索方式">
        <Radio.Group>
          <Radio.Button value="keyword">关键词 / 检索式</Radio.Button>
          <Radio.Button value="topic">主题描述（LLM 拆解）</Radio.Button>
        </Radio.Group>
      </Form.Item>

      <Form.Item
        name="query"
        label={mode === 'topic' ? '主题描述' : '关键词 / 检索式'}
        rules={[{ required: true, message: '请输入内容' }]}
      >
        <Input.TextArea
          rows={2}
          placeholder={
            mode === 'topic'
              ? '例如：基于 Transformer 的大语言模型的推理能力'
              : '例如：attention is all you need'
          }
        />
      </Form.Item>

      <Space wrap align="start">
        <Form.Item name="max_results" label="返回数量">
          <InputNumber min={1} max={100} style={{ width: 120 }} />
        </Form.Item>
        <Form.Item name="date_range" label="日期范围">
          <DatePicker.RangePicker />
        </Form.Item>
        <Form.Item label=" ">
          <Button type="primary" htmlType="submit" loading={loading} icon={<SearchOutlined />}>
            搜索
          </Button>
        </Form.Item>
      </Space>
    </Form>
  )
}
