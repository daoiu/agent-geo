// v0.7: ambient typing for `*.config.js` ES module Tailwind exports so
// tests can `import tailwindConfig from '../../tailwind.config.js'` without
// triggering TS7016. The shape is intentionally loose — `theme.extend` is
// `Record<string, unknown>` because Tailwind accepts arbitrary keys.
declare module '*.config.js' {
  const config: {
    theme: {
      extend: Record<string, unknown>;
    };
    [key: string]: unknown;
  };
  export default config;
}
