import fs from 'node:fs';
import path from 'node:path';
import { parseArgs } from 'node:util';
import { resolveRoute, UnsupportedRoute } from './route-resolver.mjs';
import { buildDocumentRouteSet } from './document-route-set.mjs';

const SOURCE_PREFIX = 'src/content/docs/';

export function extractLinks(content) {
  const links = [];
  const lines = content.split('\n');
  const linkRegex = /\[(?:[^\]\\]|\\.)*\]\(\s*([^)\s]+)(?:\s+"[^"]*")?\s*\)/g;
  let inFencedBlock = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.trim().startsWith('```')) {
      inFencedBlock = !inFencedBlock;
      continue;
    }
    if (inFencedBlock) continue;
    
    let processedLine = line.replace(/`[^`]*`/g, '');
    let match;
    while ((match = linkRegex.exec(processedLine)) !== null) {
      links.push({ href: match[1], line: i + 1 });
    }
  }
  return links;
}

export function consumeMarkdownLinks(manifest, docsRoot) {
  const routeSet = buildDocumentRouteSet(manifest);
  const fallbackPaths = new Set(routeSet.fallbacks.map(f => f.pathname));
  
  const files = [];
  function walk(dir) {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(fullPath);
      else if (entry.isFile() && /\.(md|mdx)$/i.test(entry.name)) files.push(fullPath);
    }
  }
  walk(docsRoot);
  
  const report = [];
  const memo = new Map();
  
  for (const file of files) {
    const relativeToDocs = path.relative(docsRoot, file).split(path.sep).join('/');
    const source = SOURCE_PREFIX + relativeToDocs;
    
    const primary = routeSet.primaryBySource.get(source);
    if (!primary) continue;
    
    const content = fs.readFileSync(file, 'utf8');
    const links = extractLinks(content);
    
    for (const { href, line } of links) {
      let target = null;
      let disposition = '';
      
      if (href.startsWith('#')) {
        disposition = 'fragment-only';
        target = new URL(href, primary.url).href;
      } else {
        const memoKey = `${href}::${primary.url}`;
        if (memo.has(memoKey)) {
          const res = memo.get(memoKey);
          target = res.target;
          disposition = res.disposition;
        } else {
          try {
            const resolved = resolveRoute(href, primary.url, routeSet.origin, routeSet.targetPaths);
            target = resolved.url;
            if (resolved.kind === 'external-http' || resolved.kind === 'mailto') {
              disposition = 'external';
            } else if (resolved.routeExists) {
              disposition = fallbackPaths.has(resolved.path) ? 'present-fallback' : 'present';
            } else {
              disposition = 'missing';
            }
          } catch (error) {
            if (error instanceof UnsupportedRoute) {
              disposition = 'unsupported';
            } else {
              throw error;
            }
          }
          memo.set(memoKey, { target, disposition });
        }
      }
      
      report.push({
        source,
        line,
        href,
        target,
        disposition
      });
    }
  }
  return report;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { values, positionals } = parseArgs({
    options: {
      output: { type: 'string', default: '.agent/markdown-links.json' },
    },
    allowPositionals: true,
  });
  
  const manifestPath = positionals[0];
  if (!manifestPath) {
    console.error('Usage: node markdown-link-consumer.mjs <manifest.json> [--output path]');
    process.exit(1);
  }
  
  const manifestRaw = fs.readFileSync(manifestPath, 'utf8');
  const manifest = JSON.parse(manifestRaw);
  
  const docsRoot = path.resolve(process.cwd(), 'src/content/docs');
  
  const report = consumeMarkdownLinks(manifest, docsRoot);
  
  fs.mkdirSync(path.dirname(values.output), { recursive: true });
  fs.writeFileSync(values.output, JSON.stringify(report, null, 2), 'utf8');
  console.log(`Wrote ${report.length} links to ${values.output}`);
}
