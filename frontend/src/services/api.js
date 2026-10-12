/**
 * API Service for The Lenny Growth Assistant
 * Communicates with FastAPI backend for persistence in PostgreSQL.
 */

const BACKEND_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/health`);
    if (res.ok) {
      const data = await res.json();
      return { status: 'healthy', data };
    }
    return { status: 'unhealthy', error: 'Server returned error status' };
  } catch (err) {
    return { status: 'unreachable', error: err.message };
  }
}

export async function checkDatabaseHealth() {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/health/db`);
    if (res.ok) {
      const data = await res.json();
      return { status: 'connected', data };
    }
    const data = await res.json().catch(() => ({}));
    return { status: 'disconnected', detail: data.detail || 'Database unreachable' };
  } catch (err) {
    return { status: 'unreachable', error: err.message };
  }
}

export async function checkLLMHealth() {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/health/llm`);
    if (res.ok) {
      const data = await res.json();
      return { status: data.status || 'configured', data };
    }
    return { status: 'unavailable', error: 'LLM diagnostic endpoint unreachable' };
  } catch (err) {
    return { status: 'unreachable', error: err.message };
  }
}

/**
 * Lists all persisted conversations from PostgreSQL.
 */
export async function fetchConversations() {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/api/conversations`);
    if (!res.ok) throw new Error('Failed to load conversations');
    return await res.json();
  } catch (err) {
    console.error('Error fetching conversations:', err);
    return [];
  }
}

/**
 * Creates a new conversation in PostgreSQL.
 */
export async function createConversation(title = 'New Conversation') {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/api/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title })
    });
    if (!res.ok) throw new Error('Failed to create conversation');
    return await res.json();
  } catch (err) {
    console.error('Error creating conversation:', err);
    throw err;
  }
}

/**
 * Fetches a single conversation with its messages in chronological order.
 */
export async function fetchConversationDetail(conversationId) {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/api/conversations/${conversationId}`);
    if (!res.ok) throw new Error('Conversation not found');
    return await res.json();
  } catch (err) {
    console.error(`Error fetching conversation ${conversationId}:`, err);
    throw err;
  }
}

/**
 * Sends a message to a conversation in PostgreSQL and receives mock assistant response.
 */
export async function sendMessageToConversation(conversationId, content) {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/api/conversations/${conversationId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content })
    });
    if (!res.ok) throw new Error('Failed to send message');
    return await res.json();
  } catch (err) {
    console.error('Error sending message:', err);
    throw err;
  }
}

/**
 * Deletes a conversation and its messages from PostgreSQL.
 */
export async function deleteConversation(conversationId) {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/api/conversations/${conversationId}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Failed to delete conversation');
    return await res.json();
  } catch (err) {
    console.error('Error deleting conversation:', err);
    throw err;
  }
}

/**
 * Suggested prompt recommendations for the welcome screen.
 */
export const SUGGESTED_PROMPTS = [
  {
    id: 'pmf',
    icon: '🎯',
    category: 'Product-Market Fit',
    title: 'How do I find product-market fit?',
    subtitle: 'Learn metrics like the 40% rule and retention curve analysis.'
  },
  {
    id: 'activation',
    icon: '⚡',
    category: 'User Activation',
    title: 'How can I improve user activation?',
    subtitle: 'Identify the Aha! moment and reduce time-to-value friction.'
  },
  {
    id: 'growth-loops',
    icon: '🔄',
    category: 'Growth Strategy',
    title: 'What makes a successful growth loop?',
    subtitle: 'Explore viral, content/SEO, and paid acquisition loops.'
  },
  {
    id: 'user-interviews',
    icon: '🗣️',
    category: 'User Research',
    title: 'How should I conduct user interviews?',
    subtitle: 'Apply "The Mom Test" principles to uncover non-obvious pain points.'
  }
];

/**
 * Lists all artifacts for a given conversation.
 */
export async function fetchConversationArtifacts(conversationId) {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/api/conversations/${conversationId}/artifacts`);
    if (!res.ok) throw new Error('Failed to load artifacts');
    return await res.json();
  } catch (err) {
    console.error(`Error fetching artifacts for conversation ${conversationId}:`, err);
    return [];
  }
}

/**
 * Fetches artifact detail by its unique ID.
 */
export async function fetchArtifactDetail(artifactId) {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/api/artifacts/${artifactId}`);
    if (!res.ok) throw new Error('Artifact not found');
    return await res.json();
  } catch (err) {
    console.error(`Error fetching artifact ${artifactId}:`, err);
    throw err;
  }
}

/**
 * Manually creates/persists an artifact for a conversation.
 */
export async function createArtifact(conversationId, artifactData) {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/api/conversations/${conversationId}/artifacts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(artifactData)
    });
    if (!res.ok) throw new Error('Failed to create artifact');
    return await res.json();
  } catch (err) {
    console.error('Error creating artifact:', err);
    throw err;
  }
}

/**
 * Deletes an artifact by ID.
 */
export async function deleteArtifact(artifactId) {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/api/artifacts/${artifactId}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Failed to delete artifact');
    return await res.json();
  } catch (err) {
    console.error('Error deleting artifact:', err);
    throw err;
  }
}
