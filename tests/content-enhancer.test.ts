import { describe, it, expect, beforeEach, vi } from 'vitest';

// Suppress browser boot only while importing the real transform.
const readyState = vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
const addEventListener = vi.spyOn(document, 'addEventListener').mockImplementation(() => {});
const { enhanceMetaChips } = await import('../src/scripts/content-enhancer');
readyState.mockRestore();
addEventListener.mockRestore();

// Test the content enhancer DOM transforms by simulating the patterns
// it looks for and verifying the output.

// Helper: create a minimal .sl-markdown-content container
function createContent(html: string): Element {
  document.body.innerHTML = `<div class="sl-markdown-content">${html}</div>`;
  return document.querySelector('.sl-markdown-content')!;
}

// The other enhancer helpers below are test-local; metadata uses production code.

function enhanceWarStories(root: Element): void {
  const headings = root.querySelectorAll('h2, h3, h4');
  headings.forEach((heading) => {
    const text = heading.textContent || '';
    if (!text.toLowerCase().includes('war story')) return;
    if (heading.closest('.kd-warstory')) return;

    const level = parseInt(heading.tagName[1]);
    const siblings: Element[] = [];
    let next = heading.nextElementSibling;
    while (next) {
      if (next.tagName.match(/^H[1-6]$/) && parseInt(next.tagName[1]) <= level) break;
      siblings.push(next);
      next = next.nextElementSibling;
    }

    const wrapper = document.createElement('div');
    wrapper.className = 'kd-warstory';

    const header = document.createElement('div');
    header.className = 'kd-warstory-header';

    const iconSpan = document.createElement('span');
    iconSpan.textContent = '🔥';
    header.appendChild(iconSpan);

    const titleSpan = document.createElement('span');
    titleSpan.textContent = text.replace(/war story:?\s*/i, '').trim() || 'War Story';
    header.appendChild(titleSpan);

    const body = document.createElement('div');
    body.className = 'kd-warstory-body';
    siblings.forEach((el) => body.appendChild(el));

    wrapper.appendChild(header);
    wrapper.appendChild(body);
    heading.replaceWith(wrapper);
  });
}

function enhanceQuizSections(root: Element): void {
  const headings = root.querySelectorAll('h2, h3');
  headings.forEach((heading) => {
    const text = (heading.textContent || '').toLowerCase();
    if (!text.includes('quiz') && !text.includes('knowledge check')) return;

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
          summary.prepend(badge);
        }
        next.classList.add('kd-quiz-item');
      }
      next = next.nextElementSibling;
    }
  });
}

