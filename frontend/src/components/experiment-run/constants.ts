export const STEPS = ['sync_code', 'setup_env', 'launch_training'] as const

export type Step = (typeof STEPS)[number]

export type StepState = 'pending' | 'running' | 'success' | 'failed' | 'retrying' | 'skipped'

export const STEP_LABELS: Record<Step, string> = {
  sync_code: '同步代码',
  setup_env: '环境准备',
  launch_training: '启动训练',
}
