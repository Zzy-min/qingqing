import { useState, useRef, useEffect } from 'react';
import ModelSelector from '../components/ModelSelector';

export default function Chat() {
  const [model, setModel] = useState('openai:gpt-4o');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const getHeaders = () => {
    const provider = model.split(':')[0];
    const keys = JSON.parse(localStorage.getItem('providerApiKeys') || '{}');
    const urls = JSON.parse(localStorage.getItem('providerBaseUrls') || '{}');
    const secrets = JSON.parse(localStorage.getItem('providerSecrets') || '{}');
    const headers = { 'Content-Type': 'application/json' };
    const keyMap = { openai: 'X-OpenAI-API-Key', google: 'X-Google-API-Key', qwen: 'X-QWEN-API-Key', ernie: 'X-ERNIE-API-Key', zhipu: 'X-ZHIPU-API-Key', minimax: 'X-MiniMax-API-Key' };
    const urlMap = { openai: 'X-OpenAI-Base-URL', qwen: 'X-QWEN-Base-URL' };
    if (keys[provider]) headers[keyMap[provider]] = keys[provider];
    if (urls[provider]) headers[urlMap[provider]] = urls[provider];
    if (secrets.ernie) headers['X-ERNIE-Secret-Key'] = secrets.ernie;
    return headers;
  };

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;
    const userMsg = { role: 'user', content: input.trim() };
    const newMessages = [...messages, userMsg, { role: 'assistant', content: '' }];
    setMessages(newMessages);
    setInput('');
    setIsStreaming(true);

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ model, messages: newMessages.filter(m => m.content).map(m => ({ role: m.role, content: m.content })), stream: true }),
      });

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);
          if (data === '[DONE]') continue;
          try {
            const chunk = JSON.parse(data);
            if (chunk.error) {
              fullContent += `\n\nError: ${chunk.error}`;
            } else {
              fullContent += chunk.delta || '';
            }
            setMessages(prev => {
              const updated = [...prev];
              updated[updated.length - 1] = { ...updated[updated.length - 1], content: fullContent };
              return updated;
            });
          } catch {}
        }
      }
    } catch (err) {
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: 'assistant', content: `Error: ${err.message}` };
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-gray-950 text-gray-100 rounded-2xl overflow-hidden">
      <header className="h-12 bg-gray-900 border-b border-gray-800 flex items-center px-4 gap-4 shrink-0">
        <h1 className="text-sm font-medium">Chat</h1>
        <ModelSelector capability="chat" value={model} onChange={setModel} />
      </header>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            选择模型并开始对话
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[70%] px-4 py-2 rounded-2xl text-sm ${msg.role === 'user' ? 'bg-blue-600' : 'bg-gray-800'}`}>
              <pre className="whitespace-pre-wrap font-sans">{msg.content}</pre>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <div className="p-4 border-t border-gray-800 shrink-0">
        <div className="flex gap-2">
          <input value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="输入消息... (Enter 发送)"
            className="flex-1 px-4 py-2 bg-gray-800 rounded-xl text-sm border border-gray-700 focus:border-blue-500 outline-none"
            disabled={isStreaming} />
          <button onClick={handleSend} disabled={isStreaming}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-xl text-sm">
            {isStreaming ? '...' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
}
