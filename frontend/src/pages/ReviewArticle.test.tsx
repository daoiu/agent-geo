import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

vi.mock('@/api/client', () => ({
  api: {
    getArticle: vi.fn(),
    approveArticle: vi.fn(),
    rejectArticle: vi.fn(),
  },
}));

import ReviewArticle from '@/pages/ReviewArticle';
import { api } from '@/api/client';

const mockedApi = vi.mocked(api);

// Stub sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Stub clipboard.writeText — spyOn 在第一次访问 navigator.clipboard 之后才能成功。
let writeTextMock = vi.fn().mockResolvedValue(undefined);
let writeTextSpy: ReturnType<typeof vi.spyOn> | null = null;

function stubClipboard() {
  // 触发 navigator.clipboard getter 实例化（jsdom 28+）
  void navigator.clipboard;
  try {
    writeTextSpy = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockImplementation(writeTextMock);
  } catch {
    // jsdom 不可配置——退回到原型 spy
    writeTextSpy = vi
      .spyOn(Clipboard.prototype, 'writeText')
      .mockImplementation(writeTextMock);
  }
}

function renderAt(articleId: string) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/reviews/${articleId}`]}>
        <Routes>
          <Route path="/reviews/:articleId" element={<ReviewArticle />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const FULL_ARTICLE = {
  id: 'a1',
  task_id: 't1',
  title: '我的真实标题',
  content:
    '# 我的真实标题\n\n这是引言。\n\n## 章节一\n正文 **加粗** 与 *斜体*。\n\n- 列表项 1\n- 列表项 2\n\n[链接](https://example.com) 与 `inline code`。',
  content_length: 80,
  review_status: 'pending' as const,
  review_note: null,
  reviewed_at: null,
  cited_chunks: [],
  llm_provider: 'deepseek',
  error_message: null,
  created_at: '2026-07-11T00:00:00Z',
  updated_at: '2026-07-11T00:00:00Z',
};

beforeEach(() => {
  if (writeTextSpy) {
    writeTextSpy.mockRestore();
    writeTextSpy = null;
  }
  writeTextMock.mockClear();
  mockedApi.getArticle.mockReset();
  mockedApi.approveArticle.mockReset();
  mockedApi.rejectArticle.mockReset();
});

describe('ReviewArticle — title / copy / download', () => {
  it('renders the title as a distinct H1 above the content', async () => {
    mockedApi.getArticle.mockResolvedValue(FULL_ARTICLE);
    renderAt('a1');

    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
        '我的真实标题',
      ),
    );

    // 第一行 H1 不应再出现在正文里（避免重复显示）
    expect(screen.queryByText(/^# 我的真实标题$/)).toBeNull();
    // 正文里包含剥掉标题后的引言
    expect(screen.getByText(/这是引言/)).toBeInTheDocument();
  });

  it('renders three action buttons: 复制全文 / 复制纯文本 / 下载 .md', async () => {
    mockedApi.getArticle.mockResolvedValue(FULL_ARTICLE);
    renderAt('a1');

    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument(),
    );

    expect(screen.getByRole('button', { name: /复制全文/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /复制纯文本/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /下载/ })).toBeInTheDocument();
  });

  it('点击"复制全文"复制原始 Markdown（含 # 语法）', async () => {
    mockedApi.getArticle.mockResolvedValue(FULL_ARTICLE);
    const user = userEvent.setup();
    renderAt('a1');

    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument(),
    );

    stubClipboard();
    const btn = screen.getByRole('button', { name: /Markdown/ }) as HTMLButtonElement;
    await user.click(btn);

    expect(writeTextMock).toHaveBeenCalledTimes(1);
    const copied = writeTextMock.mock.calls[0][0] as string;
    expect(copied).toContain('# 我的真实标题');
  });

  it('点击"复制纯文本"剥掉 Markdown 标记', async () => {
    mockedApi.getArticle.mockResolvedValue(FULL_ARTICLE);
    const user = userEvent.setup();
    renderAt('a1');

    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument(),
    );

    stubClipboard();
    await user.click(screen.getByRole('button', { name: /纯文本/ }));

    expect(writeTextMock).toHaveBeenCalledTimes(1);
    const copied = writeTextMock.mock.calls[0][0] as string;
    // 不应包含 Markdown 标记
    expect(copied).not.toContain('**');
    expect(copied).not.toContain('[链接](https://example.com)');
    expect(copied).not.toContain('`inline code`');
    // 但应包含实际文字
    expect(copied).toContain('加粗');
    expect(copied).toContain('斜体');
    expect(copied).toContain('inline code');
  });

  it('点击"下载 .md" 触发文件下载（Blob + a.click）', async () => {
    mockedApi.getArticle.mockResolvedValue(FULL_ARTICLE);
    const user = userEvent.setup();

    // 拦截 createObjectURL / click
    const createObjectURL = vi.fn(() => 'blob:fake');
    const revokeObjectURL = vi.fn();
    URL.createObjectURL = createObjectURL;
    URL.revokeObjectURL = revokeObjectURL;

    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {});

    renderAt('a1');
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument(),
    );

    await user.click(screen.getByRole('button', { name: /下载/ }));

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    const blob = (createObjectURL.mock as unknown as {
      calls: Blob[][];
    }).calls[0]?.[0];
    expect(blob?.type).toContain('text/markdown');
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalled();

    clickSpy.mockRestore();
  });

  it('错误状态文章展示错误信息', async () => {
    mockedApi.getArticle.mockResolvedValue({
      ...FULL_ARTICLE,
      title: '生成失败 #1',
      content: null,
      error_message: 'LLM 调用失败',
    });
    renderAt('a2');

    await waitFor(() =>
      expect(screen.getByText(/LLM 调用失败/)).toBeInTheDocument(),
    );
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      '生成失败 #1',
    );
  });
});