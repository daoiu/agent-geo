/**
 * Markdown → plain text utility (no third-party deps).
 *
 * 用于"复制纯文本"按钮：把 Markdown 语法剥掉，留下可读的文字。
 * 不做完美转换（HTML 等复杂语法不处理），只覆盖最常见的
 * H1-H3 / 列表 / 引用 / 代码块 / 强调 / 链接。
 */

const H1_RE = /^#\s+(.+)$/gm;
const H2_RE = /^##\s+(.+)$/gm;
const H3_RE = /^###\s+(.+)$/gm;
const LINK_RE = /\[([^\]]+)\]\([^)]+\)/g;
const IMG_RE = /!\[([^\]]*)\]\([^)]+\)/g;
const BOLD_RE = /\*\*(.+?)\*\*|__(.+?)__/g;
const ITALIC_RE = /(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|(?<!_)_(?!_)(.+?)(?<!_)_(?!_)/g;
const INLINE_CODE_RE = /`([^`]+)`/g;
const BLOCKQUOTE_RE = /^>\s*/gm;
const HR_RE = /^---+$/gm;
const FENCE_RE = /```[\s\S]*?```/g;
const LIST_RE = /^[\s]*[-*+]\s+/gm;
const NUM_LIST_RE = /^[\s]*\d+\.\s+/gm;

export function stripMarkdown(md: string | null | undefined): string {
  if (!md) return '';

  let text = md;

  // 1. Code blocks: keep inner content, drop the fences
  text = text.replace(FENCE_RE, (m) => m.replace(/```/g, ''));

  // 2. Headings: H1 → UPPERCASE, H2/H3 → keep case (already implicit)
  text = text.replace(H1_RE, (_m, g1: string) => g1.toUpperCase());
  text = text.replace(H2_RE, (_m, g1: string) => g1);
  text = text.replace(H3_RE, (_m, g1: string) => g1);

  // 3. Images → alt text
  text = text.replace(IMG_RE, (_m, g1: string) => g1);

  // 4. Links [text](url) → text
  text = text.replace(LINK_RE, (_m, g1: string) => g1);

  // 5. Bold / italic / inline code → strip markers
  text = text.replace(BOLD_RE, (_m, a?: string, b?: string) => a ?? b ?? '');
  text = text.replace(ITALIC_RE, (_m, a?: string, b?: string) => a ?? b ?? '');
  text = text.replace(INLINE_CODE_RE, (_m, g1: string) => g1);

  // 6. Blockquote / list markers → drop
  text = text.replace(BLOCKQUOTE_RE, '');
  text = text.replace(LIST_RE, '');
  text = text.replace(NUM_LIST_RE, '');

  // 7. Horizontal rules → blank
  text = text.replace(HR_RE, '');

  // 8. Normalize whitespace
  text = text.replace(/\r\n/g, '\n');
  text = text.replace(/\n{3,}/g, '\n\n');

  return text.trim();
}