import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, User, BookOpen, PanelRight, AlertCircle, RefreshCw } from './Icons';
import { SUGGESTED_PROMPTS } from '../services/api';

export default function ChatArea({
  messages,
  onSendMessage,
  isLoading,
  onPromptClick,
  onOpenArtifact,
  onResetChat,
  onRetry,
  error
}) {
  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom of chat when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (!inputText.trim() || isLoading) return;
    onSendMessage(inputText);
    setInputText('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <main className="chat-main-container">
      {/* Error banner if local UI operation fails */}
      {error && (
        <div className="error-banner">
          <AlertCircle size={16} />
          <span>{error}</span>
          {onRetry && messages.length > 0 && (
            <button
              className="retry-query-btn"
              onClick={() => onRetry()}
              title="Retry last query"
              type="button"
              style={{ marginLeft: 'auto' }}
            >
              <RefreshCw size={12} />
              <span>Retry</span>
            </button>
          )}
        </div>
      )}

      {/* WELCOME SCREEN (When no messages exist) */}
      {messages.length === 0 ? (
        <div className="welcome-screen">
          <div className="welcome-hero">
            <div className="welcome-icon">
              <Sparkles size={32} />
            </div>
            <h1 className="welcome-title">The Lenny Growth Assistant</h1>
            <p className="welcome-subtitle">
              Your AI-powered conversational advisor for product management, growth strategies, and user acquisition frameworks — synthesized from Lenny's Podcast transcripts.
            </p>
          </div>

          {/* Suggested Prompt Cards */}
          <div className="prompts-grid">
            {SUGGESTED_PROMPTS.map((prompt) => (
              <button
                key={prompt.id}
                className="prompt-card"
                onClick={() => onPromptClick(prompt.title)}
              >
                <div className="card-header">
                  <span className="card-icon">{prompt.icon}</span>
                  <span className="card-category">{prompt.category}</span>
                </div>
                <h3 className="card-question">{prompt.title}</h3>
                <p className="card-sub">{prompt.subtitle}</p>
              </button>
            ))}
          </div>
        </div>
      ) : (
        /* MESSAGES LIST (When conversation is active) */
        <div className="messages-container">
          <div className="chat-controls-top">
            <button className="reset-chat-btn" onClick={onResetChat}>
              <RefreshCw size={13} />
              <span>Reset Chat</span>
            </button>
          </div>

          {messages.map((msg, index) => (
            <div
              key={msg.id || index}
              className={`message-row ${msg.sender === 'user' ? 'user-row' : 'assistant-row'}`}
            >
              <div className="avatar">
                {msg.sender === 'user' ? (
                  <User size={18} />
                ) : (
                  <div className="bot-avatar">L</div>
                )}
              </div>

              <div className="message-content">
                <div className="message-header">
                  <span className="sender-name">
                    {msg.sender === 'user' ? 'You' : 'Lenny Assistant'}
                  </span>
                  {msg.provider && (
                    <span className="provider-badge">
                      {msg.provider} ({msg.model})
                    </span>
                  )}
                  {msg.timestamp && (
                    <span className="message-time">{msg.timestamp}</span>
                  )}
                </div>

                <div className="message-text">
                  <p className="text-body">{msg.text}</p>
                </div>

                {/* Grounded Sources & Citations Area */}
                {msg.citations && msg.citations.length > 0 ? (
                  <div className="citations-box">
                    <div className="citations-header">
                      <BookOpen size={14} />
                      <span>Grounded Knowledge Base Sources ({msg.citations.length})</span>
                    </div>
                    <div className="citations-grid">
                      {msg.citations.map((src, i) => (
                        <div key={i} className="citation-card">
                          <div className="citation-card-header">
                            <span className="citation-badge">Source [{src.source_number || i + 1}]</span>
                            <span className="citation-type">{src.source_type || 'document'}</span>
                          </div>
                          <div className="citation-card-title">
                            {src.source_url && (src.source_url.startsWith('https://') || src.source_url.startsWith('http://')) ? (
                              <a href={src.source_url} target="_blank" rel="noopener noreferrer" className="citation-link">
                                {src.title} ↗
                              </a>
                            ) : (
                              <span>{src.title}</span>
                            )}
                          </div>
                          {src.author && <div className="citation-author">Author/Speaker: {src.author}</div>}
                          {src.snippet && <div className="citation-snippet">"{src.snippet}"</div>}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : msg.sender === 'assistant' && msg.status === 'empty_kb' && (
                  <div className="empty-kb-notice">
                    <span>💡 General AI Guidance (No relevant transcript sources found in Knowledge Base)</span>
                  </div>
                )}

                {/* Error State with Retry Button */}
                {msg.sender === 'assistant' && msg.status === 'error' && (
                  <div className="message-error-box">
                    <AlertCircle size={14} />
                    <span>Generation Failed</span>
                    {onRetry && (
                      <button
                        className="retry-query-btn"
                        onClick={() => onRetry(index)}
                        title="Retry query"
                        type="button"
                      >
                        <RefreshCw size={12} />
                        <span>Retry</span>
                      </button>
                    )}
                  </div>
                )}


                {/* Artifact Trigger Button */}
                {msg.artifact && (
                  <div className="artifact-trigger-box">
                    <button
                      className="open-artifact-btn"
                      onClick={() => onOpenArtifact(msg.artifact)}
                    >
                      <PanelRight size={15} />
                      <span>View Artifact: {msg.artifact.title}</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Loading Indicator */}
          {isLoading && (
            <div className="message-row assistant-row loading-row">
              <div className="avatar">
                <div className="bot-avatar">L</div>
              </div>
              <div className="message-content">
                <div className="loading-indicator">
                  <div className="dot"></div>
                  <div className="dot"></div>
                  <div className="dot"></div>
                  <span className="loading-text">Synthesizing response...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      )}

      {/* CHAT INPUT AREA */}
      <div className="chat-input-wrapper">
        <form className="chat-input-form" onSubmit={handleSubmit}>
          <textarea
            className="chat-textarea"
            placeholder="Ask about product strategy, growth loops, activation, or retention..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button
            type="submit"
            className="send-btn"
            disabled={!inputText.trim() || isLoading}
            title="Send Message (Enter)"
            aria-label="Send message"
          >
            <Send size={18} />
          </button>
        </form>
        <div className="input-footer">
          <span>Press <strong>Enter</strong> to send, <strong>Shift + Enter</strong> for new line</span>
        </div>
      </div>
    </main>
  );
}
