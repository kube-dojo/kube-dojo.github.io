/**
 * KubeDojo Content Enhancer
 * Issue: #138
 *
 * Runs on every page. Finds War Story, Did You Know, and Quiz patterns
 * in existing .md content and adds CSS classes for rich styling.
 * No .md files are modified — purely additive DOM enhancement.
 */

function enhanceContent(): void {
  const content = document.querySelector('.sl-markdown-content');
  if (!content) return;

  enhanceMetaChips(content);
  enhanceWarStories(content);
  enhanceDidYouKnow(content);
  enhanceQuizSections(content);
  enhanceDedication(content);
}

/**
 * Meta Chips: Style the first blockquote (Complexity/Time/Prerequisites)
 * as colored badge chips matching the POC design.
 */
/**
 * Meta Chips: Transform the first blockquote (Complexity/Time/Prerequisites)
 * into colored inline chips matching the POC design.
 * POC shows: ⚠ Medium | ⏱ 45-55 min | 🏆 CKA Exam (as colored pills on one line)
 */
function buildChips(complexity: string | null, time: string | null): HTMLDivElement | null {
  const div = document.createElement('div');
  div.className = 'kd-meta-chips';

  if (complexity) {
    const upper = complexity.toUpperCase();
    const cls = upper === 'QUICK' ? 'kd-chip-quick' :
                (upper === 'MEDIUM' ? 'kd-chip-medium' : 'kd-chip-advanced');
    const icon = upper === 'QUICK' ? '✓' : upper === 'MEDIUM' ? '⚠' : '⚡';

    const chip = document.createElement('span');
    chip.className = `kd-chip ${cls}`;
    chip.textContent = `${icon} ${upper.charAt(0) + upper.slice(1).toLowerCase()}`;
    div.appendChild(chip);
  }

  if (time) {
    const chip = document.createElement('span');
    chip.className = 'kd-chip kd-chip-time';
    chip.textContent = `⏱ ${time}`;
    div.appendChild(chip);
  }

  if (div.children.length === 0) return null;
  return div;
}

export function enhanceMetaChips(root: Element): void {
  if (root.querySelector('.kd-meta-chips')) return; // already enhanced

  // Pattern 1: blockquote format (e.g. "> **Toolkit Track** | Complexity: `[COMPLEX]` | Time: 45 min")
  const firstBq = root.querySelector('blockquote');
  if (firstBq && !firstBq.closest('.kd-warstory') && !firstBq.closest('.kd-dyk')) {
    // Parse a detached copy first so a non-metadata quote keeps its original nodes.
    const collect = (quote: Element) => {
      let complexity: string | null = null;
      let time: string | null = null;
      const removals = new Set<Node>();
      const paragraphs = [...quote.children].filter((el) => el.tagName === 'P');
      const containers = paragraphs.length ? paragraphs : [quote];
      for (const container of containers) {
        // Split only direct text separators; leave inline elements and links intact.
        for (const node of [...container.childNodes]) {
          if (node.nodeType !== Node.TEXT_NODE || !/[|\n]/.test(node.textContent || '')) continue;
          const parts = (node.textContent || '').split(/([|\n])/);
          const fragment = document.createDocumentFragment();
          parts.forEach((part) => fragment.appendChild(document.createTextNode(part)));
          node.parentNode?.replaceChild(fragment, node);
        }
        const segments: Node[][] = [[]];
        const separators: Node[] = [];
        for (const node of [...container.childNodes]) {
          if (node.nodeName === 'BR' || (node.nodeType === Node.TEXT_NODE && /^[|\n]$/.test(node.textContent || ''))) {
            separators.push(node); segments.push([]);
          } else segments[segments.length - 1].push(node);
        }
        segments.forEach((segment, index) => {
          // An unfamiliar element may carry content or behavior: leave it untouched.
          if (segment.some((node) => node instanceof Element &&
            (node.matches(':not(strong):not(em):not(code)') || node.querySelector(':not(strong):not(em):not(code)')))) return;
          const text = segment.map((node) => node.textContent || '').join('').trim();
          const c = text.match(/^Complexity:\s*\[?(QUICK|MEDIUM|COMPLEX|ADVANCED|EXPERT)\]?$/i);
          const t = text.match(/^Time(?:\s+to\s+Complete)?:\s*(.+)$/i);
          if (!c && !t) return;
          if (c) complexity = c[1];
          if (t) time = t[1].trim();
          segment.forEach((node) => removals.add(node));
          const separator = separators[index] || separators[index - 1];
          if (separator) removals.add(separator);
        });
      }
      return { chips: buildChips(complexity, time), removals, containers };
    };
    const preview = collect(firstBq.cloneNode(true) as Element);
    const { chips, removals, containers } = preview.chips
      ? collect(firstBq) : preview;
    if (chips) {
      removals.forEach((node) => node.parentNode?.removeChild(node));
      for (const container of containers) {
        if (container !== firstBq && !container.textContent?.trim() && !container.children.length) container.remove();
      }
      firstBq.before(chips);
      if (!firstBq.textContent?.trim() && !firstBq.children.length) firstBq.remove();
      return;
    }
  }

  // Pattern 2: H2 heading format (e.g. "## Complexity: [COMPLEX]" + "## Time to Complete: 55-60 min")
  const headings = root.querySelectorAll('h2');
  let complexityH2: Element | null = null;
  let timeH2: Element | null = null;
  let complexity: string | null = null;
  let time: string | null = null;

  for (const h2 of headings) {
    const text = h2.textContent || '';
    const cMatch = text.match(/Complexity:\s*\[?(QUICK|MEDIUM|COMPLEX|ADVANCED|EXPERT)\]?/i);
    if (cMatch) { complexityH2 = h2; complexity = cMatch[1]; continue; }
    const tMatch = text.match(/Time(?:\s+to\s+Complete)?:\s*(.+)/i);
    if (tMatch) { timeH2 = h2; time = tMatch[1].trim(); continue; }
    // Stop scanning after first non-meta heading
    if (complexityH2 || timeH2) break;
  }

  if (!complexityH2 && !timeH2) return;

  const chips = buildChips(complexity, time);
  if (!chips) return;

  // Replace the first meta heading with chips, remove the other
  const firstEl = complexityH2 || timeH2;
  const secondEl = complexityH2 && timeH2 ? (complexityH2 === firstEl ? timeH2 : complexityH2) : null;
  // Remove the HR between them if present
  if (firstEl && secondEl) {
    let between = firstEl.nextElementSibling;
    while (between && between !== secondEl) {
      const next = between.nextElementSibling;
      if (between.tagName === 'HR') between.remove();
      between = next;
    }
    secondEl.remove();
  }
  firstEl!.replaceWith(chips);
}

