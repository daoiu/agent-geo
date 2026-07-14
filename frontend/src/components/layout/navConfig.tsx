/**
 * navSections — v0.7 HarmonyOS IA: 6 抽屉类目 + 智能助手独立入口
 * (spec §5.1). Each section maps to a primary URL and may expose a
 * flat list of sub-items shown beneath the active section.
 *
 * Single source of truth — both NavDrawer (drawer nav) and the legacy
 * SideNav (kept in parallel for the v0.6→v0.7 transition window) consume
 * this file. After v0.7 fully ships, SideNav can be deleted.
 */
import {
  Activity,
  BookOpen,
  Compass,
  Pencil,
  Share2,
  Settings as SettingsIcon,
  Bot,
} from 'lucide-react';

import type { NavSection } from './NavDrawer';

/**
 * 6 categories + 智能助手独立入口.
 * Label / to / items are stable — see spec §5.3 for the redirect map
 * the router applies to legacy URLs.
 */
export const navSections: NavSection[] = [
  {
    id: 'diagnose',
    label: '诊断',
    icon: <Compass className="h-5 w-5" aria-hidden="true" />,
    to: '/diagnose',
    items: [
      { to: '/diagnose/new', label: '新建诊断' },
      { to: '/diagnose/reports', label: '历史报告' },
    ],
  },
  {
    id: 'knowledge',
    label: '知识',
    icon: <BookOpen className="h-5 w-5" aria-hidden="true" />,
    to: '/knowledge/bases',
    items: [
      { to: '/knowledge/search', label: '跨库检索' },
      { to: '/knowledge/bases', label: '全部 KB' },
    ],
  },
  {
    id: 'generate',
    label: '生成',
    icon: <Pencil className="h-5 w-5" aria-hidden="true" />,
    to: '/generate/tasks',
    items: [
      { to: '/generate/tasks', label: '生成任务' },
      { to: '/generate/tasks/new', label: '新建任务' },
      { to: '/generate/reviews', label: '审核队列' },
    ],
  },
  {
    id: 'publish',
    label: '发布',
    icon: <Share2 className="h-5 w-5" aria-hidden="true" />,
    to: '/publish/jobs',
    items: [
      { to: '/publish/configs', label: '平台配置' },
      { to: '/publish/jobs', label: '发布历史' },
    ],
  },
  {
    id: 'monitor',
    label: '监测',
    icon: <Activity className="h-5 w-5" aria-hidden="true" />,
    to: '/monitor/tasks',
    items: [
      { to: '/monitor/tasks', label: '品牌监测' },
      { to: '/monitor/tasks/new', label: '新建监测' },
      { to: '/cost', label: '月度成本' },
    ],
  },
  {
    id: 'settings',
    label: '设置',
    icon: <SettingsIcon className="h-5 w-5" aria-hidden="true" />,
    to: '/settings/general',
    items: [
      { to: '/settings/general', label: '通用设置' },
      { to: '/settings/notifications', label: '通知设置' },
    ],
  },
  // 智能助手 is mounted as a 7th entry so the TopBar launch button
  // and the drawer both surface it without burying it inside another tab.
  {
    id: 'agent',
    label: '智能助手',
    icon: <Bot className="h-5 w-5" aria-hidden="true" />,
    to: '/agent',
    items: [],
  },
];

/**
 * Convert sections → the legacy SideNav NavItem[] shape so the older
 * SideNav component keeps working. Used by App.tsx routing layer until
 * SideNav is removed in v0.7.1+.
 */
export function sectionsToNavItems(
  sections: NavSection[],
  parentLabel?: string,
): { key: string; label: string; to: string }[] {
  return sections.flatMap((s) => [
    { key: s.id, label: `${parentLabel ?? ''}${s.label}`, to: s.to },
    ...s.items.map((it, i) => ({
      key: `${s.id}-${i}`,
      label: it.label,
      to: it.to,
    })),
  ]);
}

/**
 * Legacy v0.6 navItems — flat SideNav-compatible shape with emoji labels.
 * Kept exported for App.tsx (which still mounts SideNav for legacy pages)
 * and CommandPalette (which flattens and indexes by label / to) until the
 * full IA migration in Task 5 finishes. Once all pages route through
 * LayoutShell with `sections`, this export can be deleted.
 */
export const navItems: { key: string; label: string; to: string; children?: { key: string; label: string; to: string }[] }[] = [
  { key: 'home', label: '🏠 仪表盘', to: '/' },
  { key: 'agent', label: '🤖 智能助手', to: '/agent' },
  {
    key: 'diag',
    label: '🔍 诊断',
    to: '/new',
    children: [
      { key: 'diag-new', label: '新建诊断', to: '/new' },
      { key: 'diag-history', label: '历史报告', to: '/reports' },
    ],
  },
  {
    key: 'kb',
    label: '📚 知识库',
    to: '/knowledge',
    children: [{ key: 'kb-list', label: '全部 KB', to: '/knowledge' }],
  },
  {
    key: 'gen',
    label: '✍️ 生成',
    to: '/tasks',
    children: [
      { key: 'gen-tasks', label: '生成任务', to: '/tasks' },
      { key: 'gen-new', label: '创建任务', to: '/tasks/new' },
      { key: 'gen-reviews', label: '审核队列', to: '/reviews' },
    ],
  },
  {
    key: 'pub',
    label: '📤 发布',
    to: '/publishes',
    children: [
      { key: 'pub-configs', label: '平台配置', to: '/publishers' },
      { key: 'pub-list', label: '发布历史', to: '/publishes' },
    ],
  },
  {
    key: 'mon',
    label: '📈 监测',
    to: '/monitors',
    children: [
      { key: 'mon-list', label: '品牌监测', to: '/monitors' },
      { key: 'mon-new', label: '新建监测', to: '/monitors/new' },
      { key: 'mon-notif', label: '阈值通知', to: '/notifications' },
    ],
  },
  { key: 'settings', label: '⚙️ 设置', to: '/settings' },
];
