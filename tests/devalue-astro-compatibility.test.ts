import { describe, expect, it } from 'vitest';
import { uneval } from 'devalue';

describe('Astro content serialization', () => {
  it('preserves URLs with the tagged-template replacer used by Astro', () => {
    const href = 'https://kube-dojo.github.io/k8s/';
    const code = uneval({ site: new URL(href) }, (value, js) => {
      if (value instanceof URL) return js`new URL(${value.href})`;
    });
    const restored = Function(`return (${code})`)() as { site: URL };
    expect(restored.site.href).toBe(href);
  });
});
