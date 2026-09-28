import { DOW_LABELS, REPLAY_MIN_DATE, REPLAY_MAX_DATE } from '../../constants';
import { dowFromDate, isReplayDate } from '../../utils/replayDate';

export default function DatePicker({ value, onChange }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label
        htmlFor="replay-date"
        style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1, display: 'block', marginBottom: 6 }}
      >Replay Date</label>
      <input
        id="replay-date"
        type="date"
        min={REPLAY_MIN_DATE}
        max={REPLAY_MAX_DATE}
        value={value}
        onChange={(e) => { if (isReplayDate(e.target.value)) onChange(e.target.value); }}
        style={{
          width: '100%', padding: '8px', fontSize: 12, color: '#fff',
          background: '#1a1a2e', border: '1px solid #333', borderRadius: 4,
          colorScheme: 'dark', boxSizing: 'border-box',
        }}
      />
      <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>{DOW_LABELS[dowFromDate(value)]}</div>
    </div>
  );
}
