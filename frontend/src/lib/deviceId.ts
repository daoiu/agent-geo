/**
 * deviceId — anonymous per-browser identity for cross-session memory (L2).
 *
 * 生成:首次访问 lazy 调用 `crypto.randomUUID()`(v4)。
 * 存储:localStorage key `geo.deviceId`。
 * 传输:作为 `X-Device-Id` header 由 client.ts 注入所有 fetch + SSE。
 *
 * 清浏览器数据 = 重置 device_id;对应 L2 `agent_memories` 表的 `scope`
 * 字段不再匹配,旧记忆自然失效(无需手动清理)。
 *
 * 模块级 `cached` 避免每次调用读 localStorage。
 */
const STORAGE_KEY = 'geo.deviceId';

let cached: string | null = null;

export function getDeviceId(): string {
  if (cached) return cached;
  if (typeof window === 'undefined') return '';
  let id = window.localStorage.getItem(STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(STORAGE_KEY, id);
  }
  cached = id;
  return id;
}

/** 仅测试用 — 清掉模块缓存与 storage,允许下一个测试重新生成。 */
export function _resetDeviceIdForTest(): void {
  cached = null;
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}
