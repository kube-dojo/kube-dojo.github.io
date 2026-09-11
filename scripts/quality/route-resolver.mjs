export class UnsupportedRoute extends TypeError {}

function text(value, label) {
  if (typeof value !== 'string') throw new UnsupportedRoute(`${label} must be text`);
  return value;
}

function parsed(value, label, base) {
  try {
    return new URL(text(value, label), base);
  } catch (error) {
    throw new UnsupportedRoute(`${label} is not a valid URL`, { cause: error });
  }
}

function siteOrigin(value) {
  const origin = parsed(value, 'site origin');
  if (!['http:', 'https:'].includes(origin.protocol) || origin.username || origin.password || origin.search || origin.hash || origin.pathname !== '/') {
    throw new UnsupportedRoute('site origin must be an HTTP(S) origin without a path, query, or fragment');
  }
  return origin;
}

function canonicalSource(value, origin) {
  const source = text(value, 'canonical source');
  if (source.startsWith('//') || (!source.startsWith('/') && !/^[a-z][a-z\d+.-]*:\/\//i.test(source))) {
    throw new UnsupportedRoute('canonical source must be an absolute URL or root-relative path');
  }
  const result = parsed(source, 'canonical source', origin);
  if (!['http:', 'https:'].includes(result.protocol)) throw new UnsupportedRoute('canonical source must be HTTP(S)');
  return result;
}

/** Manifest entries are URL-serialized pathnames; normalization is never a fallback. */
function manifestRoutes(paths, origin) {
  if (typeof paths === 'string' || !paths || typeof paths[Symbol.iterator] !== 'function') throw new UnsupportedRoute('manifest paths must be a non-string iterable');
  const routes = new Set();
  for (const value of paths) {
    const path = text(value, 'manifest route');
    if (!path.startsWith('/') || path.startsWith('//') || path.includes('?') || path.includes('#')) {
      throw new UnsupportedRoute('manifest routes must be root-relative paths');
    }
    const route = parsed(path, 'manifest route', origin);
    if (route.origin !== origin.origin || route.search || route.hash || route.pathname !== path) throw new UnsupportedRoute('manifest route must be a serialized pathname');
    routes.add(route.pathname);
  }
  return routes;
}

function serializedRedirectPath(value, origin, label) {
  const path = text(value, label);
  if (!path.startsWith('/') || path.startsWith('//') || path.includes('?') || path.includes('#') || /[\[\]*]/.test(path)) {
    throw new UnsupportedRoute(`${label} must be a root-relative pathname`);
  }
  const route = parsed(path, label, origin);
  if (route.origin !== origin.origin || route.search || route.hash || route.pathname !== path) {
    throw new UnsupportedRoute(`${label} must be a serialized pathname`);
  }
  return path;
}

function redirectMap(redirects, origin) {
  if (redirects === undefined) return new Map();
  if (typeof redirects === 'string' || !redirects || typeof redirects[Symbol.iterator] !== 'function') {
    throw new UnsupportedRoute('redirects must be a non-string iterable');
  }
  const map = new Map();
  for (const entry of redirects) {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) throw new UnsupportedRoute('redirect must be an object');
    const source = serializedRedirectPath(entry.source, origin, 'redirect source');
    const target = serializedRedirectPath(entry.target, origin, 'redirect target');
    if (map.has(source)) throw new UnsupportedRoute('duplicate redirect source');
    map.set(source, target);
  }
  return map;
}

function followRedirects(pathname, map) {
  const seen = new Set();
  let current = pathname;
  while (map.has(current)) {
    if (seen.has(current)) throw new UnsupportedRoute('redirect cycle');
    if (seen.size >= 32) throw new UnsupportedRoute('redirect chain too long');
    seen.add(current);
    current = map.get(current);
  }
  return current;
}

function rewritePath(url, pathname, origin) {
  const next = parsed(pathname, 'redirect destination', origin);
  if (next.origin !== origin.origin || next.search || next.hash || next.pathname !== pathname) {
    throw new UnsupportedRoute('redirect destination must be a serialized pathname');
  }
  next.search = url.search;
  next.hash = url.hash;
  return next;
}

/** Resolve one URL; configured redirect sources follow to the final pathname before routeExists. */
export function resolveRoute(href, canonicalSourceValue, siteOriginValue, knownPaths, redirects) {
  const origin = siteOrigin(siteOriginValue);
  const source = canonicalSource(canonicalSourceValue, origin);
  const routes = manifestRoutes(knownPaths, origin);
  const chains = redirectMap(redirects, origin);
  const target = parsed(href, 'href', source);
  if (target.protocol === 'mailto:') return { url: target.href, kind: 'mailto', path: null, routeExists: null };
  if (!['http:', 'https:'].includes(target.protocol)) throw new UnsupportedRoute('only HTTP(S) and mailto links are supported');
  const internal = target.origin === origin.origin;
  if (!internal) return { url: target.href, kind: 'external-http', path: target.pathname, routeExists: null };
  const path = followRedirects(target.pathname, chains);
  const resolved = path === target.pathname ? target : rewritePath(target, path, origin);
  return { url: resolved.href, kind: 'internal', path, routeExists: routes.has(path) };
}
