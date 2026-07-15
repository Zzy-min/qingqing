import { useEffect, useState } from 'react'
import { apiFetch } from '../services/qingqingApi'

const tierLabel = (tier) => ({ fast: '快速', medium: '均衡', slow: '精细', low: '低消耗', high: '高消耗' }[tier] || tier || '')

export default function ModelSelector({ capability, label = '模型', value = 'auto', onChange }) {
  const [models, setModels] = useState([])

  useEffect(() => {
    const query = capability ? `?capability=${encodeURIComponent(capability)}` : ''
    apiFetch(`/api/v1/models${query}`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('模型列表加载失败')))
      .then((payload) => setModels(Array.isArray(payload) ? payload : (payload.data || payload.models || [])))
      .catch(() => setModels([]))
  }, [capability])

  return (
    <label className="flex items-center gap-2 text-sm">
      <span>{label}</span>
      <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}
        className="bg-gray-800 text-sm rounded-lg px-3 py-1.5 border border-gray-700">
        <option value="auto">Auto · 推荐</option>
        {models.map((model) => {
          const available = model.availability === 'available' || model.available === true
          const meta = [tierLabel(model.speed_tier), tierLabel(model.cost_tier)].filter(Boolean).join(' · ')
          return (
            <option key={model.id} value={model.id} disabled={!available}>
              {model.display_name}{meta ? ` · ${meta}` : ''}{available ? '' : ` · ${model.unavailable_reason || '暂不可用'}`}
            </option>
          )
        })}
      </select>
    </label>
  )
}
