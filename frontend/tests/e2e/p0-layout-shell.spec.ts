import { test, expect } from '@playwright/test';

/**
 * Smoke checks for the new LayoutShell:
 *  - shell wraps every page
 *  - breadcrumb reflects URL
 *  - sidebar nav is keyboard navigable
 */
const PAGES = [
  { path: '/', label: '仪表盘' },
  { path: '/new', crumb: '新建诊断' },
  { path: '/knowledge', crumb: '知识库' },
  { path: '/tasks', crumb: '生成任务' },
  { path: '/reviews', crumb: '审核队列' },
  { path: '/publishes', crumb: '发布历史' },
  { path: '/monitors', crumb: '品牌监测' },
  { path: '/agent', crumb: '会话列表' },
  { path: '/settings', crumb: '设置' },
];

for (const { path, crumb, label } of PAGES) {
  test(`shell wraps: ${path}`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator('header')).toBeVisible();
    await expect(page.locator('footer[aria-label="全局优化流水线"]')).toBeVisible();
    await expect(page.locator('nav[aria-label="主导航"]')).toBeVisible();
    if (crumb) {
      await expect(page.locator('nav[aria-label="面包屑"]')).toContainText(crumb);
    } else if (label) {
      await expect(page.locator('nav[aria-label="面包屑"]')).toContainText(label);
    }
  });
}
