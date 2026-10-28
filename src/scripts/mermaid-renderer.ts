import mermaid from 'mermaid';

declare global {
  interface Window {
    __kdMermaid?: { refresh: () => void };
  }
}

const MERMAID_PRE_SELECTOR = 'pre[data-language="mermaid"]';
const state = {
  renderCount: 0,
  lastTheme: null as string | null,
};

function currentTheme(): 'light' | 'dark' {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}

function getMermaidBlocks(root: ParentNode = document): HTMLPreElement[] {
  return Array.from(root.querySelectorAll(MERMAID_PRE_SELECTOR));
}

function getHost(pre: HTMLPreElement): HTMLElement {
  return (pre.closest('figure') || pre.closest('.expressive-code') || pre) as HTMLElement;
}

function getDiagramSource(pre: HTMLPreElement): string {
  // Expressive Code wraps each rendered line in `.ec-line` divs. We walk
  // those directly and join with `\n`. Earlier code used `pre.innerText`,
  // but `innerText` collapses lines that share a layout block — which
  // for tightly-packed diagrams (no blank-line separators between every
  // statement) produced one giant single-line string and broke parsing.
  const ecLines = pre.querySelectorAll('.ec-line');
  if (ecLines.length > 0) {
    return Array.from(ecLines)
      .map((line) => (line.textContent || '').replace(/\u00a0/g, ' '))
      .join('\n')
      .trim();
  }
  // Fallback for non-Expressive-Code rendered blocks.
  return (pre.innerText || pre.textContent || '').replace(/\u00a0/g, ' ').trim();
}

function prepareHost(pre: HTMLPreElement): HTMLElement | null {
  const host = getHost(pre);
  const source = getDiagramSource(pre);
  if (!source) return null;

  host.classList.add('kd-mermaid-host');
  host.dataset.mermaidState = 'loading';
  host.dataset.mermaidSource = source;

  let mount = host.querySelector('.kd-mermaid__mount') as HTMLDivElement | null;
  if (!mount) {
    mount = document.createElement('div');
    mount.className = 'kd-mermaid__mount';
    mount.setAttribute('aria-live', 'polite');
    pre.insertAdjacentElement('afterend', mount);
  }

  return host;
}

async function renderHost(host: HTMLElement): Promise<void> {
  const mount = host.querySelector('.kd-mermaid__mount') as HTMLDivElement | null;
  const source = host.dataset.mermaidSource;
  if (!mount || !source) return;

  host.dataset.mermaidState = 'loading';
  mount.replaceChildren();

  mermaid.initialize({
    startOnLoad: false,
    // Diagrams are author-trusted Markdown, not user input. Keep loose mode so
    // existing labels using <br>, <b>, and <i> render correctly.
    securityLevel: 'loose',
    theme: currentTheme() === 'light' ? 'default' : 'dark',
    layout: 'dagre',
    look: 'classic',
    themeVariables: {
      fontSize: '18px',
      // Git graphs use a separate, smaller label size than the general font.
      commitLabelFontSize: '15px',
      commitLabelColor: currentTheme() === 'light' ? '#111111' : '#ffffff',
      commitLabelBackground: currentTheme() === 'light' ? '#ffffff' : '#0f172a',
      // The default light palette uses pale fills for these mindmap sections.
      ...(currentTheme() === 'light' ? { cScaleLabel0: '#111', cScaleLabel3: '#111' } : {}),
    },
  });

  const renderId = `kd-mermaid-${++state.renderCount}`;
  try {
    const { svg, bindFunctions } = await mermaid.render(renderId, source);
    mount.innerHTML = svg;
    bindFunctions?.(mount);
    host.dataset.mermaidState = 'ready';
    attachZoomHandler(host);
  } catch (error) {
    host.dataset.mermaidState = 'error';
    console.error('Mermaid render failed:', error);
  }
}

// ===== Click-to-enlarge modal =====
//
// Inline SVGs are constrained to fit the prose column for clean reading
// flow. Clicking a diagram opens a fullscreen modal where the SVG renders
// at its natural size (with both-axis scrolling if needed), so the user
// can read every event/label without horizontal-scrolling inside the
// column.

let modalEl: HTMLDivElement | null = null;
let modalContentEl: HTMLDivElement | null = null;
let lastFocusedEl: HTMLElement | null = null;