/**
 * War Stories: Find headings containing "War Story" and wrap
 * the heading + following content in a styled card.
 */
/** Get the outermost element for a heading (may be wrapped in .sl-heading-wrapper by Starlight) */
function headingRoot(heading: Element): Element {
  const wrapper = heading.closest('.sl-heading-wrapper');
  return wrapper || heading;
}

/** Check if an element is a heading of given level or lower */
function isHeadingAtOrAbove(el: Element, level: number): boolean {
  // Direct heading tag
  if (el.tagName.match(/^H[1-6]$/) && parseInt(el.tagName[1]) <= level) return true;
  // Starlight heading wrapper containing such a heading
  if (el.classList.contains('sl-heading-wrapper')) {
    const h = el.querySelector('h1, h2, h3, h4, h5, h6');
    if (h && parseInt(h.tagName[1]) <= level) return true;
  }
  return false;
}

function enhanceWarStories(root: Element): void {
  const headings = root.querySelectorAll('h2, h3, h4');
  headings.forEach((heading) => {
    const text = heading.textContent || '';
    if (!text.toLowerCase().includes('war story')) return;
    if (heading.closest('.kd-warstory')) return; // already enhanced

    // Extract impact from heading text (e.g. "$2.3M lost revenue")
    const impactMatch = text.match(/\$[\d.,]+[MBK]?\s*[\w\s]*/i);

    // Walk siblings from the heading's root (wrapper div or heading itself)
    const hRoot = headingRoot(heading);
    const level = parseInt(heading.tagName[1]);
    const siblings: Element[] = [];
    let next = hRoot.nextElementSibling;
    while (next) {
      if (isHeadingAtOrAbove(next, level)) break;
      siblings.push(next);
      next = next.nextElementSibling;
    }

    // Build wrapper — preserve heading ID for anchor links
    const wrapper = document.createElement('div');
    wrapper.className = 'kd-warstory';
    if (heading.id) wrapper.id = heading.id;

    const header = document.createElement('div');
    header.className = 'kd-warstory-header';

    const iconSpan = document.createElement('span');
    iconSpan.textContent = '🔥';
    header.appendChild(iconSpan);

    const titleSpan = document.createElement('span');
    titleSpan.textContent = text.replace(/war story:?\s*/i, '').trim() || 'War Story';
    header.appendChild(titleSpan);

    if (impactMatch) {
      const impactSpan = document.createElement('span');
      impactSpan.className = 'impact';
      impactSpan.textContent = impactMatch[0].trim();
      header.appendChild(impactSpan);
    }

    const body = document.createElement('div');
    body.className = 'kd-warstory-body';

    // Move siblings into body
    siblings.forEach((el) => body.appendChild(el));

    wrapper.appendChild(header);
    wrapper.appendChild(body);

    // Replace the heading root (wrapper or heading) with the war story card
    hRoot.replaceWith(wrapper);
  });
}

