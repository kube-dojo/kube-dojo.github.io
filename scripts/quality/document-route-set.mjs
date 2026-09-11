export class UnsupportedDocumentRouteManifest extends TypeError {}

const fail = (message) => { throw new UnsupportedDocumentRouteManifest(message); };
const object = (value, label) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) fail(`${label} must be an object`);
  return value;
};
const text = (value, label) => {
  if (typeof value !== 'string' || !value) fail(`${label} must be non-empty text`);
  return value;
};
const optionalText = (value, label) => {
  if (value !== null && (typeof value !== 'string' || !value)) fail(`${label} must be non-empty text or null`);
  return value;
};

function originFor(config) {
  const site = text(config.site, 'config.site');
  let url;
  try { url = new URL(site); } catch { fail('config.site must be a URL'); }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) fail('config.site must be an HTTP(S) URL without credentials, query, or fragment');
  if (typeof config.base !== 'string' || !config.base.startsWith('/') || config.base.startsWith('//') || config.base.includes('?') || config.base.includes('#')) fail('config.base must be a root-relative path');
  if (new URL(config.base, url.origin).pathname !== config.base) fail('config.base must be a serialized root-relative path');
  if (!['always', 'never', 'ignore'].includes(config.trailingSlash)) fail('config.trailingSlash is unsupported');
  if (config.buildFormat !== 'directory') fail('config.buildFormat is unsupported');
  return { origin: url.origin, base: config.base };
}

function safeSource(value) {
  const source = text(value, 'route.source');
  if (/[\u0000-\u001f\u007f]/.test(source) || source.startsWith('/') || source.startsWith('\\') || source.includes('\\') || source.split('/').some((part) => !part || part === '.' || part === '..')) fail('route.source must be a safe relative path');
  return source;
}

function serializedPath(value, origin, label = 'route.pathname') {
  const pathname = text(value, label);
  if (!pathname.startsWith('/') || pathname.startsWith('//') || pathname.includes('?') || pathname.includes('#')) fail(`${label} must be a root-relative serialized pathname`);
  let url;
  try { url = new URL(pathname, origin); } catch { fail(`${label} must be a URL pathname`); }
  if (url.origin !== origin || url.pathname !== pathname || url.search || url.hash) fail(`${label} must be a serialized pathname`);
  return pathname;
}

function record(value, { origin, base }) {
  object(value, 'route');
  const pathname = serializedPath(value.pathname, origin);
  const root = base.endsWith('/') ? base.slice(0, -1) : base;
  if (base !== '/' && pathname !== root && !pathname.startsWith(`${root}/`)) fail('route.pathname must lie under config.base');
  const urlText = text(value.url, 'route.url');
  let url;
  try { url = new URL(urlText); } catch { fail('route.url must be a URL'); }
  if (url.href !== urlText || url.origin !== origin || url.username || url.password || url.search || url.hash || url.pathname !== pathname) fail('route.url must be a same-origin serialized URL matching route.pathname');
  if (typeof value.isFallback !== 'boolean') fail('route.isFallback must be boolean');
  const hash = text(value.sourceSha256, 'route.sourceSha256');
  if (!/^[a-f\d]{64}$/.test(hash)) fail('route.sourceSha256 must be lowercase SHA-256 hex');
  return { id: text(value.id, 'route.id'), url: urlText, pathname, source: safeSource(value.source), sourceSha256: hash, isFallback: value.isFallback, locale: optionalText(value.locale, 'route.locale'), lang: optionalText(value.lang, 'route.lang') };
}

function redirectRecords(value, origin) {
  if (!Array.isArray(value)) fail('manifest.redirects must be an array');
  const seen = new Set();
  return value.map((redirect) => {
    object(redirect, 'redirect');
    if (redirect.status !== null && (!Number.isInteger(redirect.status) || redirect.status < 300 || redirect.status > 399)) fail('redirect.status must be a 3xx integer or null');
    const source = serializedPath(redirect.source, origin, 'redirect.source');
    const target = serializedPath(redirect.target, origin, 'redirect.target');
    if (/[\[\]*]/.test(source) || /[\[\]*]/.test(target)) fail('redirect patterns are unsupported');
    if (seen.has(source)) fail(`duplicate redirect.source: ${source}`);
    seen.add(source);
    return { source, target, status: redirect.status };
  });
}

/** Validate a schema-1 document manifest without inferring routes from source files. */
export function buildDocumentRouteSet(manifest) {
  object(manifest, 'manifest');
  if (manifest.schemaVersion !== 1 || manifest.scope !== 'starlight-document-routes') fail('unsupported manifest schema or scope');
  const config = originFor(object(manifest.config, 'manifest.config'));
  const redirects = redirectRecords(manifest.redirects, config.origin);
  if (!Array.isArray(manifest.routes)) fail('manifest.routes must be an array');
  const routes = manifest.routes.map((route) => record(route, config));
  const targetPaths = new Set();
  const bySource = new Map();
  for (const route of routes) {
    if (targetPaths.has(route.pathname)) fail(`duplicate route.pathname: ${route.pathname}`);
    targetPaths.add(route.pathname);
    const entries = bySource.get(route.source) ?? [];
    entries.push(route);
    bySource.set(route.source, entries);
  }
  const primaryBySource = new Map();
  for (const [source, entries] of bySource) {
    if (new Set(entries.map((entry) => entry.sourceSha256)).size !== 1) fail(`inconsistent sourceSha256 for ${source}`);
    const primary = entries.filter((entry) => !entry.isFallback);
    if (primary.length !== 1) fail(`source requires exactly one primary route: ${source}`);
    primaryBySource.set(source, primary[0]);
  }
  return { origin: config.origin, config: manifest.config, routes, targetPaths, primaryBySource, fallbacks: routes.filter((route) => route.isFallback), redirects };
}
