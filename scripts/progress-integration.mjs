import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

/** Deliberate private-runtime boundary: fail the build if Starlight moves these APIs. */
export function progressIntegration() {
  let format;
  const configId = 'virtual:kubedojo-progress-format';
  const entrypoint = new URL(import.meta.resolve('@astrojs/starlight'));
  const runtime = (relative) => {
    const url = new URL(relative, entrypoint);
    if (url.protocol !== 'file:' || !existsSync(url)) {
      throw new Error(`Progress catalog cannot resolve Starlight runtime: ${relative}`);
    }
    return fileURLToPath(url);
  };
  return {
    name: 'kubedojo-progress-catalog',
    hooks: {
      'astro:config:setup': ({ injectRoute, updateConfig }) => {
        updateConfig({ vite: { plugins: [{
          name: 'kubedojo-progress-format',
          resolveId: id => id === configId ? `\0${configId}` : undefined,
          load: id => id === `\0${configId}` ? `export default ${JSON.stringify(format)}` : undefined,
        }], resolve: { alias: {
          '#kubedojo-progress-routes': runtime('./utils/routing/index.js'),
          '#kubedojo-progress-slugs': runtime('./utils/slugs.js'),
          '#kubedojo-progress-canonical': runtime('./utils/canonical.js'),
        } } } });
        injectRoute({ pattern: '/progress-catalog.json', entrypoint: new URL('../src/progress-endpoint.ts', import.meta.url), prerender: true });
      },
      'astro:config:done': ({ config }) => {
        if (!config.site || config.build.format !== 'directory') {
          throw new Error('Progress catalog requires a configured site and directory build format');
        }
        format = { format: config.build.format, trailingSlash: config.trailingSlash };
      },
    },
  };
}
