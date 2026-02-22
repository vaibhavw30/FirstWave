import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../../constants';

const EXAMPLE_PROMPTS = [
  'Yankees game Friday night?',
  'Heavy storm Tuesday evening?',
  'Quiet Monday 4 AM?',
];

function buildContext(heatmapData, counterfactualData, controls) {
  const topZones = [];
  if (heatmapData?.features) {
    const sorted = [...heatmapData.features]
      .sort((a, b) => (b.properties.predicted_count || 0) - (a.properties.predicted_count || 0))
      .slice(0, 10);
    for (const f of sorted) {
      topZones.push({
        zone: f.properties.zone,
        borough: f.properties.borough,
        count: parseFloat(f.properties.predicted_count) || 0,
      });
    }
  }
  const coverage = {};
  if (counterfactualData) {
    coverage.pct_static = counterfactualData.pct_within_8min_static;
    coverage.pct_staged = counterfactualData.pct_within_8min_staged;
    coverage.median_saved_sec = counterfactualData.median_seconds_saved;
  }
  return {
    hour: controls.hour,
    dow: controls.dow,
    weather: controls.weather,
    ambulances: controls.ambulances,
    top_zones: topZones,
    coverage,
  };
}

export default function AiPanel({ heatmapData, counterfactualData, controls, onControlsUpdate }) {
  const [isOpen, setIsOpen] = useState(false);
  const [briefing, setBriefing] = useState('');
  const [isBriefingLoading, setIsBriefingLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const briefingTimerRef = useRef(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Auto-briefing: debounced 1.5s after heatmapData changes
  const fetchBriefing = useCallback(async () => {
    setIsBriefingLoading(true);
    try {
      const { data } = await axios.post(`${API_BASE_URL}/api/ai`, {
        message: null,
        context: buildContext(heatmapData, counterfactualData, controls),
      });
      setBriefing(data.reply || '');
    } catch (err) {
      console.warn('AI briefing error:', err.message);
      setBriefing('AI briefing unavailable — check backend connection.');
    } finally {
      setIsBriefingLoading(false);
    }
  }, [heatmapData, counterfactualData, controls]);

  useEffect(() => {
    if (!heatmapData) return;
    clearTimeout(briefingTimerRef.current);
    briefingTimerRef.current = setTimeout(() => fetchBriefing(), 1500);
    return () => clearTimeout(briefingTimerRef.current);
  }, [heatmapData, fetchBriefing]);

  // Chat send — captures prevControls for undo
  const handleSend = useCallback(async (textOverride) => {
    const text = (textOverride ?? inputText).trim();
    if (!text || isChatLoading) return;

    const prevControlsSnapshot = { ...controls };
    setMessages((prev) => [...prev, { role: 'user', text }]);
    setInputText('');
    setIsChatLoading(true);

    try {
      const { data } = await axios.post(`${API_BASE_URL}/api/ai`, {
        message: text,
        context: buildContext(heatmapData, counterfactualData, controls),
      });
      const mapChanged = !!(data.controls && Object.keys(data.controls).length > 0);
      setMessages((prev) => [...prev, {
        role: 'bot',
        text: data.reply || '...',
        mapChanged,
        prevControls: mapChanged ? prevControlsSnapshot : null,
      }]);
      if (mapChanged) onControlsUpdate(data.controls);
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'bot', text: 'Error contacting AI. Check backend.' }]);
    } finally {
      setIsChatLoading(false);
    }
  }, [inputText, isChatLoading, heatmapData, counterfactualData, controls, onControlsUpdate]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  }, [handleSend]);

  // ── Collapsed: pill button ────────────────────────────────────────────────
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        title="Open AI Dispatcher"
        style={{
          position: 'fixed',
          top: 60,
          right: 16,
          padding: '7px 14px',
          borderRadius: 20,
          background: '#0D47A1',
          border: '1px solid #42A5F5',
          color: '#E3F2FD',
          fontSize: 12,
          fontWeight: 700,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          zIndex: 1000,
          boxShadow: '0 2px 8px rgba(0,0,0,0.5)',
          letterSpacing: 0.3,
        }}
      >
        🤖 AI Dispatcher
        {isBriefingLoading && (
          <span style={{ color: '#FDD835', fontSize: 11 }}>↻</span>
        )}
      </button>
    );
  }

  // ── Expanded ──────────────────────────────────────────────────────────────
  return (
    <div style={{
      position: 'fixed',
      top: 60,
      right: 16,
      width: 340,
      height: 520,
      background: '#0f0f23',
      border: '1px solid #2a2a4a',
      borderRadius: 10,
      display: 'flex',
      flexDirection: 'column',
      boxShadow: '0 8px 32px rgba(0,0,0,0.7)',
      zIndex: 1000,
      overflow: 'hidden',
      fontSize: 12,
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '9px 12px',
        background: '#0D47A1',
        borderBottom: '1px solid #1565C0',
        flexShrink: 0,
      }}>
        <span style={{ fontWeight: 700, fontSize: 13, color: '#E3F2FD', letterSpacing: 0.3 }}>
          🤖 AI Dispatcher
          {isBriefingLoading && <span style={{ color: '#FDD835', fontSize: 10, marginLeft: 6, fontWeight: 400 }}>↻ updating…</span>}
        </span>
        <button
          onClick={() => setIsOpen(false)}
          title="Close"
          style={{
            background: 'rgba(255,255,255,0.15)',
            border: 'none',
            color: '#fff',
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 700,
            width: 22,
            height: 22,
            borderRadius: 4,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            lineHeight: 1,
          }}
        >
          ✕
        </button>
      </div>

      {/* Auto-briefing */}
      <div style={{ padding: '10px 12px', borderBottom: '1px solid #1a1a3a', flexShrink: 0 }}>
        <div style={{ fontSize: 10, color: '#42A5F5', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 5 }}>
          Live Briefing — updates when you change the time or day
        </div>
        <div style={{
          background: '#12122a',
          border: '1px solid #2a2a4a',
          borderRadius: 6,
          padding: '8px 10px',
          color: briefing ? '#E0E0E0' : '#555',
          lineHeight: 1.55,
          minHeight: 68,
          fontSize: 12,
        }}>
          {briefing || (isBriefingLoading ? 'Analyzing current demand pattern…' : 'Waiting for map data…')}
        </div>
      </div>

      {/* Chat */}
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
        <div style={{ padding: '7px 12px 2px', flexShrink: 0 }}>
          <div style={{ fontSize: 10, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1 }}>
            Ask a scenario
          </div>
          <div style={{ fontSize: 10, color: '#555', marginTop: 2 }}>
            Describe a time, event, or weather — AI will answer and update the map.
            If the map changes, you can undo it.
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 12px' }}>
          {/* Empty state: example chips */}
          {messages.length === 0 && (
            <div style={{ marginTop: 6 }}>
              <div style={{ color: '#444', fontSize: 11, marginBottom: 6 }}>Try asking:</div>
              {EXAMPLE_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => handleSend(p)}
                  style={{
                    display: 'block', width: '100%', textAlign: 'left',
                    background: '#12122a', border: '1px solid #2a2a4a',
                    borderRadius: 6, color: '#90CAF9', fontSize: 11,
                    padding: '5px 9px', marginBottom: 5, cursor: 'pointer',
                  }}
                >
                  {p}
                </button>
              ))}
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} style={{
              marginBottom: 8,
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}>
              <div style={{
                background: msg.role === 'user' ? '#1565C0' : '#1a1a3a',
                color: msg.role === 'user' ? '#E3F2FD' : '#CCC',
                padding: '6px 10px',
                borderRadius: msg.role === 'user' ? '10px 10px 2px 10px' : '10px 10px 10px 2px',
                maxWidth: '88%',
                lineHeight: 1.5,
              }}>
                {msg.text}
              </div>
              {/* Undo chip — only shown on messages that updated the map */}
              {msg.mapChanged && (
                <button
                  onClick={() => onControlsUpdate(msg.prevControls)}
                  title="Revert the map to before this response"
                  style={{
                    marginTop: 4,
                    background: 'none',
                    border: '1px solid #333',
                    borderRadius: 12,
                    color: '#888',
                    fontSize: 10,
                    padding: '2px 8px',
                    cursor: 'pointer',
                    alignSelf: 'flex-start',
                  }}
                >
                  ↩ Undo map change
                </button>
              )}
            </div>
          ))}

          {isChatLoading && (
            <div style={{ color: '#42A5F5', fontStyle: 'italic', fontSize: 11 }}>Thinking…</div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input row */}
        <div style={{
          display: 'flex', gap: 6, padding: '8px 12px',
          borderTop: '1px solid #1a1a3a', flexShrink: 0,
        }}>
          <input
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g. 'Yankees game Friday night?'"
            style={{
              flex: 1, background: '#12122a', border: '1px solid #2a2a4a',
              borderRadius: 6, color: '#e0e0e0', fontSize: 12, padding: '6px 8px',
              outline: 'none',
            }}
          />
          <button
            onClick={() => handleSend()}
            disabled={!inputText.trim() || isChatLoading}
            style={{
              background: inputText.trim() ? '#1565C0' : '#1a1a2e',
              color: inputText.trim() ? '#E3F2FD' : '#444',
              border: '1px solid ' + (inputText.trim() ? '#42A5F5' : '#2a2a4a'),
              borderRadius: 6, padding: '6px 10px',
              cursor: inputText.trim() ? 'pointer' : 'default',
              fontSize: 14, fontWeight: 700,
            }}
          >
            →
          </button>
        </div>
      </div>
    </div>
  );
}
