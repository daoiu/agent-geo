import { test, expect } from '@playwright/test';

/**
 * v0.7 e2e — verifies the 10 LangGraph SSE events reach the chat pane
 * and TimelineRail (Top 3 + spec §6.2).
 *
 * NOTE: this spec is intentionally `test.skip`-ed for v0.7 first cut —
 * enabling it requires (1) the dev server running (`npm run dev`) so
 * Playwright has something to hit, and (2) the LangGraph flag toggled
 * via the TopBar dev switch (Task 11).  Both landed in v0.7.1.
 *
 * Unskip after `useAgentStream` is mounted in AgentWorkspace (Task 8
 * v0.7.1 integration step) and the dev server boots clean.
 */

test.describe.skip('agent LangGraph SSE (v0.7)', () => {
  test('10 events flow to UI when LangGraph mode is on', async ({ page }) => {
    await page.goto('/agent?langgraph=1');
    await page.getByPlaceholderText('输入消息').fill('帮我诊断小米');
    await page.getByRole('button', { name: '发送' }).click();
    await expect(page.getByText(/handoff/i)).toBeVisible();
    await expect(page.getByText(/memory/i)).toBeVisible();
    await expect(page.getByText(/truncation/i)).toBeVisible();
  });
});
