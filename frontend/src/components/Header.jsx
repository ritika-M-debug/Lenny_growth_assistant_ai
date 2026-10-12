import React from 'react';
import { Menu, PanelRight, Sparkles, Database, Server, RefreshCw } from './Icons';

export default function Header({
  isSidebarOpen,
  onToggleSidebar,
  isArtifactOpen,
  onToggleArtifact,
  hasArtifact,
  backendStatus,
  dbStatus,
  llmStatus,
  onRefreshHealth
}) {
  return (
    <header className="chat-header">
      <div className="header-left">
        <button
          className="icon-btn sidebar-toggle-btn"
          onClick={onToggleSidebar}
          title={isSidebarOpen ? "Collapse Sidebar" : "Expand Sidebar"}
          aria-label="Toggle Sidebar"
        >
          <Menu size={20} />
        </button>
        <div className="header-title-container">
          <span className="header-app-badge">
            <Sparkles size={14} className="sparkle-icon" /> AI Agent + RAG
          </span>
          <h1 className="header-title">The Lenny Growth Assistant</h1>
        </div>
      </div>

      <div className="header-right">
        {/* Backend, Provider & DB Status Badges */}
        <div className="status-badges">
          {backendStatus?.data?.llm_provider && (
            <div
              className={`status-pill model-pill ${
                llmStatus?.status === 'available' || llmStatus?.status === 'configured'
                  ? 'success'
                  : llmStatus?.status === 'missing_model' || llmStatus?.status === 'unconfigured'
                  ? 'warning'
                  : llmStatus?.status === 'unavailable'
                  ? 'danger'
                  : ''
              }`}
              title={
                llmStatus?.data?.diagnostics?.message ||
                `LLM Provider: ${backendStatus.data.llm_provider} (${backendStatus.data.model})`
              }
            >
              <Sparkles size={12} />
              <span>
                {backendStatus.data.llm_provider} ({backendStatus.data.model})
                {llmStatus?.status === 'missing_model' ? ' [missing model]' : ''}
                {llmStatus?.status === 'unavailable' ? ' [offline]' : ''}
                {llmStatus?.status === 'unconfigured' ? ' [unconfigured]' : ''}
              </span>
            </div>
          )}

          <div
            className={`status-pill ${backendStatus.status === 'healthy' ? 'success' : 'danger'}`}
            title="Backend API Status"
          >
            <Server size={12} />
            <span>API: {backendStatus.status}</span>
          </div>

          <div
            className={`status-pill ${dbStatus.status === 'connected' ? 'success' : 'warning'}`}
            title="PostgreSQL Database Status"
          >
            <Database size={12} />
            <span>DB: {dbStatus.status}</span>
          </div>

          <button
            className="icon-btn refresh-btn"
            onClick={onRefreshHealth}
            title="Re-check Backend & DB Health"
            aria-label="Refresh Health"
          >
            <RefreshCw size={14} />
          </button>
        </div>

        {/* Artifact Panel Toggle Button */}
        <button
          className={`artifact-toggle-btn ${isArtifactOpen ? 'active' : ''} ${hasArtifact ? 'has-artifact' : ''}`}
          onClick={onToggleArtifact}
          title="Toggle Artifact Studio Panel"
        >
          <PanelRight size={18} />
          <span className="btn-text">Artifact Studio</span>
          {hasArtifact && <span className="artifact-indicator"></span>}
        </button>
      </div>
    </header>
  );
}
