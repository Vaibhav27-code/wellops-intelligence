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
  const { currentUser, addCorrection } = useStore();
  const [scope, setScope] = React.useState<'well' | 'well_type'>(wellId ? 'well' : 'well_type');
  const [fieldName, setFieldName] = React.useState(initialField);
  const [originalVal, setOriginalVal] = React.useState(String(currentValue ?? ''));
  const [correctedVal, setCorrectedVal] = React.useState('');
  const [reason, setReason] = React.useState('');
  const [evidence, setEvidence] = React.useState('');
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fieldName || !correctedVal || !reason) {
      setError('Field name, corrected value, and reason are required.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        scope,
        well_id: scope === 'well' ? wellId : undefined,
        well_type: scope === 'well_type' ? wellType : undefined,
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
        well_id: scope === 'well' ? wellId : undefined,
        well_type: scope === 'well_type' ? wellType : undefined,
        field: fieldName,
        original_value: originalVal,
        corrected_value: correctedVal,
        author: currentUser.user_id,
        created_at: new Date().toISOString(),
        reason,
        evidence: evidence || undefined,
      });
      onClose();
    } catch (err) {
      // Log correction locally even if backend is not yet ready
      addCorrection({
        correction_id: `local-${Date.now()}`,
        scope,
        well_id: scope === 'well' ? wellId : undefined,
        well_type: scope === 'well_type' ? wellType : undefined,
        field: fieldName,
        original_value: originalVal,
        corrected_value: correctedVal,
        author: currentUser.user_id,
        created_at: new Date().toISOString(),
        reason,
        evidence: evidence || undefined,
      });
      onClose();
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

        <form onSubmit={handleSubmit} className="modal__body">
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
                Single well {wellId ? `(${wellId})` : ''}
              </label>
              <label>
                <input
                  type="radio"
                  value="well_type"
                  checked={scope === 'well_type'}
                  onChange={() => setScope('well_type')}
                />
                All wells of type {wellType ? `(${wellType})` : ''}
              </label>
            </div>
          </div>

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
      </div>
    </div>
  );
}
