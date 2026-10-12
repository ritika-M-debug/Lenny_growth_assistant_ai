import React from 'react';
import { Plus, MessageSquare, Compass, Sparkles, ChevronLeft, Trash2 } from './Icons';

const TOPIC_CATEGORIES = [
  { id: 'pm', name: 'Product Management', icon: '🎯' },
  { id: 'growth', name: 'Growth Strategy', icon: '⚡' },
  { id: 'research', name: 'User Research', icon: '🗣️' },
  { id: 'pmf', name: 'Product-Market Fit', icon: '🔄' }
];

function formatConversationDateTime(dateValue) {
  if (!dateValue) return '';
  try {
    const d = new Date(dateValue);
    if (isNaN(d.getTime())) return '';
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const yesterday = new Date();
    yesterday.setDate(now.getDate() - 1);
    const isYesterday = d.toDateString() === yesterday.toDateString();

    if (isToday) {
      return `Today, ${timeStr}`;
    } else if (isYesterday) {
      return `Yesterday, ${timeStr}`;
    } else {
      const dateStr = d.toLocaleDateString([], { month: 'short', day: 'numeric' });
      return `${dateStr}, ${timeStr}`;
    }
  } catch {
    return '';
  }
}


export default function Sidebar({
  isOpen,
  onClose,
  onNewChat,
  conversations = [],
  activeChatId,
  onSelectConversation,
  onDeleteConversation,
  onSelectTopicPrompt
}) {
  return (
    <aside className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
      {/* Mobile Close Button */}
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <div className="brand-avatar">L</div>
          <div className="brand-text">
            <span className="brand-name">Lenny Assistant</span>
            <span className="brand-tag">Growth & PM AI</span>
          </div>
        </div>
        <button
          className="icon-btn close-sidebar-btn"
          onClick={onClose}
          aria-label="Close sidebar"
        >
          <ChevronLeft size={20} />
        </button>
      </div>

      {/* New Chat Button */}
      <div className="sidebar-action">
        <button className="new-chat-btn" onClick={onNewChat}>
          <Plus size={18} />
          <span>New Chat</span>
        </button>
      </div>

      <div className="sidebar-scrollable">
        {/* Conversation History Section */}
        <div className="sidebar-section">
          <h3 className="section-label">
            <MessageSquare size={14} />
            <span>Persisted Conversations ({conversations.length})</span>
          </h3>
          <div className="history-list">
            {conversations.length === 0 ? (
              <div className="empty-history-text">No saved conversations yet.</div>
            ) : (
              conversations.map((chat) => (
                <div
                  key={chat.id}
                  className={`history-item-wrapper ${activeChatId === chat.id ? 'active' : ''}`}
                >
                  <button
                    className="history-item"
                    onClick={() => onSelectConversation(chat.id)}
                  >
                    <MessageSquare size={15} className="item-icon" />
                    <div className="item-details">
                      <span className="item-title">{chat.title}</span>
                      <span className="item-meta">
                        {formatConversationDateTime(chat.updatedAt || chat.updated_at || chat.createdAt || chat.created_at)}
                      </span>

                    </div>
                  </button>

                  <button
                    className="delete-item-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteConversation(chat.id);
                    }}
                    title="Delete Conversation"
                    aria-label="Delete conversation"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Example Topics Section */}
        <div className="sidebar-section">
          <h3 className="section-label">
            <Compass size={14} />
            <span>Explore Topics</span>
          </h3>
          <div className="topics-list">
            {TOPIC_CATEGORIES.map((topic) => (
              <button
                key={topic.id}
                className="topic-pill"
                onClick={() => onSelectTopicPrompt(topic.name)}
              >
                <span className="topic-emoji">{topic.icon}</span>
                <span className="topic-name">{topic.name}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Sidebar Footer */}
      <div className="sidebar-footer">
        <div className="system-info">
          <Sparkles size={14} className="info-icon" />
          <span>PostgreSQL Persisted Chat Engine</span>
        </div>
      </div>
    </aside>
  );
}
