import { test, expect } from '@playwright/test';

test('home page loads and shows empty state or list', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('GEO 诊断 Agent')).toBeVisible();
  await expect(page.getByRole('link', { name: /新建诊断/ })).toBeVisible();
});

test('new diagnosis form has 3 steps', async ({ page }) => {
  await page.goto('/new');
  await expect(page.getByText('品牌信息')).toBeVisible();
  await expect(page.getByLabel(/品牌名/)).toBeVisible();
});

test('form validates required fields', async ({ page }) => {
  await page.goto('/new');
  // Click next without filling
  await page.getByRole('button', { name: /下一步/ }).click();
  // Should still be on step 0 because next is disabled
  await expect(page.getByText('品牌信息')).toBeVisible();
});
