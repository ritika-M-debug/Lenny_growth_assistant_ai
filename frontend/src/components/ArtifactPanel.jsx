import React, { useState } from 'react';
import { X, FileText, Code, Copy, Check, Sparkles, Download } from './Icons';
import MarkdownRenderer from './MarkdownRenderer';


export default function ArtifactPanel({
  isOpen,
  onClose,
  artifact,
  artifacts = [],
  onSelectArtifact
}) {
  const [activeTab, setActiveTab] = useState('preview');
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const currentArtifact = artifact || (artifacts && artifacts.length > 0 ? artifacts[0] : null);

  const handleCopy = () => {
    if (!currentArtifact) return;
    navigator.clipboard.writeText(currentArtifact.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!currentArtifact) return;
    const isHtml = currentArtifact.type === 'html';
    const extension = isHtml ? 'html' : 'md';
    const mimeType = isHtml ? 'text/html' : 'text/markdown';
    const blob = new Blob([currentArtifact.content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const cleanTitle = (currentArtifact.title || 'artifact')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
    a.download = `${cleanTitle || 'artifact'}.${extension}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const isHtmlArtifact = currentArtifact?.type === 'html';

  return (
    <aside className="artifact-panel" aria-label="Artifact Studio">
      {/* Panel Header */}
      <div className="panel-header">
        <div className="panel-title-box">
          <Sparkles size={16} className="panel-icon" />
          <h2 className="panel-title" title={currentArtifact?.title || 'Artifact Studio'}>
            {currentArtifact?.title || 'Artifact Studio'}
          </h2>
          {currentArtifact && (
            <span className={`panel-badge ${isHtmlArtifact ? 'badge-html' : 'badge-md'}`}>
              {isHtmlArtifact ? 'HTML/CSS' : 'Markdown'}
            </span>
          )}
        </div>
        <button
          className="icon-btn close-panel-btn"
          onClick={onClose}
          aria-label="Close Artifact Studio"
          title="Close Studio"
        >
          <X size={18} />
        </button>
      </div>

      {/* Multiple Artifact Selector (if more than 1 in conversation) */}
      {artifacts && artifacts.length > 1 && (
        <div className="artifact-selector-bar">
          <span className="selector-label">Artifacts ({artifacts.length}):</span>
          <div className="artifact-pill-list">
            {artifacts.map((art) => (
              <button
                key={art.id}
                className={`artifact-pill ${art.id === currentArtifact?.id ? 'active' : ''}`}
                onClick={() => onSelectArtifact && onSelectArtifact(art)}
                title={art.title}
              >
                {art.title.length > 20 ? `${art.title.slice(0, 20)}...` : art.title}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="panel-toolbar">
        <div className="tabs">
          <button
            className={`tab-btn ${activeTab === 'preview' ? 'active' : ''}`}
            onClick={() => setActiveTab('preview')}
            title="Rendered visual preview"
          >
            <FileText size={14} />
            <span>{isHtmlArtifact ? 'Page Preview' : 'Preview'}</span>
          </button>
          <button
            className={`tab-btn ${activeTab === 'code' ? 'active' : ''}`}
            onClick={() => setActiveTab('code')}
            title="Inspect raw source code"
          >
            <Code size={14} />
            <span>Source Code</span>
          </button>
        </div>

        <div className="panel-action-buttons">
          <button
            className="copy-btn"
            onClick={handleCopy}
            disabled={!currentArtifact}
            title="Copy content to clipboard"
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            <span>{copied ? 'Copied!' : 'Copy'}</span>
          </button>

          <button
            className="download-btn"
            onClick={handleDownload}
            disabled={!currentArtifact}
            title={isHtmlArtifact ? 'Download as .html' : 'Download as .md'}
          >
            <Download size={14} />
            <span>{isHtmlArtifact ? '.html' : '.md'}</span>
          </button>
        </div>
      </div>

      {/* Panel Body Content */}
      <div className="panel-content">
        {!currentArtifact ? (
          <div className="artifact-empty-state">
            <div className="empty-icon-wrap">
              <Sparkles size={28} />
            </div>
            <h3>No Artifact Selected</h3>
            <p>
              Ask Lenny Assistant to generate a <strong>Ship 30 for 30 essay</strong>,
              a <strong>Markdown guide</strong>, or an <strong>HTML landing page</strong>.
            </p>
          </div>
        ) : activeTab === 'preview' ? (
          isHtmlArtifact ? (
            <div className="artifact-iframe-container">
              <div className="iframe-security-banner">
                <span className="security-icon">🔒</span>
                <span>Sandboxed Preview (scripts isolated & disabled)</span>
              </div>
              <iframe
                title={currentArtifact.title}
                className="artifact-iframe"
                sandbox=""
                srcDoc={currentArtifact.content}
              />
            </div>
          ) : (
            <div className="artifact-preview">
              <div className="artifact-paper">
                <MarkdownRenderer content={currentArtifact.content} />
              </div>

            </div>
          )
        ) : (
          <div className="artifact-code">
            <pre>
              <code>{currentArtifact.content}</code>
            </pre>
          </div>
        )}
      </div>

      {/* Panel Footer */}
      <div className="panel-footer">
        <div className="footer-info">
          {currentArtifact ? (
            <>
              <span>{currentArtifact.content ? `${currentArtifact.content.length.toLocaleString()} characters` : ''}</span>
              <span className="footer-dot">•</span>
              <span>PostgreSQL Persisted</span>
            </>
          ) : (
            <span>Ready for Generation</span>
          )}
        </div>
      </div>
    </aside>
  );
}
