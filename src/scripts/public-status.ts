/** Queue metadata only: no source, editorial, lab or translation acceptance. */
export function isStatusPage(filePath: string | undefined): boolean {
  const prefix = 'src/content/docs/';
  if (!filePath?.startsWith(prefix)) throw new Error('Status scope requires a known docs source path');
  const id = filePath.slice(prefix.length).replace(/\.[^.]+$/, '');
  const roots = new Set(['ai', 'ai-history', 'ai-ml-engineering', 'cloud', 'k8s',
    'linux', 'on-premises', 'platform', 'prerequisites']);
  return roots.has(id.split('/')[0]) && id.split('/').at(-1) !== 'index';
}

export function summarizeFlags(entries: readonly { revisionPending?: unknown; qaPending?: unknown }[]) {
  const rework = entries.filter((entry) => entry.revisionPending === true).length;
  const review = entries.filter((entry) => entry.qaPending === true).length;
  const flagged = entries.filter((entry) => entry.revisionPending === true || entry.qaPending === true).length;
  return { total: entries.length, rework, review, flagged, unflagged: entries.length - flagged };
}
