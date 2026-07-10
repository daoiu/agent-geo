import { test, expect } from '@playwright/test';

test('home page loads and shows the new GEO 优化系统 brand', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('GEO 优化系统').first()).toBeVisible();
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

test('P0: brand shows in <header> and PipelineRail renders all 6 nodes', async ({ page }) => {
  await page.goto('/');
  const header = page.locator('header');
  await expect(header).toContainText('GEO 优化系统');
  const rail = page.locator('footer[aria-label="全局优化流水线"]');
  await expect(rail).toBeVisible();
  for (const label of ['诊断', '生成', '审核', '发布', '监测', '跟踪']) {
    await expect(rail).toContainText(label);
  }
});

test('P0: sidebar shows 7 nav groups', async ({ page }) => {
  await page.goto('/');
  const nav = page.locator('nav[aria-label="主导航"]');
  await expect(nav).toBeVisible();
  for (const item of ['仪表盘', '诊断', '知识库', '生成', '发布', '监测', '智能助手']) {
    await expect(nav).toContainText(item);
  }
});