describe('Content Enhancer — Meta Chips', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('preserves prerequisites in the captured production header', () => {
    const root = createContent("<blockquote>\n<p><strong>Complexity</strong>: <code dir=\"auto\">[MEDIUM]</code></p>\n<p><strong>Time to Complete</strong>: 100–130 minutes (estimate for reading and practice, not measured learner timing)</p>\n<p><strong>Prerequisites</strong>: Module 3 of Git Deep Dive and Git 2.28 or later (the lab uses <code dir=\"auto\">git init -b</code>).</p>\n</blockquote>\n");
    enhanceMetaChips(root);
    expect(root.querySelectorAll('.kd-chip')).toHaveLength(2);
    expect(root.querySelector('blockquote')?.textContent).toContain('Git 2.28 or later');
    expect(root.querySelector('blockquote')?.textContent).toContain('Prerequisites');
  });

  it('preserves prerequisite list and link nodes beside metadata paragraphs', () => {
    const root = createContent('<blockquote><p>Complexity: [MEDIUM]</p><p>Time: 30 min</p><ul><li><a href="/git/">Git prerequisite</a></li></ul></blockquote>');
    const list = root.querySelector('ul');
    const link = root.querySelector('a');
    enhanceMetaChips(root);
    expect(root.querySelectorAll('.kd-chip')).toHaveLength(2);
    expect(root.querySelector('ul')).toBe(list);
    expect(root.querySelector('a')).toBe(link);
    expect(link?.getAttribute('href')).toBe('/git/');
  });

  it('handles Markdown soft breaks without replacing prerequisite links', () => {
    const root = createContent('<blockquote><p><strong>Complexity:</strong> <code>[MEDIUM]</code> - Bridge module\n<strong>Time:</strong> 30 min\nPrerequisite: <a href="/git/">Git</a></p></blockquote>');
    const link = root.querySelector('a'); enhanceMetaChips(root);
    expect(root.querySelectorAll('.kd-chip')).toHaveLength(2);
    expect(root.querySelector('a')).toBe(link);
    expect(root.querySelector('blockquote')?.textContent).toContain('[MEDIUM] - Bridge module');
  });

  it('preserves separate prerequisite and next-module paragraphs and links', () => {
    const root = createContent('<blockquote><p><strong>Complexity</strong>: <code>[MEDIUM]</code></p><p><strong>Time to Complete</strong>: 45 min</p><p><strong>Prerequisites</strong>: <a href="/git/">Git</a></p><p>Next: <a href="/next/">Next module</a></p></blockquote>');
    const links = [...root.querySelectorAll('a')];
    enhanceMetaChips(root);
    expect(root.querySelectorAll('.kd-chip')).toHaveLength(2);
    expect(root.querySelector('blockquote')?.textContent).toContain('Prerequisites');
    expect([...root.querySelectorAll('a')]).toEqual(links);
    expect(links.map((link) => link.getAttribute('href'))).toEqual(['/git/', '/next/']);
  });

  it('handles BR fields and preserves inline unknown content', () => {
    const root = createContent('<blockquote><p><strong>Complexity:</strong> <code>[COMPLEX]</code><br><strong>Time:</strong> 30 min<br>Prerequisite: <a href="/start/">Start</a></p></blockquote>');
    const link = root.querySelector('a');
    enhanceMetaChips(root);
    expect(root.querySelector('.kd-chip-advanced')?.textContent).toContain('Complex');
    expect(root.querySelector('.kd-chip-time')?.textContent).toContain('30 min');
    expect(root.querySelector('a')).toBe(link);
    expect(link?.getAttribute('href')).toBe('/start/');
  });

  it('does not consume a field containing an unknown inline link', () => {
    const root = createContent('<blockquote><p>Complexity: [MEDIUM]</p><p>Time: <a href="/details/">45 min</a></p></blockquote>');
    const link = root.querySelector('a');
    enhanceMetaChips(root);
    expect(root.querySelector('a')).toBe(link);
    expect(root.querySelector('.kd-chip-time')).toBeNull();
  });

  it('preserves unknown pipe fields and removes metadata-only quotes', () => {
    const root = createContent('<blockquote>Toolkit <a href="/more/">More</a> | Complexity: [MEDIUM] | Time: 45 min</blockquote>');
    enhanceMetaChips(root);
    expect(root.querySelector('blockquote')?.textContent).toContain('Toolkit');
    expect(root.querySelector('blockquote')?.textContent).not.toContain('|');
    expect(root.querySelector('a')?.getAttribute('href')).toBe('/more/');
    const only = createContent('<blockquote><p>Complexity: [QUICK]</p><p>Time: 15 min</p></blockquote>');
    enhanceMetaChips(only);
    expect(only.querySelector('blockquote')).toBeNull();
  });

  it('retains heading fallback', () => {
    const root = createContent('<h2>Complexity: [MEDIUM]</h2><h2>Time to Complete: 45 min</h2>');
    enhanceMetaChips(root);
    expect(root.querySelectorAll('.kd-chip')).toHaveLength(2);
  });

  it('transforms complexity blockquote into chips', () => {
    const root = createContent(`
      <blockquote>Complexity: [MEDIUM] | Time to Complete: 45-55 min</blockquote>
      <p>Module content here</p>
    `);
    enhanceMetaChips(root);

    const chips = root.querySelector('.kd-meta-chips');
    expect(chips).not.toBeNull();
    expect(chips!.querySelector('.kd-chip-medium')).not.toBeNull();
    expect(chips!.querySelector('.kd-chip-time')).not.toBeNull();
    expect(chips!.querySelector('.kd-chip-time')!.textContent).toContain('45-55 min');
  });

  it('handles QUICK complexity', () => {
    const root = createContent(`<blockquote>Complexity: [QUICK] | Time to Complete: 15 min</blockquote>`);
    enhanceMetaChips(root);

    const chip = root.querySelector('.kd-chip-quick');
    expect(chip).not.toBeNull();
    expect(chip!.textContent).toContain('Quick');
  });

  it('handles ADVANCED complexity', () => {
    const root = createContent(`<blockquote>Complexity: [ADVANCED] | Time to Complete: 90 min</blockquote>`);
    enhanceMetaChips(root);

    expect(root.querySelector('.kd-chip-advanced')).not.toBeNull();
  });

  it('ignores blockquotes without Complexity/Time', () => {
    const root = createContent(`<blockquote>Just a regular quote</blockquote>`);
    enhanceMetaChips(root);

    expect(root.querySelector('.kd-meta-chips')).toBeNull();
    expect(root.querySelector('blockquote')).not.toBeNull();
  });

  it('leaves original nodes untouched in a non-metadata pipe quote', () => {
    const root = createContent('<blockquote>Alpha | <a href="/guide/">Guide</a> | Beta</blockquote>');
    const quote = root.querySelector('blockquote')!;
    const nodes = [...quote.childNodes];
    enhanceMetaChips(root);
    expect(root.querySelector('.kd-meta-chips')).toBeNull();
    expect(root.querySelector('blockquote')).toBe(quote);
    expect([...quote.childNodes]).toEqual(nodes);
    expect(root.querySelector('a')?.getAttribute('href')).toBe('/guide/');
  });

  it('does not double-enhance', () => {
    const root = createContent(`<blockquote>Complexity: [MEDIUM] | Time to Complete: 30 min</blockquote>`);
    enhanceMetaChips(root);
    enhanceMetaChips(root);

    expect(root.querySelectorAll('.kd-meta-chips').length).toBe(1);
  });

  it('renders time chip text without parsing injected markup', () => {
    const maliciousTime = '<img src=x onerror=alert(1)>';
    const root = createContent(
      `<blockquote>Complexity: [MEDIUM] | Time to Complete: &lt;img src=x onerror=alert(1)&gt;</blockquote>`,
    );
    enhanceMetaChips(root);

    const timeChip = root.querySelector('.kd-chip-time')!;
    expect(timeChip.textContent).toBe(`⏱ ${maliciousTime}`);
    expect(timeChip.querySelector('img')).toBeNull();
    expect(timeChip.innerHTML).not.toContain('<img');
  });
});

