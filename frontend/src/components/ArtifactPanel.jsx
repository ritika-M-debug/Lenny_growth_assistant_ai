import React, { useState } from 'react';
import { X, FileText, Code, Copy, Check, Sparkles, Download } from './Icons';

/**
 * Lightweight safe Markdown renderer for React without dangerouslySetInnerHTML
 */
function MarkdownPreview({ content }) {
  if (!content) return null;

  // Helper for inline tokens: **bold**, `code`, *italic*
  const renderInline = (text) => {
    if (!text) return '';
    const parts = [];
    const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
    let lastIndex = 0;
    let match;
    let keyIdx = 0;

    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index));
      }
      const token = match[0];
      if (token.startsWith('**') && token.endsWith('**')) {
        parts.push(<strong key={`b-${keyIdx++}`}>{token.slice(2, -2)}</strong>);
      } else if (token.startsWith('`') && token.endsWith('`')) {
        parts.push(<code key={`c-${keyIdx++}`} className="inline-code">{token.slice(1, -1)}</code>);
      } else if (token.startsWith('*') && token.endsWith('*')) {
        parts.push(<em key={`i-${keyIdx++}`}>{token.slice(1, -1)}</em>);
      }
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }
    return parts.length > 0 ? parts : text;
  };

  const lines = content.split('\n');
  const elements = [];
  let inCodeBlock = false;
  let codeBlockLines = [];
  let codeBlockLang = '';
  let currentList = [];
  let keyCounter = 0;

  const flushList = () => {
    if (currentList.length > 0) {
      elements.push(
        <ul key={`ul-${keyCounter++}`} className="md-list">
          {currentList.map((item, i) => (
            <li key={i} className={item.isChecklist ? 'md-checklist-item' : 'md-list-item'}>
              {item.isChecklist ? (
                <label className="checkbox-label">
                  <input type="checkbox" checked={item.checked} readOnly />
                  <span>{renderInline(item.text)}</span>
                </label>
              ) : (
                renderInline(item.text)
              )}
            </li>
          ))}
        </ul>
      );
      currentList = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code blocks
    if (line.trim().startsWith('```')) {
      flushList();
      if (inCodeBlock) {
        elements.push(
          <div key={`codeblock-${keyCounter++}`} className="md-code-block-wrapper">
            {codeBlockLang && <div className="code-lang-tag">{codeBlockLang}</div>}
            <pre className="md-code-block">
              <code>{codeBlockLines.join('\n')}</code>
            </pre>
          </div>
        );
        inCodeBlock = false;
        codeBlockLines = [];
        codeBlockLang = '';
      } else {
        inCodeBlock = true;
        codeBlockLang = line.trim().slice(3).trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeBlockLines.push(line);
      continue;
    }

    // Horizontal Rule
    if (/^---+$|^\*\*\*+$/.test(line.trim())) {
      flushList();
      elements.push(<hr key={`hr-${keyCounter++}`} className="md-divider" />);
      continue;
    }

    // Headings
    if (line.startsWith('# ')) {
      flushList();
      elements.push(<h1 key={`h1-${keyCounter++}`} className="md-h1">{renderInline(line.slice(2))}</h1>);
      continue;
    }
    if (line.startsWith('## ')) {
      flushList();
      elements.push(<h2 key={`h2-${keyCounter++}`} className="md-h2">{renderInline(line.slice(3))}</h2>);
      continue;
    }
    if (line.startsWith('### ')) {
      flushList();
      elements.push(<h3 key={`h3-${keyCounter++}`} className="md-h3">{renderInline(line.slice(4))}</h3>);
      continue;
    }
    if (line.startsWith('#### ')) {
      flushList();
      elements.push(<h4 key={`h4-${keyCounter++}`} className="md-h4">{renderInline(line.slice(5))}</h4>);
      continue;
    }

    // Blockquote
    if (line.startsWith('> ')) {
      flushList();
      elements.push(
        <blockquote key={`bq-${keyCounter++}`} className="md-blockquote">
          {renderInline(line.slice(2))}
        </blockquote>
      );
      continue;
    }

    // Checklist items: - [ ] or - [x]
    const checklistMatch = line.match(/^[-*]\s+\[([ xX])\]\s+(.*)$/);
    if (checklistMatch) {
      currentList.push({
        isChecklist: true,
        checked: checklistMatch[1].toLowerCase() === 'x',
        text: checklistMatch[2]
      });
      continue;
    }

    // Bullet items: - item or * item
    const bulletMatch = line.match(/^[-*]\s+(.*)$/);
    if (bulletMatch) {
      currentList.push({
        isChecklist: false,
        text: bulletMatch[1]
      });
      continue;
    }

    // Empty lines flush lists
    if (!line.trim()) {
      flushList();
      continue;
    }

    // Standard paragraph
    flushList();
    elements.push(<p key={`p-${keyCounter++}`} className="md-p">{renderInline(line)}</p>);
  }

  flushList();

  return <div className="markdown-render-flow">{elements}</div>;
}

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
                <MarkdownPreview content={currentArtifact.content} />
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
