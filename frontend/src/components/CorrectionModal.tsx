import React from 'react';
import { useStore } from '../store';
import { api } from '../api/client';
import { X, Save } from 'lucide-react';

interface CorrectionModalProps {
  wellId?: string;
  wellType?: string;
  field?: string;
  currentValue?: unknown;
  onClose: () => void;
}

export function CorrectionModal({
  wellId,
  wellType,
  field: initialField = '',
  currentValue,
  onClose,
}: CorrectionModalProps) {
  const { currentUser, addCorrection, isSidebarOpen, toggleSidebar } = useStore();
  const [scope, setScope] = React.useState<'well' | 'well_type'>(wellId ? 'well' : 'well_type');
  const [targetWellId, setTargetWellId] = React.useState(wellId ?? '');
  const [targetWellType, setTargetWellType] = React.useState(wellType ?? '');
  const [fieldName, setFieldName] = React.useState(initialField);
  const [originalVal, setOriginalVal] = React.useState(String(currentValue ?? ''));
  const [correctedVal, setCorrectedVal] = React.useState('');
  const [reason, setReason] = React.useState('');
  const [evidence, setEvidence] = React.useState('');
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [successInfo, setSuccessInfo] = React.useState<{
    scope: string;
    field: string;
    original: string;
    corrected: string;
    author: string;
    time: string;
  } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fieldName || !correctedVal || !reason || (scope === 'well' && !targetWellId.trim()) || (scope === 'well_type' && !targetWellType.trim())) {
      setError('Choose a correction scope and target, then provide the field, corrected value, and reason.');
      return;
    }
    setSaving(true);
    setError(null);
    const recordedTime = new Date().toISOString();
    try {
      const payload = {
        scope,
        well_id: scope === 'well' ? targetWellId.trim() : undefined,
        well_type: scope === 'well_type' ? targetWellType.trim() : undefined,
        field: fieldName,
        original_value: originalVal,
        corrected_value: correctedVal,
        reason,
        evidence: evidence || undefined,
        author: currentUser.user_id,
      };
      const res = await api.postCorrection(payload);
      addCorrection({
        correction_id: res.correction_id,
        scope,
        well_id: scope === 'well' ? targetWellId.trim() : undefined,
        well_type: scope === 'well_type' ? targetWellType.trim() : undefined,
        field: fieldName,
        original_value: originalVal,
        corrected_value: correctedVal,
        author: currentUser.name ? `${currentUser.name} (${currentUser.user_id})` : currentUser.user_id,
        created_at: recordedTime,
        reason,
        evidence: evidence || undefined,
      });

      // Open sidebar if not already open
      if (!isSidebarOpen) {
        toggleSidebar();
      }

      setSuccessInfo({
        scope: scope === 'well' ? `Well ${targetWellId.trim()}` : `All wells of type ${targetWellType.trim()}`,
        field: fieldName,
        original: originalVal,
        corrected: correctedVal,
        author: currentUser.name ? `${currentUser.name} (${currentUser.user_id})` : currentUser.user_id,
        time: new Date(recordedTime).toLocaleTimeString(),
      });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Correction recording failed';
      setError(`Failed to save correction to backend: ${errMsg}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal__header">
          <h2 className="modal__title">Record a Correction</h2>
          <button className="modal__close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal__body">
          {successInfo ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                padding: '12px',
                background: 'rgba(34, 197, 94, 0.12)',
                border: '1px solid var(--c-ok)',
                borderRadius: '8px',
              }}
            >
              <div style={{ fontWeight: 700, color: 'var(--c-ok)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>✓ Correction Audited & Recorded to Shared Memory</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '6px', fontSize: '12px' }}>
                <span style={{ color: 'var(--c-text-muted)' }}>Scope:</span>
                <strong>{successInfo.scope}</strong>

                <span style={{ color: 'var(--c-text-muted)' }}>Field:</span>
                <code>{successInfo.field}</code>

                <span style={{ color: 'var(--c-text-muted)' }}>Value Change:</span>
                <span>
                  <span style={{ textDecoration: 'line-through', color: 'var(--c-err)', marginRight: '6px' }}>
                    {successInfo.original || '(empty)'}
                  </span>
                  {' → '}
                  <strong style={{ color: 'var(--c-ok)', marginLeft: '6px' }}>
                    {successInfo.corrected}
                  </strong>
                </span>

                <span style={{ color: 'var(--c-text-muted)' }}>Author:</span>
                <span>{successInfo.author}</span>

                <span style={{ color: 'var(--c-text-muted)' }}>Timestamp:</span>
                <span>{successInfo.time}</span>
              </div>
              <p style={{ fontSize: '11px', color: 'var(--c-text-muted)', margin: '4px 0 0 0' }}>
                The audited log is now active in the shared memory database and visible in the right-hand audit sidebar.
              </p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }}>
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={onClose}
                  style={{ padding: '6px 16px' }}
                >
                  Done
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {error && <p className="modal__error">{error}</p>}

              <div className="form-group">
                <label>Scope</label>
            <div className="form-radio-group">
              <label>
                <input
                  type="radio"
                  value="well"
                  checked={scope === 'well'}
                  onChange={() => setScope('well')}
                />
                Single well
              </label>
              <label>
                <input
                  type="radio"
                  value="well_type"
                  checked={scope === 'well_type'}
                  onChange={() => setScope('well_type')}
                />
                All wells of a type
              </label>
            </div>
          </div>

          {scope === 'well' ? (
            <div className="form-group">
              <label htmlFor="corr-well-id">Well ID *</label>
              <input
                id="corr-well-id"
                className="form-input"
                value={targetWellId}
                onChange={(e) => setTargetWellId(e.target.value)}
                placeholder="e.g. WELL-0164"
                required
              />
            </div>
          ) : (
            <div className="form-group">
              <label htmlFor="corr-well-type">Well type *</label>
              <input
                id="corr-well-type"
                className="form-input"
                value={targetWellType}
                onChange={(e) => setTargetWellType(e.target.value)}
                placeholder="e.g. T350"
                required
              />
            </div>
          )}

          <div className="form-group">
            <label htmlFor="corr-field">Field name *</label>
            <input
              id="corr-field"
              className="form-input"
              value={fieldName}
              onChange={(e) => setFieldName(e.target.value)}
              placeholder="e.g. volume_bbl, status"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="corr-original">Original value</label>
            <input
              id="corr-original"
              className="form-input"
              value={originalVal}
              onChange={(e) => setOriginalVal(e.target.value)}
              placeholder="What the data says now"
            />
          </div>

          <div className="form-group">
            <label htmlFor="corr-corrected">Corrected value *</label>
            <input
              id="corr-corrected"
              className="form-input"
              value={correctedVal}
              onChange={(e) => setCorrectedVal(e.target.value)}
              placeholder="What it should be"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="corr-reason">Reason *</label>
            <textarea
              id="corr-reason"
              className="form-input form-textarea"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Why is this correction valid?"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="corr-evidence">Evidence (optional)</label>
            <input
              id="corr-evidence"
              className="form-input"
              value={evidence}
              onChange={(e) => setEvidence(e.target.value)}
              placeholder="Document reference, page, field note…"
            />
          </div>

          <div className="modal__footer">
            <button type="button" className="btn btn--ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn--primary" disabled={saving}>
              <Save size={14} />
              {saving ? 'Saving…' : 'Save Correction'}
            </button>
          </div>
        </form>
      )}
    </div>
  </div>
</div>
  );
}
