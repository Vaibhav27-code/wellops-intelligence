import { EXAMPLE_QUESTIONS } from '../store';

interface ExampleChipsProps {
  onSelect: (q: string) => void;
}

export function ExampleChips({ onSelect }: ExampleChipsProps) {
  return (
    <div className="example-chips">
      <p className="example-chips__label">Try asking:</p>
      <div className="example-chips__list">
        {EXAMPLE_QUESTIONS.map((q) => (
          <button
            key={q}
            className="example-chips__chip"
            onClick={() => onSelect(q)}
            title={q}
          >
            {q.length > 60 ? q.slice(0, 57) + '…' : q}
          </button>
        ))}
      </div>
    </div>
  );
}
