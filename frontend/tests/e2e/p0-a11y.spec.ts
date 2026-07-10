import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

/**
 * a11y checks for the new v0.6 layout shell — header / sidebar / rail only.
 * Per-page a11y coverage happens in P1+ as pages get rewritten.
 */
test('P0 a11y: LayoutShell elements pass axe checks', async ({ page }) => {
  await page.goto('/');
  const results = await new AxeBuilder({ page })
    .include('header')
    .include('nav[aria-label]')
    .include('footer[aria-label]')
    .include('main')
    .analyze();
  // axe types expect particular shape; cast for tolerance
  expect((results as unknown as { violations: unknown[] }).violations).toEqual([]);
});
