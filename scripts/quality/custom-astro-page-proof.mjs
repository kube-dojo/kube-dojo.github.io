import { buildDocumentRouteSet } from './document-route-set.mjs';

export class UnsupportedCustomAstroPage extends TypeError {}

const fail = (message) => { throw new UnsupportedCustomAstroPage(message); };

function attr(tag, name) {
  const quoted = tag.match(new RegExp(`(?:^|\\s)${name}\\s*=\\s*("([^"]*)"|'([^']*)')`, 'i'));
  return quoted ? (quoted[2] ?? quoted[3]) : null;
}

function canonicalHref(html) {
  if (typeof html !== 'string' || !html) fail('rendered HTML must be non-empty text');
  const hrefs = [];
  for (const match of html.matchAll(/<link\b[^>]*>/gi)) {
    const rel = attr(match[0], 'rel');
    if (!rel || !rel.toLowerCase().split(/\s+/).includes('canonical')) continue;
    const href = attr(match[0], 'href');
    if (href == null) fail('canonical link is missing href');
    hrefs.push(href);
  }
  if (hrefs.length !== 1) fail('rendered HTML must contain exactly one canonical link');
  return hrefs[0];
}

function optionalSource(value) {
  if (value == null) return null;
  if (typeof value !== 'string' || !value) fail('page.source must be non-empty text or null');
  if (/[\u0000-\u001f\u007f]/.test(value) || value.startsWith('/') || value.includes('\\') || value.split('/').some((part) => !part || part === '.' || part === '..')) {
    fail('page.source must be a safe relative path');
  }
  if (!value.startsWith('src/pages/') || !value.endsWith('.astro')) fail('page.source must be a custom Astro page');
  return value;
}

/** Prove custom Astro pages from same-build rendered HTML. Routes are never inferred from source filenames. */
export function proveCustomAstroPages(manifest, pages) {
  const routeSet = buildDocumentRouteSet(manifest);
  if (!Array.isArray(pages)) fail('rendered pages must be an array');
  const { origin } = routeSet;
  const { base, trailingSlash } = routeSet.config;
  const root = base.endsWith('/') ? base.slice(0, -1) : base;
  const targetPaths = new Set();
  const proven = [];
  for (const page of pages) {
    if (!page || typeof page !== 'object' || Array.isArray(page)) fail('rendered page must be an object');
    const source = optionalSource(page.source);
    const href = canonicalHref(page.html);
    let url;
    try { url = new URL(href); } catch { fail('canonical href must be a URL'); }
    if (url.href !== href || url.origin !== origin || url.username || url.password || url.search || url.hash) {
      fail('canonical href must be a same-origin serialized URL without credentials, query, or fragment');
    }
    const pathname = url.pathname;
    if (trailingSlash === 'always' && !pathname.endsWith('/')) fail('canonical pathname must use trailingSlash always');
    if (trailingSlash === 'never' && pathname !== '/' && pathname.endsWith('/')) fail('canonical pathname must use trailingSlash never');
    if (base !== '/' && pathname !== root && !pathname.startsWith(`${root}/`)) fail('canonical pathname must lie under config.base');
    if (routeSet.targetPaths.has(pathname)) fail(`custom page collides with document route: ${pathname}`);
    if (targetPaths.has(pathname)) fail(`duplicate custom page pathname: ${pathname}`);
    targetPaths.add(pathname);
    proven.push({ url: href, pathname, source });
  }
  return { origin, config: routeSet.config, pages: proven, targetPaths };
}