function ensureModal(): HTMLDivElement {
  if (modalEl) return modalEl;
  modalEl = document.createElement('div');
  modalEl.className = 'kd-mermaid-modal';
  modalEl.dataset.state = 'closed';
  modalEl.setAttribute('role', 'dialog');
  modalEl.setAttribute('aria-modal', 'true');
  modalEl.setAttribute('aria-label', 'Diagram, full size');
  modalEl.innerHTML =
    '<button class="kd-mermaid-modal__close" type="button" aria-label="Close diagram (Escape)">&times;</button>' +
    '<div class="kd-mermaid-modal__content"></div>';
  modalContentEl = modalEl.querySelector('.kd-mermaid-modal__content');

  const closeBtn = modalEl.querySelector<HTMLButtonElement>('.kd-mermaid-modal__close');
  closeBtn?.addEventListener('click', closeModal);
  modalEl.addEventListener('click', (event) => {
    if (event.target === modalEl) closeModal();
  });

  document.body.appendChild(modalEl);
  return modalEl;
}

function openModal(svg: SVGElement): void {
  ensureModal();
  if (!modalEl || !modalContentEl) return;

  const clone = svg.cloneNode(true) as SVGElement;
  // Strip Mermaid's inline max-width and any width/height attrs the inline
  // copy carried, then size the clone to its viewBox so the modal renders
  // it at natural pixel size (otherwise an SVG with only a viewBox collapses
  // to 0×0 inside a flex container that has no intrinsic width).
  clone.removeAttribute('style');
  clone.removeAttribute('width');
  clone.removeAttribute('height');
  const viewBox = clone.getAttribute('viewBox');
  if (viewBox) {
    const parts = viewBox.split(/\s+/).map(Number);
    if (parts.length === 4 && parts.every((n) => Number.isFinite(n))) {
      const [, , vw, vh] = parts;
      clone.setAttribute('width', String(Math.round(vw)));
      clone.setAttribute('height', String(Math.round(vh)));
    }
  }

  modalContentEl.replaceChildren(clone);
  lastFocusedEl = document.activeElement as HTMLElement | null;
  modalEl.dataset.state = 'open';
  document.body.dataset.kdModalOpen = 'true';

  const closeBtn = modalEl.querySelector<HTMLButtonElement>('.kd-mermaid-modal__close');
  closeBtn?.focus();
}

function closeModal(): void {
  if (!modalEl) return;
  modalEl.dataset.state = 'closed';
  delete document.body.dataset.kdModalOpen;
  if (modalContentEl) modalContentEl.replaceChildren();
  if (lastFocusedEl && typeof lastFocusedEl.focus === 'function') {
    lastFocusedEl.focus();
  }
  lastFocusedEl = null;
}

function attachZoomHandler(host: HTMLElement): void {
  if (host.dataset.kdMermaidZoomable === 'true') return;
  host.dataset.kdMermaidZoomable = 'true';
  host.tabIndex = 0;
  host.setAttribute('role', 'button');
  host.setAttribute('aria-label', 'Open diagram full size');

  const trigger = (event: Event) => {
    const svg = host.querySelector<SVGElement>('svg');
    if (!svg || host.dataset.mermaidState !== 'ready') return;
    event.preventDefault();
    openModal(svg);
  };

  host.addEventListener('click', trigger);
  host.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') trigger(event);
  });
}


async function refresh(root: ParentNode = document): Promise<void> {
  document.documentElement.classList.add('js-mermaid');
  const hosts = getMermaidBlocks(root).map(prepareHost).filter(Boolean) as HTMLElement[];
  const theme = currentTheme();

  if (!hosts.length) {
    state.lastTheme = theme;
    return;
  }

  await Promise.all(hosts.map((host) => renderHost(host)));
  state.lastTheme = theme;
}

function runRefresh(): void {
  refresh().catch((error) => {
    console.error('Mermaid initialization failed:', error);
    document.querySelectorAll<HTMLElement>('.kd-mermaid-host').forEach((host) => {
      host.dataset.mermaidState = 'error';
    });
  });
}

if (window.__kdMermaid?.refresh) {
  window.__kdMermaid.refresh();
} else {
  window.__kdMermaid = { refresh: runRefresh };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', runRefresh, { once: true });
  } else {
    runRefresh();
  }

  document.addEventListener('astro:page-load', runRefresh);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modalEl?.dataset.state === 'open') closeModal();
  });

  const themeObserver = new MutationObserver(() => {
    const theme = currentTheme();
    if (theme !== state.lastTheme && document.querySelector('.kd-mermaid-host')) {
      runRefresh();
    }
  });

  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  });
}
