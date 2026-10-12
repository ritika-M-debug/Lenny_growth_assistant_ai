import React, { useState, useEffect } from 'react';
import ChatPage from './pages/ChatPage';
import './styles/global.css';
import './styles/chat.css';

export default function App() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('lenny_assistant_theme') || 'dark';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('lenny_assistant_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  return <ChatPage theme={theme} onToggleTheme={toggleTheme} />;
}

