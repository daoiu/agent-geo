import { test, expect } from '@playwright/test';

/**
 * v0.7 e2e — verifies the Multi-Agent handoff TimelineRail (Top 3 +
 * spec §6.1).
 *
 * NOTE: this spec is intentionally `test.skip`-ed for v0.7 first cut.
 * TimelineRail ships as a standalone component in v0.7 but is not yet
 * mounted inside AgentWorkspace (deliberate to keep the red-line 5
 * components untouched).  Unskip after v0.7.1 integrates the rail
 * into AgentWorkspace's right pane.
 */

test.describe.skip('Multi-Agent TimelineRail (v0.7)', () => {
  test('specialist nodes render and the current agent is highlighted', async ({ page }) => {
    await page.goto('/agent/timeline-preview');
    await expect(page.getByTestId('timeline-rail')).toBeVisible();
    await expect(page.getByRole('button', { name: /monitor_specialist/ })).toHaveAttribute(
      'aria-current',
      'true',
    );
  });
});
