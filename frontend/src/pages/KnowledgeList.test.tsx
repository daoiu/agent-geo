import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('@/api/client', () => ({
  api: {
    listKnowledgeBases: vi.fn(),
    createKnowledgeBase: vi.fn(),
    deleteKnowledgeBase: vi.fn(),
    searchKnowledgeGlobal: vi.fn(),
  },
}));

import { api } from '@/api/client';
import KnowledgeList from './KnowledgeList';

const mockedApi = vi.mocked(api);

const fakeKBs = [
  {
    id: 'kb-1',
    name: '北北云吞',
    description: null,
    created_at: '2026-07-10T10:00:00Z',
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.listKnowledgeBases.mockResolvedValue(fakeKBs);
  mockedApi.searchKnowledgeGlobal.mockResolvedValue({
    query: '陈皮马蹄',
    hits: [
      {
        kb_id: 'kb-1',
        kb_name: '北北云吞',
        doc_id: 'doc-1',
        doc_filename: '北北云吞.md',
        chunk_id: 'chunk-1',
        chunk_index: 0,
        content: '脆马蹄陈皮捶打大肉云吞',
        score: 0.054,
        sources: ['keyword'],
      },
    ],
  });
});

describe('KnowledgeList — global cross-KB search (v0.6 P1.3)', () => {
  it('renders the existing KB list', async () => {
    renderWithRouter(<KnowledgeList />, { initialEntries: ['/knowledge'] });
    expect(await screen.findByText('北北云吞')).toBeInTheDocument();
  });

  it('does NOT render any hits before the user searches', () => {
    renderWithRouter(<KnowledgeList />, { initialEntries: ['/knowledge'] });
    expect(screen.queryAllByTestId('global-search-hit')).toHaveLength(0);
  });

  it('Enter in the search input triggers searchKnowledgeGlobal with the typed q (no kb_id)', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeList />, { initialEntries: ['/knowledge'] });

    const input = screen.getByPlaceholderText(/跨知识库/);
    await user.type(input, '陈皮马蹄');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(mockedApi.searchKnowledgeGlobal).toHaveBeenCalledTimes(1);
    });
    expect(mockedApi.searchKnowledgeGlobal).toHaveBeenCalledWith('陈皮马蹄', 10);
    expect(mockedApi.searchKnowledgeGlobal.mock.calls[0]).toHaveLength(2); // no kb_id!
  });

  it('renders hits with KB name badge + source document filename', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeList />, { initialEntries: ['/knowledge'] });

    await user.type(screen.getByPlaceholderText(/跨知识库/), '陈皮马蹄');
    await user.keyboard('{Enter}');

    const hits = await screen.findAllByTestId('global-search-hit');
    expect(hits).toHaveLength(1);
    // Both the original KB list and the search hit badge render the KB name.
    // Scope the assertions to the search hit row to avoid duplicate-match errors.
    expect(within(hits[0]).getByText('北北云吞')).toBeInTheDocument();
    expect(within(hits[0]).getByText(/北北云吞\.md/)).toBeInTheDocument();
    expect(within(hits[0]).getByText('keyword')).toBeInTheDocument();
    expect(within(hits[0]).getByText(/0\.054/)).toBeInTheDocument();
  });

  it('shows an empty hint when the API returns zero hits', async () => {
    mockedApi.searchKnowledgeGlobal.mockResolvedValueOnce({
      query: 'no-match',
      hits: [],
    });
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeList />, { initialEntries: ['/knowledge'] });

    await user.type(screen.getByPlaceholderText(/跨知识库/), 'no-match');
    await user.keyboard('{Enter}');

    expect(await screen.findByText(/没有命中任何知识库片段/)).toBeInTheDocument();
  });

  it('does NOT call the API for an empty query', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeList />, { initialEntries: ['/knowledge'] });

    await user.click(screen.getByRole('button', { name: '搜索' }));

    // No refetch fired (enabled: false) → mock never called
    expect(mockedApi.searchKnowledgeGlobal).not.toHaveBeenCalled();
  });
});