/**
 * Did You Know: Find headings or blockquotes containing "Did You Know"
 * and wrap in a styled card.
 */
function enhanceDidYouKnow(root: Element): void {
  // Pattern 1: ## Did You Know? heading followed by blockquotes
  const headings = root.querySelectorAll('h2, h3');
  headings.forEach((heading) => {
    const text = heading.textContent || '';
    if (!text.toLowerCase().includes('did you know')) return;
    if (heading.closest('.kd-dyk')) return;

    // Walk siblings from the heading's root (wrapper div or heading itself)
    const hRoot = headingRoot(heading);
    const blockquotes: Element[] = [];
    let next = hRoot.nextElementSibling;
    while (next) {
      if (next.tagName === 'BLOCKQUOTE') {
        blockquotes.push(next);
      } else if (next.tagName === 'HR' || isHeadingAtOrAbove(next, parseInt(heading.tagName[1]))) {
        break;
      }
      next = next.nextElementSibling;
    }

    if (blockquotes.length === 0) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'kd-dyk';
    if (heading.id) wrapper.id = heading.id;

    const header = document.createElement('div');
    header.className = 'kd-dyk-header';
    header.textContent = '💡 Did You Know?';

    wrapper.appendChild(header);
    blockquotes.forEach((bq) => {
      const div = document.createElement('div');
      div.className = 'kd-dyk-item';
      // Move all children from the blockquote to our new div
      while (bq.firstChild) {
        div.appendChild(bq.firstChild);
      }
      wrapper.appendChild(div);
    });

    // Replace heading root and blockquotes
    blockquotes.forEach((bq) => bq.remove());
    hRoot.replaceWith(wrapper);
  });
}

/**
 * Quiz sections: Enhance details/summary blocks within quiz sections
 * with letter badges and better styling.
 */
function enhanceQuizSections(root: Element): void {
  // Find quiz headings
  const headings = root.querySelectorAll('h2, h3');
  headings.forEach((heading) => {
    const text = (heading.textContent || '').toLowerCase();
    if (!text.includes('quiz') && !text.includes('knowledge check')) return;

    // Find all details elements after this heading
    let next = heading.nextElementSibling;
    let questionNum = 0;
    while (next) {
      if (next.tagName.match(/^H[1-6]$/) && next.tagName <= heading.tagName) break;

      if (next.tagName === 'DETAILS') {
        const summary = next.querySelector('summary');
        if (summary && !summary.querySelector('.kd-quiz-badge')) {
          questionNum++;
          const badge = document.createElement('span');
          badge.className = 'kd-quiz-badge';
          badge.textContent = `Q${questionNum}`;
          badge.style.cssText = `
            display: inline-block; background: #326CE5; color: white;
            font-size: 0.7rem; font-weight: 700; padding: 0.1rem 0.5rem;
            border-radius: 4px; margin-right: 0.5rem; font-family: var(--sl-font-mono);
          `;
          summary.prepend(badge);
        }
        next.classList.add('kd-quiz-item');
      }
      next = next.nextElementSibling;
    }
  });
}

/**
 * Dedication: Wrap the 🇺🇦 Dedication/Присвята section in a Ukrainian flag border.
 */
function enhanceDedication(root: Element): void {
  const headings = root.querySelectorAll('h2');
  headings.forEach((heading) => {
    const text = heading.textContent || '';
    if (!text.includes('Dedication') && !text.includes('Присвята')) return;
    if (heading.closest('.kd-dedication-wrap')) return;

    // Collect ALL siblings until the next <hr> or end of content
    // This captures the h2, paragraphs, h3 (poem title), AND the blockquote (poem)
    const siblings: Element[] = [];
    let next = heading.nextElementSibling;
    while (next) {
      // Stop at <hr> (markdown ---) which separates dedication from the dojo quote
      if (next.tagName === 'HR') break;
      // Stop at another h2 that ISN'T part of the dedication
      if (next.tagName === 'H2' && !next.textContent?.includes('Заповіт') && !next.textContent?.includes('Testament')) break;
      siblings.push(next);
      next = next.nextElementSibling;
    }

    // Build wrapper with flag border
    const outer = document.createElement('div');
    outer.className = 'kd-dedication-wrap';
    const inner = document.createElement('div');
    inner.className = 'kd-dedication-wrap-inner';

    // Clone heading into inner, then move siblings
    inner.appendChild(heading.cloneNode(true));
    siblings.forEach((el) => inner.appendChild(el));

    outer.appendChild(inner);
    heading.replaceWith(outer);
  });
}

// Run on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', enhanceContent);
} else {
  enhanceContent();
}

// Re-run on Astro page transitions (View Transitions)
document.addEventListener('astro:page-load', enhanceContent);
