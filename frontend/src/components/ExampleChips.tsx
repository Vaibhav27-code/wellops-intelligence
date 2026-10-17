import React from 'react';
import { ALL_18_QUESTIONS } from '../store';
import type { GroupedQuestion } from '../store';

interface ExampleChipsProps {
  onSelect: (q: string) => void;
}

const GROUP_LABELS: Record<GroupedQuestion['group'], string> = {
  single_well: 'Single Well',
  area_analysis: 'Area Analysis',
  compliance: 'Compliance',
  memory_corrections: 'Memory / Audit',
};

export function ExampleChips({ onSelect }: ExampleChipsProps) {
  const [activeTab, setActiveTab] = React.useState<GroupedQuestion['group'] | 'all'>('all');

  const groups: Array<GroupedQuestion['group']> = [
    'single_well',
    'area_analysis',
    'compliance',
    'memory_corrections',
  ];

  const filtered = activeTab === 'all'
    ? ALL_18_QUESTIONS
    : ALL_18_QUESTIONS.filter((q) => q.group === activeTab);

  return (
    <div className="example-chips" style={{ width: '100%', maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <p className="example-chips__label" style={{ fontWeight: 600, color: 'var(--c-text)' }}>
          Sample Benchmark Questions (Q1 – Q18):
        </p>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            onClick={() => setActiveTab('all')}
            style={{
              fontSize: '11px',
              padding: '2px 8px',
              borderRadius: '4px',
              background: activeTab === 'all' ? 'var(--c-accent)' : 'var(--c-surface2)',
              color: '#fff',
            }}
          >
            All (18)
          </button>
          {groups.map((g) => (
            <button
              key={g}
              onClick={() => setActiveTab(g)}
              style={{
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: '4px',
                background: activeTab === g ? 'var(--c-accent)' : 'var(--c-surface2)',
                color: '#fff',
              }}
            >
              {GROUP_LABELS[g]}
            </button>
          ))}
        </div>
      </div>

      <div className="example-chips__list" style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        {filtered.map((item) => (
          <div key={item.id} style={{ display: 'inline-flex', flexDirection: 'column', gap: '2px' }}>
            <button
              className="example-chips__chip"
              onClick={() => onSelect(item.question)}
              title={item.question}
              style={{ textAlign: 'left', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <span style={{ fontWeight: 700, color: 'var(--c-accent-h)' }}>{item.id}:</span>
              <span>{item.label.replace(/^Q\d+:\s*/, '')}</span>
            </button>
            {item.suggestedUser && (
              <span style={{ fontSize: '10px', color: 'var(--c-text-muted)', paddingLeft: '6px' }}>
                💡 Suggested user: <strong style={{ color: 'var(--c-text)' }}>{item.suggestedUser}</strong>
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

