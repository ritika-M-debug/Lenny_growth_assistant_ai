import React, { useState, useEffect } from 'react';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';
import ChatArea from '../components/ChatArea';
import ArtifactPanel from '../components/ArtifactPanel';
import {
  checkBackendHealth,
  checkDatabaseHealth,
  checkLLMHealth,
  fetchConversations,
  createConversation,
  fetchConversationDetail,
  sendMessageToConversation,
  deleteConversation,
  fetchConversationArtifacts
} from '../services/api';

export default function ChatPage() {
  const [conversations, setConversations] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Sidebar & Artifact Panel state
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isArtifactOpen, setIsArtifactOpen] = useState(false);
  const [activeArtifact, setActiveArtifact] = useState(null);
  const [conversationArtifacts, setConversationArtifacts] = useState([]);

  // System Health
  const [backendStatus, setBackendStatus] = useState({ status: 'checking...' });
  const [dbStatus, setDbStatus] = useState({ status: 'checking...' });
  const [llmStatus, setLlmStatus] = useState(null);

  const refreshHealth = async () => {
    const bRes = await checkBackendHealth();
    setBackendStatus(bRes);
    const dRes = await checkDatabaseHealth();
    setDbStatus(dRes);
    const lRes = await checkLLMHealth();
    setLlmStatus(lRes);
  };

  const loadConversations = async () => {
    const list = await fetchConversations();
    setConversations(list);
    return list;
  };

  useEffect(() => {
    refreshHealth();
    loadConversations();
  }, []);

  // Format backend message list for UI rendering
  const formatMessagesForUI = (rawMessages = []) => {
    return rawMessages.map((msg) => {
      const metadata = msg.metadata_json || {};
      const citations = msg.citations || metadata.citations || [];
      const artifact = msg.artifact || metadata.artifact || null;
      return {
        id: msg.id,
        sender: msg.role === 'user' ? 'user' : 'assistant',
        text: msg.content,
        timestamp: new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: citations,
        artifact: artifact,
        provider: metadata.provider,
        model: metadata.model,
        status: metadata.status
      };
    });
  };

  // Select existing conversation
  const handleSelectConversation = async (convId) => {
    try {
      setError(null);
      setIsLoading(true);
      const detail = await fetchConversationDetail(convId);
      setActiveChatId(convId);
      const formatted = formatMessagesForUI(detail.messages || []);
      setMessages(formatted);

      // Load persisted artifacts for this conversation
      const arts = await fetchConversationArtifacts(convId);
      setConversationArtifacts(arts || []);
      if (arts && arts.length > 0) {
        setActiveArtifact(arts[0]);
      } else {
        const msgArt = formatted.slice().reverse().find((m) => m.artifact)?.artifact;
        setActiveArtifact(msgArt || null);
      }

      if (window.innerWidth < 768) setIsSidebarOpen(false);
    } catch (err) {
      setError('Failed to load conversation messages.');
    } finally {
      setIsLoading(false);
    }
  };

  // New Chat Handler
  const handleNewChat = async () => {
    try {
      setError(null);
      const newConv = await createConversation('New Conversation');
      setActiveChatId(newConv.id);
      setMessages([]);
      setActiveArtifact(null);
      setConversationArtifacts([]);
      setIsArtifactOpen(false);
      await loadConversations();
    } catch (err) {
      setError('Failed to create new conversation.');
    }
  };

  // Delete Conversation Handler
  const handleDeleteConversation = async (convId) => {
    try {
      setError(null);
      await deleteConversation(convId);
      if (activeChatId === convId) {
        setActiveChatId(null);
        setMessages([]);
        setActiveArtifact(null);
        setConversationArtifacts([]);
        setIsArtifactOpen(false);
      }
      await loadConversations();
    } catch (err) {
      setError('Failed to delete conversation.');
    }
  };

  // Select Topic Prompt
  const handleSelectTopicPrompt = async (topicName) => {
    const promptText = `Can you provide key frameworks and insights on ${topicName}?`;
    await handleSendMessage(promptText);
  };

  // Prompt Card Click
  const handlePromptClick = async (promptTitle) => {
    await handleSendMessage(promptTitle);
  };

  // Send Message Handler
  const handleSendMessage = async (text) => {
    if (isLoading) return; // Prevent duplicate submissions

    let currentConvId = activeChatId;

    try {
      setError(null);
      setIsLoading(true);

      // Create conversation if none active
      if (!currentConvId) {
        const newConv = await createConversation(text.slice(0, 30));
        currentConvId = newConv.id;
        setActiveChatId(currentConvId);
      }

      // Optimistically show user message in UI
      const tempUserMsg = {
        id: `temp-${Date.now()}`,
        sender: 'user',
        text,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages((prev) => [...prev, tempUserMsg]);

      // Call backend API to save user message and receive assistant response
      const assistantMsg = await sendMessageToConversation(currentConvId, text);

      // Reload updated messages from PostgreSQL
      const detail = await fetchConversationDetail(currentConvId);
      const formatted = formatMessagesForUI(detail.messages || []);
      setMessages(formatted);

      // Reload artifacts for this conversation
      const arts = await fetchConversationArtifacts(currentConvId);
      setConversationArtifacts(arts || []);

      // If the response generated an artifact, set it active and auto-open the panel
      const newArtifact =
        assistantMsg?.artifact ||
        assistantMsg?.metadata_json?.artifact ||
        (arts && arts.length > 0 ? arts[0] : null);

      if (newArtifact) {
        setActiveArtifact(newArtifact);
        setIsArtifactOpen(true);
      }

      // Refresh sidebar list to update titles and chronological timestamps
      await loadConversations();
    } catch (err) {
      setError('Failed to persist message to backend.');
    } finally {
      setIsLoading(false);
    }
  };

  // Retry previous prompt on assistant error
  const handleRetry = async (assistantIndex) => {
    if (isLoading) return;
    const targetIdx = assistantIndex !== undefined ? assistantIndex : messages.length;
    for (let i = targetIdx - 1; i >= 0; i--) {
      if (messages[i]?.sender === 'user') {
        await handleSendMessage(messages[i].text);
        break;
      }
    }
  };

  // Open Artifact Panel
  const handleOpenArtifact = (artifact) => {
    setActiveArtifact(artifact);
    setIsArtifactOpen(true);
  };

  return (
    <div className="chat-page-layout">
      {/* Header Bar */}
      <Header
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        isArtifactOpen={isArtifactOpen}
        onToggleArtifact={() => setIsArtifactOpen(!isArtifactOpen)}
        hasArtifact={Boolean(activeArtifact || conversationArtifacts.length > 0)}
        backendStatus={backendStatus}
        dbStatus={dbStatus}
        llmStatus={llmStatus}
        onRefreshHealth={refreshHealth}
      />

      <div className="chat-body-layout">
        {/* Left Sidebar */}
        <Sidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          onNewChat={handleNewChat}
          conversations={conversations}
          activeChatId={activeChatId}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
          onSelectTopicPrompt={handleSelectTopicPrompt}
        />

        {/* Main Central Chat Area */}
        <ChatArea
          messages={messages}
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          onPromptClick={handlePromptClick}
          onOpenArtifact={handleOpenArtifact}
          onResetChat={() => {
            setActiveChatId(null);
            setMessages([]);
            setActiveArtifact(null);
            setConversationArtifacts([]);
            setIsArtifactOpen(false);
          }}
          onRetry={handleRetry}
          error={error}
        />

        {/* Right Artifact Studio Panel */}
        <ArtifactPanel
          isOpen={isArtifactOpen}
          onClose={() => setIsArtifactOpen(false)}
          artifact={activeArtifact}
          artifacts={conversationArtifacts}
          onSelectArtifact={(art) => setActiveArtifact(art)}
        />
      </div>
    </div>
  );
}
