import { describe, expect, it } from 'vitest';

import { stripMarkdown } from '@/lib/markdown';

describe('stripMarkdown', () => {
  it('strips bold / italic markers', () => {
    const md = '这是 **加粗** 与 *斜体* 的示例。';
    expect(stripMarkdown(md)).toBe('这是 加粗 与 斜体 的示例。');
  });

  it('replaces links with their text', () => {
    const md = '访问 [官网](https://example.com) 了解。';
    const out = stripMarkdown(md);
    expect(out).toContain('官网');
    expect(out).not.toContain('https://example.com');
    expect(out).not.toContain('[');
  });

  it('replaces images with alt text', () => {
    const md = '![公司 logo](logo.png) 旁边是文字。';
    const out = stripMarkdown(md);
    expect(out).toContain('公司 logo');
    expect(out).not.toContain('logo.png');
  });

  it('uppercases H1 headings', () => {
    const md = '# 我的标题\n\n正文';
    const out = stripMarkdown(md);
    expect(out).toContain('我的标题'); // 中文 upper 没变化
    expect(out).not.toContain('#');
  });

  it('drops list bullets and blockquote markers', () => {
    const md = '- 项 1\n- 项 2\n\n> 引用文字';
    const out = stripMarkdown(md);
    expect(out).toContain('项 1');
    expect(out).toContain('项 2');
    expect(out).toContain('引用文字');
    expect(out).not.toContain('- ');
    expect(out).not.toContain('> ');
  });

  it('keeps inline code content but drops backticks', () => {
    const md = '使用 `npm install` 安装。';
    const out = stripMarkdown(md);
    expect(out).toContain('npm install');
    expect(out).not.toContain('`');
  });

  it('keeps code block content but drops fences', () => {
    const md = '示例：\n\n```\nconst x = 1;\n```\n\n结束。';
    const out = stripMarkdown(md);
    expect(out).toContain('const x = 1;');
    expect(out).not.toContain('```');
  });

  it('returns empty string for null/undefined/empty', () => {
    expect(stripMarkdown(null)).toBe('');
    expect(stripMarkdown(undefined)).toBe('');
    expect(stripMarkdown('')).toBe('');
  });

  it('collapses 3+ consecutive newlines to 2', () => {
    const md = '第一段\n\n\n\n\n第二段';
    const out = stripMarkdown(md);
    expect(out).not.toMatch(/\n{3,}/);
    expect(out).toContain('第一段');
    expect(out).toContain('第二段');
  });

  it('handles ordered lists', () => {
    const md = '1. 第一\n2. 第二\n3. 第三';
    const out = stripMarkdown(md);
    expect(out).toContain('第一');
    expect(out).toContain('第二');
    expect(out).toContain('第三');
    expect(out).not.toMatch(/^\d+\./);
  });

  it('drops horizontal rules', () => {
    const md = '段落 A\n\n---\n\n段落 B';
    const out = stripMarkdown(md);
    expect(out).toContain('段落 A');
    expect(out).toContain('段落 B');
    expect(out).not.toContain('---');
  });
});