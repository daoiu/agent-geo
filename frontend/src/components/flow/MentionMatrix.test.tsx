import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { MentionMatrix, type MentionCell } from './MentionMatrix';

const CELLS: MentionCell[] = [
  { brand: '小米', question: 'Q1', provider: 'DeepSeek', mentioned: true, position: 1, sentiment: 'positive' },
  { brand: '小米', question: 'Q1', provider: 'Kimi', mentioned: false },
  { brand: '竞品A', question: 'Q1', provider: 'DeepSeek', mentioned: true, position: 3 },
];

describe('MentionMatrix', () => {
  it('a11y: each cell has aria-label with mention status', () => {
    renderWithRouter(
      <MentionMatrix
        cells={CELLS}
        brands={['小米', '竞品A']}
        questions={['Q1']}
        providers={['DeepSeek', 'Kimi']}
      />
    );
    expect(screen.getByLabelText('小米·Q1·DeepSeek 提及且位置第 1 情感 positive')).toBeInTheDocument();
    expect(screen.getByLabelText('小米·Q1·Kimi 未提及')).toBeInTheDocument();
    expect(screen.getByLabelText('竞品A·Q1·DeepSeek 提及且位置第 3')).toBeInTheDocument();
  });

  it('renders brands × providers × questions in a table', () => {
    renderWithRouter(
      <MentionMatrix cells={CELLS} brands={['小米']} questions={['Q1']} providers={['DeepSeek']} />
    );
    expect(screen.getByRole('table', { name: '品牌提及矩阵（按 provider 分列）' })).toBeInTheDocument();
  });
});
