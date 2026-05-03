import { useState, useEffect } from 'react';

export default function ModelSelector({ capability, value, onChange }) {
  const [models, setModels] = useState({});

  useEffect(() => {
    fetch('/api/models')
      .then(r => r.json())
      .then(data => {
        if (data.success) setModels(data.data.models);
      })
      .catch(console.error);
  }, []);

  const filtered = Object.entries(models)
    .filter(([_, m]) => m.enabled && m.capabilities.includes(capability))
    .sort((a, b) => a[1].provider.localeCompare(b[1].provider));

  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      className="bg-gray-800 text-sm rounded-lg px-3 py-1.5 border border-gray-700">
      {filtered.length === 0 && <option>无可用模型</option>}
      {Object.entries(
        filtered.reduce((acc, [id, m]) => {
          (acc[m.provider] = acc[m.provider] || []).push({ id, ...m });
          return acc;
        }, {})
      ).map(([provider, modelList]) => (
        <optgroup key={provider} label={provider}>
          {modelList.map(m => (
            <option key={m.id} value={m.id}>{m.display_name}{m.supports_vision ? ' \u{1F441}' : ''}</option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
