import { Alert } from 'antd'
import { useAgentState } from '../../hooks/useAgentState'
import AgentSessionList from './AgentSessionList'
import AgentChatMessages from './AgentChatMessages'
import AgentConfigBar from './AgentConfigBar'
import AgentChatInput from './AgentChatInput'
import AgentApprovalModal from './AgentApprovalModal'
import styles from './AgentPage.module.css'

export default function AgentPage() {
  const agent = useAgentState()
  const { connectionState, pendingApproval } = agent

  return (
    <div className={styles.pageRow}>
      <AgentSessionList
        sessions={agent.sessions}
        sessionsLoading={agent.sessionsLoading}
        currentId={agent.currentId}
        onSelect={agent.handleSelect}
        onNew={agent.handleNew}
        onDelete={agent.handleDelete}
        onExport={agent.handleExport}
        onRename={agent.startRename}
        renamingId={agent.renamingId}
        renameValue={agent.renameValue}
        setRenameValue={agent.setRenameValue}
        commitRename={agent.commitRename}
        offline={agent.offline}
      />
      <div className={styles.mainPanel}>
        {(connectionState === 'reconnecting' || connectionState === 'closed') && (
          <Alert
            className={styles.stateAlert}
            type={connectionState === 'closed' ? 'error' : 'warning'}
            showIcon
            message={connectionState === 'closed' ? '连接已断开且自动重连失败' : '连接中断，正在自动重连…'}
            description={connectionState === 'closed' ? '请检查后端服务是否可用，刷新页面或重新选择会话以重建连接。' : undefined}
          />
        )}
        <AgentChatMessages
          messages={agent.messages}
          loading={agent.loading}
          running={agent.running}
          statusLabel={agent.statusLabel}
          bottomRef={agent.bottomRef}
          sessionId={agent.currentId}
          onCopyText={agent.copyText}
        />
        {pendingApproval && (
          <Alert
            className={styles.approvalAlert}
            type="warning"
            showIcon
            message={`Agent 请求执行危险操作：${pendingApproval.tool}`}
            description="请在下方确认弹窗中选择「允许」或「拒绝」。"
          />
        )}
        <AgentChatInput
          input={agent.input}
          setInput={agent.setInput}
          onSend={agent.handleSend}
          onStop={agent.handleStop}
          onUploadFiles={agent.handleUploadFiles}
          uploadedFiles={agent.uploadedFiles}
          onRemoveFile={agent.handleRemoveFile}
          running={agent.running}
          loading={agent.loading}
          offline={agent.offline}
          pendingApproval={pendingApproval}
          uploading={agent.uploading}
          connectionState={connectionState}
          dragOver={agent.dragOver}
          onDragOver={agent.handleDragOver}
          onDragLeave={agent.handleDragLeave}
          onDrop={agent.handleDrop}
          configBar={
            <AgentConfigBar
              models={agent.models}
              model={agent.model}
              onModelChange={agent.handleModelChange}
              reasoningEffort={agent.reasoningEffort}
              onEffortChange={agent.setReasoningEffort}
              reasoningEffortOptions={agent.reasoningEffortOptions}
              usage={agent.usage}
              contextLength={agent.contextLength}
              compactedVisible={agent.compactedVisible}
                        offline={agent.offline}
            />
          }
        />
      </div>
      <AgentApprovalModal pendingApproval={pendingApproval} onApprove={agent.respondApproval} offline={agent.offline} />
    </div>
  )
}
