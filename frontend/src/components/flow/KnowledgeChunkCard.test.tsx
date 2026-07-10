import { describe, it, expect, vi } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { KnowledgeChunkCard } from './KnowledgeChunkCard';

describe('KnowledgeChunkCard', () => {
  it('renders title / source / preview', () => {
    renderWithRouter(
      <KnowledgeChunkCard title="GEO 指南" preview="这是摘要..." source="白皮书" />
    );
    expect(screen.getByText('GEO 指南')).toBeInTheDocument();
    expect(screen.getByText('这是摘要...')).toBeInTheDocument();
    expect(screen.getByText('白皮书')).toBeInTheDocument();
  });

  it('renders hybrid score when provided', () => {
    renderWithRouter(
      <KnowledgeChunkCard title="x" preview="" source="y" hybridScore={0.83} />
    );
    expect(screen.getByLabelText('检索分 0.83')).toBeInTheDocument();
  });

  it('fires onClick when interactive', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    renderWithRouter(
      <KnowledgeChunkCard title="x" preview="" source="y" onClick={onClick} />
    );
    await user.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
