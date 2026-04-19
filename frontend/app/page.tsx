'use client';

import React, { useState, useRef, useEffect } from 'react';

type Message = {
  role: 'user' | 'bot';
  content: string;
  source_url?: string;
};

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'bot',
      content: 'Hello! I am your HDFC Mutual Fund Assistant. Ask me factual questions about HDFC schemes.'
    }
  ]);
  const [inputStr, setInputStr] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  // Single pseudo-session per page load
  const sessionIdRef = useRef(`web-${Math.random().toString(36).substring(7)}`);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputStr.trim()) return;

    const userMessage = inputStr.trim();
    setInputStr('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          query: userMessage
        }),
      });

      if (!res.ok) {
        throw new Error(`API responded with status: ${res.status}`);
      }

      const data = await res.json();
      setMessages(prev => [...prev, {
        role: 'bot',
        content: data.answer,
        source_url: data.source_url
      }]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, {
        role: 'bot',
        content: 'Sorry, I am having trouble connecting to the server. Please check my connection or API Keys.'
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.brandContainer}>
          <div style={styles.logoCircle} />
          <h1 style={styles.title}>HDFC MF Assistant</h1>
        </div>
        <div style={styles.badge}>Beta</div>
      </header>

      {/* Main Chat Area */}
      <section style={styles.chatArea}>

        {/* Example Questions - visible only initially */}
        {messages.length === 1 && (
          <div style={styles.examplesWrapper}>
            <div 
              style={styles.exampleChip} 
              onClick={() => setInputStr("What is the expense ratio of HDFC ELSS Tax Saver?")}
            >
              "What is the expense ratio of HDFC ELSS Tax Saver?"
            </div>
            <div 
              style={styles.exampleChip} 
              onClick={() => setInputStr("What is the minimum SIP for HDFC Mid Cap?")}
            >
              "What is the minimum SIP for HDFC Mid Cap?"
            </div>
            <div 
              style={styles.exampleChip} 
              onClick={() => setInputStr("How do I download my capital gains statement?")}
            >
              "How do I download my capital gains statement?"
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div 
            key={idx} 
            className="animate-enter"
            style={{
              ...styles.messageRow,
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
            }}
          >
            <div style={msg.role === 'user' ? styles.bubbleUser : styles.bubbleBot}>
              <p style={styles.messageText}>{msg.content}</p>
              
              {msg.source_url && (
                <div style={styles.sourceBox}>
                  <strong>Source:</strong>{' '}
                  <a href={msg.source_url} target="_blank" rel="noopener noreferrer" style={{color: 'inherit'}}>
                    {msg.source_url}
                  </a>
                </div>
              )}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div style={{...styles.messageRow, justifyContent: 'flex-start'}} className="animate-enter">
            <div style={{...styles.bubbleBot, minHeight: '44px', display: 'flex', alignItems: 'center'}}>
              <div className="typing-indicator">
                <span />
                <span />
                <span />
              </div>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </section>

      {/* Input Area & Footer */}
      <footer style={styles.footer}>
        <form onSubmit={handleSend} style={styles.form}>
          <input 
            type="text" 
            placeholder="Ask about ELSS, Mid Cap, or expense ratios..." 
            value={inputStr}
            onChange={(e) => setInputStr(e.target.value)}
            disabled={isLoading}
            style={styles.input}
          />
          <button 
            type="submit" 
            disabled={isLoading || !inputStr.trim()}
            style={styles.sendButton}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </form>
        <div style={styles.disclaimerText}>
          Facts-only. No investment advice.
        </div>
      </footer>
    </main>
  );
}

// Inline styles substituting tailwind for full control & vanilla aesthetics
const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: '900px',
    margin: '0 auto',
    height: '100vh',
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
  },
  header: {
    padding: '24px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid var(--border-color)',
    backdropFilter: 'blur(10px)',
    backgroundColor: 'rgba(11, 13, 17, 0.8)',
    position: 'sticky',
    top: 0,
    zIndex: 10,
  },
  brandContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  logoCircle: {
    width: '32px',
    height: '32px',
    borderRadius: '12px',
    background: 'var(--chat-user-bg)',
    boxShadow: '0 4px 12px rgba(0, 205, 172, 0.2)',
  },
  title: {
    fontSize: '20px',
    fontWeight: 600,
  },
  badge: {
    padding: '4px 12px',
    borderRadius: '16px',
    background: 'rgba(255, 255, 255, 0.05)',
    border: '1px solid var(--border-color)',
    fontSize: '12px',
    fontWeight: 500,
    color: 'var(--text-secondary)',
  },
  examplesWrapper: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    padding: '0 12px',
    marginBottom: '16px',
  },
  exampleChip: {
    background: 'var(--surface-color)',
    border: '1px solid var(--border-color)',
    padding: '12px 16px',
    borderRadius: '12px',
    color: 'var(--text-secondary)',
    fontSize: '14px',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  chatArea: {
    flex: 1,
    overflowY: 'auto',
    padding: '32px 24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
  },
  messageRow: {
    display: 'flex',
    width: '100%',
  },
  bubbleUser: {
    maxWidth: '85%',
    background: 'var(--chat-user-bg)',
    color: '#fff',
    padding: '16px 20px',
    borderRadius: '20px 20px 4px 20px',
    fontSize: '15px',
    lineHeight: '1.6',
    boxShadow: '0 4px 15px rgba(0, 82, 204, 0.15)',
  },
  bubbleBot: {
    maxWidth: '85%',
    background: 'var(--chat-bot-bg)',
    color: 'var(--text-primary)',
    padding: '16px 20px',
    borderRadius: '20px 20px 20px 4px',
    fontSize: '15px',
    lineHeight: '1.6',
    border: '1px solid var(--border-color)',
    backdropFilter: 'blur(12px)',
  },
  messageText: {
    whiteSpace: 'pre-wrap',
  },
  sourceBox: {
    marginTop: '12px',
    padding: '10px 12px',
    background: 'rgba(0,0,0, 0.3)',
    borderRadius: '8px',
    fontSize: '13px',
    color: 'var(--text-secondary)',
    wordBreak: 'break-all',
  },
  footer: {
    padding: '24px',
    backgroundColor: 'var(--bg-color)',
    position: 'sticky',
    bottom: 0,
    borderTop: '1px solid var(--border-color)',
  },
  form: {
    display: 'flex',
    gap: '12px',
    position: 'relative',
    background: 'var(--surface-color)',
    padding: '8px',
    borderRadius: '24px',
    border: '1px solid var(--border-color)',
    boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
  },
  input: {
    flex: 1,
    background: 'transparent',
    border: 'none',
    outline: 'none',
    color: 'var(--text-primary)',
    fontSize: '15px',
    padding: '8px 16px',
  },
  sendButton: {
    width: '44px',
    height: '44px',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'var(--chat-user-bg)',
    color: 'white',
    border: 'none',
    cursor: 'pointer',
    transition: 'transform 0.2s ease, opacity 0.2s',
  },
  disclaimerText: {
    textAlign: 'center',
    fontSize: '12px',
    color: 'var(--text-secondary)',
    marginTop: '12px',
  }
};
