import { test, expect } from '@playwright/test';

/**
 * v0.7 e2e — verifies the Replay API menu (Top 3 + spec §6.3).
 *
 * NOTE: this spec is intentionally `test.skip`-ed for v0.7 first cut.
 * See `agent-langgraph.spec.ts` for the dev-server / flag rationale;
 * the additional blocker here is wiring `<MessageActions>` into
 * `ChatMessage`, which is a red-line change scheduled for v0.7.1.
 *
 * Unskip once MessageActions is mounted in ChatMessage and the agent
 * backend exposes the `/replay/{msg_id}` endpoint.
 */

test.describe.skip('agent Replay menu (v0.7)', () => {
  test('user can replay from the latest checkpoint message', async ({ page }) => {
    await page.goto('/agent');
    await page.getByLabel('消息操作').first().click();
    await page.getByRole('menuitem', { name: /重放消息/ }).click();
    await expect(page.getByText(/重放完成/)).toBeVisible();
  });
});
