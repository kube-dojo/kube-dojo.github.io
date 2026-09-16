import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const ROUTE_MANIFEST_ENV = 'KUBEDOJO_ROUTE_MANIFEST';
export const ROUTE_MANIFEST_PATTERN = '/_quality/routes.json';
const CONFIG_MODULE = 'virtual:kubedojo-quality-route-manifest-config';

/** Match Astro's absolute context.url.pathname before Starlight formats the canonical URL. */
export function runtimeUrlFromPathname(site, base, pathname) {
  if (!base.startsWith('/') || !pathname.startsWith('/')) throw new Error('KubeDojo route manifest requires root-relative base and pathname');
  const normalizedBase = base.endsWith('/') ? base : `${base}/`;
  return new URL(`${normalizedBase}${pathname.slice(1)}`, site);
}

function privateStarlightModule(pathname) {
  let entrypoint;
  try {
    entrypoint = new URL(import.meta.resolve('@astrojs/starlight'));
  } catch (error) {
    throw new Error('KubeDojo route manifest requires a resolvable @astrojs/starlight package', { cause: error });
  }
  if (entrypoint.protocol !== 'file:') throw new Error('KubeDojo route manifest requires a file-based Starlight package');
  const module = new URL(pathname, entrypoint);
  if (!existsSync(module)) throw new Error(`KubeDojo route manifest is incompatible with this Starlight package: missing ${pathname}`);
  return fileURLToPath(module);
}

function manifestConfig(config) {
  return {
    schemaVersion: 1,
    site: typeof config.site === 'string' ? config.site : config.site?.href ?? null,
    base: config.base,
    trailingSlash: config.trailingSlash,
    buildFormat: config.build.format,
    redirects: Object.entries(config.redirects).map(([source, target]) => ({
      source,
      target: typeof target === 'string' ? target : target.destination,
      status: typeof target === 'string' ? null : target.status,
    })),
  };
}

/** Inject the audit-only endpoint and bridge Starlight's runtime-only route modules. */
export function routeManifestIntegration() {
  let snapshot;
  const configModule = {
    name: 'kubedojo-route-manifest-config',
    resolveId: (id) => id === CONFIG_MODULE ? `\0${CONFIG_MODULE}` : undefined,
    load: (id) => {
      if (id !== `\0${CONFIG_MODULE}`) return undefined;
      if (!snapshot) throw new Error('KubeDojo route manifest did not receive resolved Astro config');
      return `export default ${JSON.stringify(snapshot)}`;
    },
  };
  return {
    name: 'kubedojo-route-manifest',
    hooks: {
      'astro:config:setup': ({ injectRoute, updateConfig }) => {
        if (process.env[ROUTE_MANIFEST_ENV] !== '1') return;
        updateConfig({
          vite: {
            plugins: [configModule],
            resolve: {
              alias: {
                '#kubedojo-quality-starlight-routing': privateStarlightModule('./utils/routing/index.js'),
                '#kubedojo-quality-starlight-slugs': privateStarlightModule('./utils/slugs.js'),
                '#kubedojo-quality-starlight-canonical': privateStarlightModule('./utils/canonical.js'),
              },
            },
          },
        });
        injectRoute({ pattern: ROUTE_MANIFEST_PATTERN, entrypoint: new URL('./route-manifest-endpoint.ts', import.meta.url), prerender: true });
      },
      'astro:config:done': ({ config }) => {
        if (process.env[ROUTE_MANIFEST_ENV] === '1') snapshot = manifestConfig(config);
      },
    },
  };
}