describe('Content Enhancer — War Stories', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('wraps war story heading + content in card', () => {
    const root = createContent(`
      <h2>War Story: $2.3M Database Meltdown</h2>
      <p>The database crashed at 3am.</p>
      <p>Nobody had monitoring.</p>
      <h2>Next Section</h2>
    `);
    enhanceWarStories(root);

    const warstory = root.querySelector('.kd-warstory');
    expect(warstory).not.toBeNull();
    expect(warstory!.querySelector('.kd-warstory-header')).not.toBeNull();
    expect(warstory!.querySelector('.kd-warstory-body')!.children.length).toBe(2);
  });

  it('does not capture content past the next heading', () => {
    const root = createContent(`
      <h2>War Story: Outage</h2>
      <p>Story content</p>
      <h2>Unrelated Section</h2>
      <p>Should not be captured</p>
    `);
    enhanceWarStories(root);

    const body = root.querySelector('.kd-warstory-body')!;
    expect(body.children.length).toBe(1);
    expect(body.textContent).toContain('Story content');
    expect(body.textContent).not.toContain('Should not be captured');
  });

  it('does not double-enhance', () => {
    const root = createContent(`<h2>War Story: Test</h2><p>Content</p>`);
    enhanceWarStories(root);
    enhanceWarStories(root);

    expect(root.querySelectorAll('.kd-warstory').length).toBe(1);
  });

  it('renders war story heading text without parsing injected markup', () => {
    const maliciousTitle = '</span><script>alert(1)</script>';
    const root = createContent(
      '<h2>War Story: &lt;/span&gt;&lt;script&gt;alert(1)&lt;/script&gt;</h2><p>Content</p>',
    );
    enhanceWarStories(root);

    const header = root.querySelector('.kd-warstory-header')!;
    const title = header.querySelectorAll('span')[1]!;
    expect(title.textContent).toBe(maliciousTitle);
    expect(header.querySelector('script')).toBeNull();
    expect(header.innerHTML).not.toContain('<script>');
  });
});

describe('Content Enhancer — Quiz Sections', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('adds Q badges to details elements', () => {
    const root = createContent(`
      <h2>Knowledge Check</h2>
      <details><summary>What is a Pod?</summary><p>Answer</p></details>
      <details><summary>What is a Service?</summary><p>Answer</p></details>
      <details><summary>What is a Deployment?</summary><p>Answer</p></details>
    `);
    enhanceQuizSections(root);

    const badges = root.querySelectorAll('.kd-quiz-badge');
    expect(badges.length).toBe(3);
    expect(badges[0].textContent).toBe('Q1');
    expect(badges[1].textContent).toBe('Q2');
    expect(badges[2].textContent).toBe('Q3');
  });

  it('adds kd-quiz-item class to details', () => {
    const root = createContent(`
      <h2>Quiz</h2>
      <details><summary>Question</summary><p>Answer</p></details>
    `);
    enhanceQuizSections(root);

    expect(root.querySelector('details.kd-quiz-item')).not.toBeNull();
  });

  it('ignores non-quiz headings', () => {
    const root = createContent(`
      <h2>Regular Section</h2>
      <details><summary>Some details</summary><p>Content</p></details>
    `);
    enhanceQuizSections(root);

    expect(root.querySelectorAll('.kd-quiz-badge').length).toBe(0);
  });

  it('does not double-badge', () => {
    const root = createContent(`
      <h2>Quiz</h2>
      <details><summary>Q?</summary><p>A</p></details>
    `);
    enhanceQuizSections(root);
    enhanceQuizSections(root);

    expect(root.querySelectorAll('.kd-quiz-badge').length).toBe(1);
  });
});
