import { useState, useRef, useEffect } from 'react';
import ModelSelector from '../components/ModelSelector';
import { useWorkbench } from '../context/WorkbenchContext';
import { apiFetch } from '../services/qingqingApi';

export default function Chat() {
  const { settings } = useWorkbench();
  const [model, setModel] = useState('auto');
  const [routeInfo, setRouteInfo] = useState(null);
  const [pendingRun, setPendingRun] = useState(null);
  const [routeError, setRouteError] = useState('');
  const [showRouting, setShowRouting] = useState(false);
  const [budgetLimit, setBudgetLimit] = useState('10');
  const [stageOverrides, setStageOverrides] = useState({});
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;
    const userMsg = { role: 'user', content: input.trim() };
    const newMessages = [...messages, userMsg, { role: 'assistant', content: '' }];
    setMessages(newMessages);
    setInput('');
    setIsStreaming(true);

    try {
      const routing = { mode: model === 'auto' ? 'auto' : 'preferred', credential_preference: settings.credentialPreference || 'platform_first', preferred_model_id: model === 'auto' ? null : model, stage_overrides: stageOverrides, budget_limit: budgetLimit === '' ? null : Number(budgetLimit) };
      setRouteError('');
      const previewResp = await apiFetch('/api/v1/model-routes/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capability: 'chat', ...routing }),
      });
      if (!previewResp.ok) {
        const failure = await previewResp.json().catch(() => ({}));
        setRouteError(`路由预览失败：${failure.detail || '暂时无法选择模型'}`);
        throw new Error(failure.detail || '路由预览失败');
      }
      const preview = await previewResp.json();
      setRouteInfo(preview?.data || preview);
      const requestId = typeof crypto?.randomUUID === 'function' ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
      const resp = await apiFetch('/api/v1/agent/runs', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestId }, body: JSON.stringify({ goal: userMsg.content, routing }) });
      if (!resp.ok) throw new Error((await resp.json().catch(() => ({}))).detail || '创建任务失败');
      const run = await resp.json();
      if (run.status === 'awaiting_approval') setPendingRun(run);
      if (run.status === 'planned') await apiFetch(`/api/v1/agent/runs/${encodeURIComponent(run.id)}/execute`, { method: 'POST' });
      const content = run.status === 'awaiting_approval' ? `任务预计消耗 ${run.estimated_cost} 额度，超过你的预算，需要确认后继续。` : (run.message || run.summary || `任务已开始执行（${run.id || run.run_id || '处理中'}）`);
      setMessages(prev => { const updated = [...prev]; updated[updated.length - 1] = { role: 'assistant', content }; return updated; });
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

  const resolveApproval = async (action) => {
    if (!pendingRun) return;
    const response = await apiFetch(`/api/v1/agent/runs/${encodeURIComponent(pendingRun.id)}/${action}`, { method: 'POST' });
    if (!response.ok) return setRouteError(action === 'approve' ? '任务确认失败，请重试' : '取消任务失败，请重试');
    const run = await response.json();
    if (action === 'approve') await apiFetch(`/api/v1/agent/runs/${encodeURIComponent(run.id)}/execute`, { method: 'POST' });
    setPendingRun(null);
    setMessages((current) => [...current, { role: 'assistant', content: action === 'approve' ? `已确认预算，任务 ${run.id} 等待执行。` : `任务 ${run.id} 已取消。` }]);
  };

  return (
    <div className="flex h-[calc(100dvh-24rem)] min-h-[420px] flex-col overflow-hidden rounded-2xl bg-gray-950 text-gray-100 md:h-[calc(100vh-4rem)]">
      <header className="h-12 bg-gray-900 border-b border-gray-800 flex items-center px-4 gap-4 shrink-0">
        <h1 className="text-sm font-medium">Chat</h1>
        <ModelSelector capability="chat" value={model} onChange={setModel} />
        <button type="button" aria-label="模型安排" className="text-xs text-blue-300" onClick={() => setShowRouting((value) => !value)}>模型安排</button>
      </header>
      {showRouting && <div className="grid grid-cols-2 gap-3 border-b border-gray-800 bg-gray-900 p-4 md:grid-cols-3">
        {[['chat', '文本理解与规划'], ['image', '图片理解/生成'], ['tts', '语音'], ['music', '音乐'], ['video', '视频']].map(([capability, label]) => <ModelSelector key={capability} label={label} capability={capability} value={stageOverrides[capability] || 'auto'} onChange={(value) => setStageOverrides((current) => value === 'auto' ? Object.fromEntries(Object.entries(current).filter(([key]) => key !== capability)) : { ...current, [capability]: value })} />)}
        <label className="text-sm">任务预算<input aria-label="任务预算" type="number" min="0" step="0.1" value={budgetLimit} onChange={(event) => setBudgetLimit(event.target.value)} className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5" /></label>
      </div>}
      {(routeInfo || routeError) && <div className={`border-b px-4 py-3 text-xs ${routeError ? 'border-red-800 bg-red-950 text-red-200' : 'border-emerald-800 bg-emerald-950 text-emerald-100'}`}>
        {routeError || <><strong>{routeInfo.selected_model?.display_name || 'Auto 已完成路由'}</strong> · {routeInfo.reason || '质量、成本与可用性平衡'} · 预估 {routeInfo.estimated_cost?.max == null ? '由供应商结算' : `${routeInfo.estimated_cost.min}–${routeInfo.estimated_cost.max} 额度`}{routeInfo.byok_cost_notice ? '（BYOK 费用以供应商账单为准）' : ''}</>}
      </div>}
      {pendingRun && <div className="flex items-center justify-between gap-4 border-b border-amber-700 bg-amber-950 px-4 py-3 text-sm text-amber-100">
        <span>预计消耗 {pendingRun.estimated_cost} 额度，超出任务预算。</span>
        <span className="flex gap-2"><button className="rounded-lg bg-amber-300 px-3 py-1 text-amber-950" onClick={() => resolveApproval('approve')}>确认执行</button><button className="rounded-lg border border-amber-600 px-3 py-1" onClick={() => resolveApproval('cancel')}>取消任务</button></span>
      </div>}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            告诉轻青你想创作什么，默认由 Auto 选择合适模型
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
            className="min-w-0 flex-1 px-4 py-2 bg-gray-800 rounded-xl text-sm border border-gray-700 focus:border-blue-500 outline-none"
            disabled={isStreaming} />
          <button onClick={handleSend} disabled={isStreaming}
            className="shrink-0 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-xl text-sm">
            {isStreaming ? '...' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
}
