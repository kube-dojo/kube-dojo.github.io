// @ts-check
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'astro/config';
import { unified } from '@astrojs/markdown-remark';
import starlight from '@astrojs/starlight';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { routeManifestIntegration } from './scripts/quality/route-manifest-integration.mjs';
import { progressIntegration } from './scripts/progress-integration.mjs';

const projectRoot = fileURLToPath(new URL('.', import.meta.url));
const ignoredDevWatchPaths = [
  '.bridge',
  '.cache',
  '.pids',
  '.pipeline',
  '.worktrees',
  'logs',
].map((dir) => `${projectRoot}${dir}/**`);

export default defineConfig({
  site: 'https://kube-dojo.github.io',
  trailingSlash: 'always',
  compressHTML: true,
  redirects: {
    // ML curriculum reorganization (#677): classical-ml/ -> machine-learning/
    '/ai-ml-engineering/classical-ml/': '/ai-ml-engineering/machine-learning/',
    '/ai-ml-engineering/classical-ml/index/': '/ai-ml-engineering/machine-learning/',
    '/ai-ml-engineering/classical-ml/module-1.1-scikit-learn-classical-ml/':
      '/ai-ml-engineering/machine-learning/module-1.1-scikit-learn-api-and-pipelines/',
    '/ai-ml-engineering/classical-ml/module-1.2-xgboost-gradient-boosting/':
      '/ai-ml-engineering/machine-learning/module-1.6-xgboost-gradient-boosting/',
    '/ai-ml-engineering/classical-ml/module-1.3-time-series-forecasting/':
      '/ai-ml-engineering/machine-learning/module-1.12-time-series-forecasting/',
    // #1639 Option B §4: retired moved-stubs — prompt/harness/symphony teaching
    // consolidated into the canonical ai-engineering-foundations spine.
    '/ai/ai-native-work/module-2.1-harness-engineering/':
      '/ai/ai-engineering-foundations/module-3.1-harness-fundamentals-layers-and-system-of-record/',
    '/ai/ai-native-work/module-2.2-orchestrating-fleets-symphony/':
      '/ai/ai-engineering-foundations/module-4.1-symphony-work-orchestration-as-applied-harness/',
    '/ai-ml-engineering/ai-native-development/module-1.6-prompt-engineering-fundamentals/':
      '/ai/ai-engineering-foundations/module-1.1-prompt-fundamentals/',
    // Block A rescope: 1.7 -> 1.1.8 computational graphs & scalar autograd
    '/ai-ml-engineering/deep-learning/module-1.7-backpropagation-and-autograd-from-scratch/':
      '/ai-ml-engineering/deep-learning/module-1.1.8-computational-graphs-scalar-autograd/',
    // Block B: 1.4 gutted — its norm/reg/opt survey is now the 1.3.1-1.3.6 sub-chain
    '/ai-ml-engineering/deep-learning/module-1.4-cnns-computer-vision/':
      '/ai-ml-engineering/deep-learning/module-1.3.1-initialization-signal-propagation/',
    // Block C: 1.6 gutted — its attention/transformer content is now the 1.4.1-1.4.4 sub-chain
    '/ai-ml-engineering/deep-learning/module-1.6-backpropagation-deep-dive/':
      '/ai-ml-engineering/deep-learning/module-1.4.4-transformer-block-from-scratch/',
    // Block D: old 1.5 slug was mislabeled 'rnns' but bodied CNNs; now the canonical CNN module
    '/ai-ml-engineering/deep-learning/module-1.5-rnns-sequence-models/':
      '/ai-ml-engineering/deep-learning/module-1.5-cnns-computer-vision/',
  },
  markdown: {
    // Astro 7 defaults to the Rust "Sätteri" markdown engine, which drops the
    // unified remark/rehype pipeline. We keep KaTeX by explicitly running the
    // unified processor from @astrojs/markdown-remark (a Starlight 0.41 peer dep).
    processor: unified({
      remarkPlugins: [remarkMath],
      rehypePlugins: [rehypeKatex],
    }),
  },
  vite: {
    server: {
      watch: {
        ignored: ignoredDevWatchPaths,
      },
    },
    build: {
      rollupOptions: {
        onwarn(warning, defaultWarn) {
          if (
            warning.message?.includes('"matchHostname", "matchPathname", "matchPort" and "matchProtocol"') &&
            warning.message?.includes('@astrojs/internal-helpers/remote') &&
            warning.message?.includes('node_modules/astro/dist/assets/utils/index.js')
          ) {
            return;
          }
          defaultWarn(warning);
        },
      },
    },
  },

  integrations: [
    starlight({
      title: 'KubeDojo',
      tagline: 'Free, comprehensive cloud native education',
      disable404Route: false,
      // GoatCounter — privacy-friendly analytics (no cookies). Injected into the
      // <head> of every page via the default Starlight Head (kept by our custom
      // src/components/Head.astro override, which renders <Default>). The loader is
      // self-hosted at /count.js (public/count.js) to avoid a third-party CDN script
      // dependency, matching the repo's posture for Mermaid and the content scripts.
      head: [
        {
          tag: 'script',
          attrs: {
            'data-goatcounter': 'https://kube-dojo.goatcounter.com/count',
            src: '/count.js',
            async: true,
          },
        },
      ],
      expressiveCode: {
        shiki: {
          langAlias: {
            ascii: 'txt',
            jinja2: 'jinja',
            kubernetes: 'yaml',
            logql: 'txt',
            promql: 'txt',
            rego: 'txt',
            traceql: 'txt',
            wing: 'typescript',
          },
        },
      },
      social: [
        {
          label: 'GitHub',
          icon: 'github',
          href: 'https://github.com/kube-dojo/kube-dojo.github.io',
        },
      ],
      credits: false,
      components: {
        Head: './src/components/Head.astro',
        Header: './src/components/Header.astro',
        Footer: './src/components/Footer.astro',
        Sidebar: './src/components/Sidebar.astro',
        PageTitle: './src/components/PageTitle.astro',
      },
      defaultLocale: 'root',
      locales: {
        root: { label: 'English', lang: 'en' },
        uk: { label: 'Українська', lang: 'uk' },
      },
      customCss: ['./src/css/custom.css', 'katex/dist/katex.min.css'],
      sidebar: [

        // ── 1. Foundations: beginner entry points ──

        {
          label: 'Fundamentals',
          collapsed: true,
          items: [
            { label: 'Fundamentals Hub', link: '/prerequisites/' },
            { label: 'Zero to Terminal', collapsed: true, items: [{ autogenerate: { directory: 'prerequisites/zero-to-terminal', collapsed: true } }] },
            { label: 'Everyday Linux', collapsed: true, items: [{ autogenerate: { directory: 'linux/foundations/everyday-use', collapsed: true } }] },
            { label: 'Cloud Native 101', collapsed: true, items: [{ autogenerate: { directory: 'prerequisites/cloud-native-101', collapsed: true } }] },
            { label: 'Kubernetes Basics', collapsed: true, items: [{ autogenerate: { directory: 'prerequisites/kubernetes-basics', collapsed: true } }] },
            { label: 'Philosophy & Design', collapsed: true, items: [{ autogenerate: { directory: 'prerequisites/philosophy-design', collapsed: true } }] },
            { label: 'Git Deep Dive', collapsed: true, items: [{ autogenerate: { directory: 'prerequisites/git-deep-dive', collapsed: true } }] },
            { label: 'Modern DevOps', collapsed: true, items: [{ autogenerate: { directory: 'prerequisites/modern-devops', collapsed: true } }] },
          ],
        },
        {
          label: 'Linux',
          collapsed: true,
          items: [
            { label: 'Linux Hub', link: '/linux/' },
            {
              label: 'Foundations',
              collapsed: true,
              items: [
                { label: 'Everyday Use', collapsed: true, items: [{ autogenerate: { directory: 'linux/foundations/everyday-use', collapsed: true } }] },
                { label: 'System Essentials', collapsed: true, items: [{ autogenerate: { directory: 'linux/foundations/system-essentials', collapsed: true } }] },
                { label: 'Container Primitives', collapsed: true, items: [{ autogenerate: { directory: 'linux/foundations/container-primitives', collapsed: true } }] },
                { label: 'Networking', collapsed: true, items: [{ autogenerate: { directory: 'linux/foundations/networking', collapsed: true } }] },
              ],
            },
            {
              label: 'Operations',
              collapsed: true,
              items: [
                { label: 'Shell Scripting', collapsed: true, items: [{ autogenerate: { directory: 'linux/operations/shell-scripting', collapsed: true } }] },
                { label: 'Performance', collapsed: true, items: [{ autogenerate: { directory: 'linux/operations/performance', collapsed: true } }] },
                { label: 'Troubleshooting', collapsed: true, items: [{ autogenerate: { directory: 'linux/operations/troubleshooting', collapsed: true } }] },
              ],
            },
            {
              label: 'Security',
              collapsed: true,
              items: [
                { label: 'Hardening', collapsed: true, items: [{ autogenerate: { directory: 'linux/security/hardening', collapsed: true } }] },
              ],
            },
            { label: 'LFCS: Linux SysAdmin', collapsed: true, items: [{ autogenerate: { directory: 'k8s/lfcs', collapsed: true } }] },
          ],
        },
        {
          label: 'AI',
          collapsed: true,
          items: [
            { label: 'AI Hub', link: '/ai/' },
            { label: 'AI Foundations', collapsed: true, items: [{ autogenerate: { directory: 'ai/foundations', collapsed: true } }] },
            { label: 'AI Engineering Foundations', collapsed: true, items: [{ autogenerate: { directory: 'ai/ai-engineering-foundations', collapsed: true } }] },
            { label: 'AI-Native Work', collapsed: true, items: [{ autogenerate: { directory: 'ai/ai-native-work', collapsed: true } }] },
            { label: 'AI Building', collapsed: true, items: [{ autogenerate: { directory: 'ai/ai-building', collapsed: true } }] },
            { label: 'Open Models & Local Inference', collapsed: true, items: [{ autogenerate: { directory: 'ai/open-models-local-inference', collapsed: true } }] },
            { label: 'AI for Kubernetes & Platform Work', collapsed: true, items: [{ autogenerate: { directory: 'ai/ai-for-kubernetes-platform-work', collapsed: true } }] },
            { label: 'History of AI', collapsed: true, items: [
              { label: 'Overview', link: '/ai-history/' },
              {
                label: 'Part 1: Mathematical Foundations (1840s–1940s)',
                collapsed: true,
                items: [
                  { label: '01: The Laws of Thought', link: '/ai-history/ch-01-the-laws-of-thought/' },
                  { label: '02: The Universal Machine', link: '/ai-history/ch-02-the-universal-machine/' },
                  { label: '03: The Physical Bridge', link: '/ai-history/ch-03-the-physical-bridge/' },
                  { label: '04: The Statistical Roots', link: '/ai-history/ch-04-the-statistical-roots/' },
                  { label: '05: The Neural Abstraction', link: '/ai-history/ch-05-the-neural-abstraction/' },
                ],
              },
              {
                label: 'Part 2: Analog Dream & Digital Blank Slate (1940s–1950s)',
                collapsed: true,
                items: [
                  { label: '06: The Cybernetics Movement', link: '/ai-history/ch-06-the-cybernetics-movement/' },
                  { label: '07: The Analog Bottleneck', link: '/ai-history/ch-07-the-analog-bottleneck/' },
                  { label: '08: The Stored Program', link: '/ai-history/ch-08-the-stored-program/' },
                  { label: '09: The Memory Miracle', link: '/ai-history/ch-09-the-memory-miracle/' },
                  { label: '10: The Imitation Game', link: '/ai-history/ch-10-the-imitation-game/' },
                ],
              },
              {
                label: 'Part 3: Birth of Symbolic AI (1950s–1960s)',
                collapsed: true,
                items: [
                  { label: '11: The Summer AI Named Itself', link: '/ai-history/ch-11-the-summer-ai-named-itself/' },
                  { label: '12: The Logic Theorist and GPS', link: '/ai-history/ch-12-logic-theorist-gps/' },
                  { label: '13: The List Processor', link: '/ai-history/ch-13-the-list-processor/' },
                  { label: '14: The Perceptron', link: '/ai-history/ch-14-the-perceptron/' },
                  { label: '15: The Gradient Descent Concept', link: '/ai-history/ch-15-the-gradient-descent-concept/' },
                  { label: '16: The Cold War Blank Check', link: '/ai-history/ch-16-the-cold-war-blank-check/' },
                ],
              },
              {
                label: 'Part 4: First Winter & Shift to Knowledge (1970s–1980s)',
                collapsed: true,
                items: [
                  { label: "17: The Perceptron's Fall", link: '/ai-history/ch-17-the-perceptron-s-fall/' },
                  { label: '18: The Lighthill Devastation', link: '/ai-history/ch-18-the-lighthill-devastation/' },
                  { label: '19: Rules, Experts, and the Knowledge Bottleneck', link: '/ai-history/ch-19-rules-experts-and-the-knowledge-bottleneck/' },
                  { label: '20: Project MAC', link: '/ai-history/ch-20-project-mac/' },
                  { label: '21: The Rule-Based Fortune', link: '/ai-history/ch-21-the-rule-based-fortune/' },
                  { label: '22: The Lisp Machine Bubble', link: '/ai-history/ch-22-the-lisp-machine-bubble/' },
                  { label: '23: The Japanese Threat', link: '/ai-history/ch-23-the-japanese-threat/' },
                ],
              },
              {
                label: 'Part 5: Mathematical Resurrection (1980s–1990s)',
                collapsed: true,
                items: [
                  { label: '24: The Math That Waited for the Machine', link: '/ai-history/ch-24-the-math-that-waited-for-the-machine/' },
                  { label: '25: The Universal Approximation Theorem', link: '/ai-history/ch-25-the-universal-approximation-theorem-1989/' },
                  { label: '26: Bayesian Networks', link: '/ai-history/ch-26-bayesian-networks/' },
                  { label: '27: The Convolutional Breakthrough', link: '/ai-history/ch-27-the-convolutional-breakthrough/' },
                  { label: '28: The Second AI Winter', link: '/ai-history/ch-28-the-second-ai-winter/' },
                  { label: '29: Support Vector Machines', link: '/ai-history/ch-29-support-vector-machines/' },
                  { label: '30: The Statistical Underground', link: '/ai-history/ch-30-the-statistical-underground/' },
                  { label: '31: Reinforcement Learning Roots', link: '/ai-history/ch-31-reinforcement-learning-roots/' },
                ],
              },
              {
                label: 'Part 6: Rise of Data & Distributed Compute (1990s–2000s)',
                collapsed: true,
                items: [
                  { label: '32: The DARPA SUR Program', link: '/ai-history/ch-32-the-darpa-sur-program/' },
                  { label: '33: Deep Blue', link: '/ai-history/ch-33-deep-blue/' },
                  { label: '34: The Accidental Corpus', link: '/ai-history/ch-34-the-accidental-corpus/' },
                  { label: '35: Indexing the Mind', link: '/ai-history/ch-35-indexing-the-mind/' },
                  { label: '36: The Multicore Wall', link: '/ai-history/ch-36-the-multicore-wall/' },
                  { label: '37: Distributing the Compute', link: '/ai-history/ch-37-distributing-the-compute/' },
                  { label: '38: The Human API', link: '/ai-history/ch-38-the-human-api/' },
                  { label: '39: The Vision Wall', link: '/ai-history/ch-39-the-vision-wall/' },
                  { label: '40: Data Becomes Infrastructure', link: '/ai-history/ch-40-data-becomes-infrastructure/' },
                ],
              },
              {
                label: 'Part 7: Deep Learning Revolution & GPU Coup (2010s)',
                collapsed: true,
                items: [
                  { label: '41: The Graphics Hack', link: '/ai-history/ch-41-the-graphics-hack/' },
                  { label: '42: CUDA', link: '/ai-history/ch-42-cuda/' },
                  { label: '43: The ImageNet Smash', link: '/ai-history/ch-43-the-imagenet-smash/' },
                  { label: '44: The Latent Space', link: '/ai-history/ch-44-the-latent-space/' },
                  { label: '45: Generative Adversarial Networks', link: '/ai-history/ch-45-generative-adversarial-networks/' },
                  { label: '46: The Recurrent Bottleneck', link: '/ai-history/ch-46-the-recurrent-bottleneck/' },
                  { label: '47: The Depths of Vision', link: '/ai-history/ch-47-the-depths-of-vision/' },
                  { label: '48: AlphaGo', link: '/ai-history/ch-48-alphago/' },
                  { label: '49: The Custom Silicon', link: '/ai-history/ch-49-the-custom-silicon/' },
                ],
              },
              {
                label: 'Part 8: Transformer, Scale & Open Source (2017–2022)',
                collapsed: true,
                items: [
                  { label: '50: Attention Is All You Need', link: '/ai-history/ch-50-attention-is-all-you-need/' },
                  { label: '51: The Open Source Distribution Layer', link: '/ai-history/ch-51-the-open-source-distribution-layer/' },
                  { label: '52: Bidirectional Context', link: '/ai-history/ch-52-bidirectional-context/' },
                  { label: '53: The Dawn of Few-Shot Learning', link: '/ai-history/ch-53-the-dawn-of-few-shot-learning/' },
                  { label: '54: The Hub of Weights', link: '/ai-history/ch-54-the-hub-of-weights/' },
                  { label: '55: The Scaling Laws', link: '/ai-history/ch-55-the-scaling-laws/' },
                  { label: '56: The Megacluster', link: '/ai-history/ch-56-the-megacluster/' },
                  { label: '57: The Alignment Problem', link: '/ai-history/ch-57-the-alignment-problem/' },
                  { label: '58: The Math of Noise', link: '/ai-history/ch-58-the-math-of-noise/' },
                ],
              },
              {
                label: 'Part 9: Product Shock & Physical Limits (2022–present)',
                collapsed: true,
                items: [
                  { label: '59: The Product Shock', link: '/ai-history/ch-59-the-product-shock/' },
                  { label: '60: The Agent Turn', link: '/ai-history/ch-60-the-agent-turn/' },
                  { label: '61: The Physics of Scale', link: '/ai-history/ch-61-the-physics-of-scale/' },
                  { label: '62: Multimodal Convergence', link: '/ai-history/ch-62-multimodal-convergence/' },
                  { label: '63: Inference Economics', link: '/ai-history/ch-63-inference-economics/' },
                  { label: '64: The Edge Compute Bottleneck', link: '/ai-history/ch-64-the-edge-compute-bottleneck/' },
                  { label: '65: The Open Weights Rebellion', link: '/ai-history/ch-65-the-open-weights-rebellion/' },
                  { label: '66: Benchmark Wars', link: '/ai-history/ch-66-benchmark-wars/' },
                  { label: '67: The Monopoly', link: '/ai-history/ch-67-the-monopoly/' },
                  { label: '68: Data Labor and the Copyright Reckoning', link: '/ai-history/ch-68-data-labor-and-the-copyright-reckoning/' },
                  { label: '69: The Data Exhaustion Limit', link: '/ai-history/ch-69-the-data-exhaustion-limit/' },
                  { label: '70: The Energy Grid Collision', link: '/ai-history/ch-70-the-energy-grid-collision/' },
                  { label: '71: The Chip War', link: '/ai-history/ch-71-the-chip-war/' },
                  { label: '72: The Infinite Datacenter', link: '/ai-history/ch-72-the-infinite-datacenter/' },
                ],
              },
            ] },
          ],
        },

        // ── 2. Certifications: core K8s knowledge (before cloud-specific) ──

        {
          label: 'Certifications',
          collapsed: true,
          items: [
            { label: 'Certifications Hub', link: '/k8s/' },
            {
              label: 'Release Radar',
              collapsed: true,
              items: [{ autogenerate: { directory: 'k8s/releases', collapsed: true } }],
            },
            {
              label: 'Core Kubernetes',
              collapsed: true,
              items: [
                { label: 'KCNA: Cloud Native Associate', collapsed: true, items: [{ autogenerate: { directory: 'k8s/kcna', collapsed: true } }] },
                { label: 'KCSA: Security Associate', collapsed: true, items: [{ autogenerate: { directory: 'k8s/kcsa', collapsed: true } }] },
                { label: 'CKA: K8s Administrator', collapsed: true, items: [{ autogenerate: { directory: 'k8s/cka', collapsed: true } }] },
                { label: 'CKAD: App Developer', collapsed: true, items: [{ autogenerate: { directory: 'k8s/ckad', collapsed: true } }] },
                { label: 'CKS: Security Specialist', collapsed: true, items: [{ autogenerate: { directory: 'k8s/cks', collapsed: true } }] },
              ],
            },
            { label: 'Extending Kubernetes', collapsed: true, items: [{ autogenerate: { directory: 'k8s/extending', collapsed: true } }] },
            { label: 'Bridges to Other Tracks', collapsed: true, items: [{ autogenerate: { directory: 'k8s/bridges', collapsed: true } }] },
            {
              label: 'Ecosystem Certifications',
              collapsed: true,
              items: [
                { label: 'PCA: Prometheus', collapsed: true, items: [{ autogenerate: { directory: 'k8s/pca', collapsed: true } }] },
                { label: 'ICA: Istio', collapsed: true, items: [{ autogenerate: { directory: 'k8s/ica', collapsed: true } }] },
                { label: 'CCA: Cilium', collapsed: true, items: [{ autogenerate: { directory: 'k8s/cca', collapsed: true } }] },
                { label: 'CGOA: GitOps', collapsed: true, items: [{ autogenerate: { directory: 'k8s/cgoa', collapsed: true } }] },
                { label: 'CBA: Backstage', collapsed: true, items: [{ autogenerate: { directory: 'k8s/cba', collapsed: true } }] },
                { label: 'OTCA: OpenTelemetry', collapsed: true, items: [{ autogenerate: { directory: 'k8s/otca', collapsed: true } }] },
                { label: 'KCA: Kyverno', collapsed: true, items: [{ autogenerate: { directory: 'k8s/kca', collapsed: true } }] },
                { label: 'CAPA: Argo', collapsed: true, items: [{ autogenerate: { directory: 'k8s/capa', collapsed: true } }] },
                { label: 'CNPE: Platform Engineer', collapsed: true, items: [{ autogenerate: { directory: 'k8s/cnpe', collapsed: true } }] },
                { label: 'CNPA: Platform Associate', collapsed: true, items: [{ autogenerate: { directory: 'k8s/cnpa', collapsed: true } }] },
                { label: 'FinOps Practitioner', collapsed: true, items: [{ autogenerate: { directory: 'k8s/finops', collapsed: true } }] },
              ],
            },
          ],
        },

        // ── 3. Infrastructure: cloud + bare metal ──

        {
          label: 'Cloud',
          collapsed: true,
          items: [
            { label: 'Cloud Hub', link: '/cloud/' },
            { label: 'Rosetta Stone', link: '/cloud/hyperscaler-rosetta-stone/' },
            {
              label: 'AWS',
              collapsed: true,
              items: [
                { label: 'AWS Essentials', collapsed: true, items: [{ autogenerate: { directory: 'cloud/aws-essentials', collapsed: true } }] },
                { label: 'EKS Deep Dive', collapsed: true, items: [{ autogenerate: { directory: 'cloud/eks-deep-dive', collapsed: true } }] },
              ],
            },
            {
              label: 'Google Cloud',
              collapsed: true,
              items: [
                { label: 'GCP Essentials', collapsed: true, items: [{ autogenerate: { directory: 'cloud/gcp-essentials', collapsed: true } }] },
                { label: 'GKE Deep Dive', collapsed: true, items: [{ autogenerate: { directory: 'cloud/gke-deep-dive', collapsed: true } }] },
              ],
            },
            {
              label: 'Azure',
              collapsed: true,
              items: [
                { label: 'Azure Essentials', collapsed: true, items: [{ autogenerate: { directory: 'cloud/azure-essentials', collapsed: true } }] },
                { label: 'AKS Deep Dive', collapsed: true, items: [{ autogenerate: { directory: 'cloud/aks-deep-dive', collapsed: true } }] },
              ],
            },
            {
              label: 'Architecture & Enterprise',
              collapsed: true,
              items: [
                { label: 'Architecture Patterns', collapsed: true, items: [{ autogenerate: { directory: 'cloud/architecture-patterns', collapsed: true } }] },
                { label: 'Advanced Operations', collapsed: true, items: [{ autogenerate: { directory: 'cloud/advanced-operations', collapsed: true } }] },
                { label: 'Managed Services', collapsed: true, items: [{ autogenerate: { directory: 'cloud/managed-services', collapsed: true } }] },
                { label: 'Enterprise & Hybrid', collapsed: true, items: [{ autogenerate: { directory: 'cloud/enterprise-hybrid', collapsed: true } }] },
              ],
            },
          ],
        },
        {
          label: 'AI/ML Engineering',
          collapsed: true,
          items: [
            { label: 'AI/ML Hub', link: '/ai-ml-engineering/' },
            { label: 'Prerequisites', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/prerequisites', collapsed: true } }] },
            {
              label: 'Build AI Apps',
              collapsed: true,
              items: [
                { label: 'AI-Native Development', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/ai-native-development', collapsed: true } }] },
                { label: 'Generative AI', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/generative-ai', collapsed: true } }] },
                { label: 'Vector Search & RAG', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/vector-rag', collapsed: true } }] },
                { label: 'Frameworks & Agents', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/frameworks-agents', collapsed: true } }] },
                { label: 'Synthesis Apps', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/synthesis-apps', collapsed: true } }] },
              ],
            },
            {
              label: 'Model Foundations',
              collapsed: true,
              items: [
                {
                  // Deep Learning is the deepest section (27 modules); split into sub-chains
                  // via explicit links so the flat autogenerate list isn't a 27-item wall.
                  // Links only — no files moved, no URLs changed (issue #1810).
                  label: 'Deep Learning Foundations',
                  collapsed: true,
                  items: [
                    { label: 'Overview', link: '/ai-ml-engineering/deep-learning/' },
                    {
                      label: 'From-Scratch Foundations (NumPy)',
                      collapsed: true,
                      items: [
                        { label: '1.1 · NumPy, Pandas & Data Tooling', link: '/ai-ml-engineering/deep-learning/module-1.1-numpy-pandas-data-tooling/' },
                        { label: '1.1.1 · Neural Network Math Warm-Up', link: '/ai-ml-engineering/deep-learning/module-1.1.1-nn-math-warmup/' },
                        { label: '1.1.2 · The Neuron & Perceptron from Scratch', link: '/ai-ml-engineering/deep-learning/module-1.1.2-neuron-from-scratch/' },
                        { label: '1.1.3 · Forward Propagation in MLPs', link: '/ai-ml-engineering/deep-learning/module-1.1.3-forward-propagation-mlp/' },
                        { label: '1.1.4 · Activation Functions in Depth', link: '/ai-ml-engineering/deep-learning/module-1.1.4-activation-functions/' },
                        { label: '1.1.5 · Loss Functions & Output Heads', link: '/ai-ml-engineering/deep-learning/module-1.1.5-loss-functions-output-heads/' },
                        { label: '1.1.6 · Backprop by Hand for Dense Nets', link: '/ai-ml-engineering/deep-learning/module-1.1.6-backprop-by-hand-dense-nets/' },
                        { label: '1.1.7 · Tiny NumPy NN Lab', link: '/ai-ml-engineering/deep-learning/module-1.1.7-tiny-numpy-nn-lab/' },
                        { label: '1.1.8 · Computational Graphs & Scalar Autograd', link: '/ai-ml-engineering/deep-learning/module-1.1.8-computational-graphs-scalar-autograd/' },
                      ],
                    },
                    {
                      label: 'PyTorch & the Training Loop',
                      collapsed: true,
                      items: [
                        { label: '1.2 · The PyTorch Bridge', link: '/ai-ml-engineering/deep-learning/module-1.2-pytorch-fundamentals/' },
                        { label: '1.3 · The Training Loop', link: '/ai-ml-engineering/deep-learning/module-1.3-training-neural-networks/' },
                        { label: '1.3.1 · Initialization & Signal Propagation', link: '/ai-ml-engineering/deep-learning/module-1.3.1-initialization-signal-propagation/' },
                        { label: '1.3.2 · Optimizers & LR Dynamics', link: '/ai-ml-engineering/deep-learning/module-1.3.2-optimizers-lr-dynamics/' },
                        { label: '1.3.3 · Regularization & Generalization', link: '/ai-ml-engineering/deep-learning/module-1.3.3-regularization-generalization/' },
                        { label: '1.3.4 · Normalization Layers', link: '/ai-ml-engineering/deep-learning/module-1.3.4-normalization-layers/' },
                        { label: '1.3.5 · Training-Diagnostics Playbook', link: '/ai-ml-engineering/deep-learning/module-1.3.5-training-diagnostics-playbook/' },
                        { label: '1.3.6 · Numerical Stability & Precision', link: '/ai-ml-engineering/deep-learning/module-1.3.6-numerical-stability-precision/' },
                      ],
                    },
                    {
                      label: 'Representations, Attention & Transformers',
                      collapsed: true,
                      items: [
                        { label: '1.4.1 · Embeddings & Representation Learning', link: '/ai-ml-engineering/deep-learning/module-1.4.1-embeddings-representation-learning/' },
                        { label: '1.4.2 · Residual Connections & Deep Architectures', link: '/ai-ml-engineering/deep-learning/module-1.4.2-residual-deep-architectures/' },
                        { label: '1.4.3 · Attention from Scratch', link: '/ai-ml-engineering/deep-learning/module-1.4.3-attention-from-scratch/' },
                        { label: '1.4.4 · The Transformer Block from Scratch', link: '/ai-ml-engineering/deep-learning/module-1.4.4-transformer-block-from-scratch/' },
                      ],
                    },
                    {
                      label: 'Architectures & Capstone',
                      collapsed: true,
                      items: [
                        { label: '1.5 · CNNs & Computer Vision', link: '/ai-ml-engineering/deep-learning/module-1.5-cnns-computer-vision/' },
                        { label: '1.6 · Recurrent Networks & Sequence Models', link: '/ai-ml-engineering/deep-learning/module-1.6-rnns-sequence-models/' },
                        { label: '1.7 · Capstone: Train a Real Net End-to-End', link: '/ai-ml-engineering/deep-learning/module-1.7-capstone-train-a-real-net/' },
                      ],
                    },
                    {
                      label: 'Advanced Topics',
                      collapsed: true,
                      items: [
                        { label: '1.8 · Self-Supervised Learning', link: '/ai-ml-engineering/deep-learning/module-1.8-self-supervised-learning/' },
                        { label: '1.9 · Graph Neural Networks', link: '/ai-ml-engineering/deep-learning/module-1.9-graph-neural-networks/' },
                        { label: '1.10 · Modern Transformers: RoPE & Attention Variants', link: '/ai-ml-engineering/deep-learning/module-1.10-modern-transformers-rope-and-attention/' },
                      ],
                    },
                  ],
                },
                { label: 'Machine Learning', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/machine-learning', collapsed: true } }] },
                { label: 'Reinforcement Learning', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/reinforcement-learning', collapsed: true } }] },
              ],
            },
            {
              label: 'Operate & Scale',
              collapsed: true,
              items: [
                { label: 'MLOps & LLMOps', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/mlops', collapsed: true } }] },
                { label: 'AI Infrastructure', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/ai-infrastructure', collapsed: true } }] },
                { label: 'Advanced GenAI & Safety', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/advanced-genai', collapsed: true } }] },
                { label: 'Multimodal AI', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/multimodal-ai', collapsed: true } }] },
              ],
            },
            {
              label: 'Reference',
              collapsed: true,
              items: [
                { label: 'Bridges to Other Tracks', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/bridges', collapsed: true } }] },
                { label: 'Appendix A: History of AI/ML', collapsed: true, items: [{ autogenerate: { directory: 'ai-ml-engineering/history', collapsed: true } }] },
              ],
            },
          ],
        },
        {
          label: 'On-Premises',
          collapsed: true,
          items: [
            { label: 'On-Premises Hub', link: '/on-premises/' },
            { label: 'Planning & Economics', collapsed: true, items: [{ autogenerate: { directory: 'on-premises/planning', collapsed: true } }] },
            { label: 'Bare Metal Provisioning', collapsed: true, items: [{ autogenerate: { directory: 'on-premises/provisioning', collapsed: true } }] },
            { label: 'Networking', collapsed: true, items: [{ autogenerate: { directory: 'on-premises/networking', collapsed: true } }] },
            { label: 'Storage', collapsed: true, items: [{ autogenerate: { directory: 'on-premises/storage', collapsed: true } }] },
            { label: 'Multi-Cluster', collapsed: true, items: [{ autogenerate: { directory: 'on-premises/multi-cluster', collapsed: true } }] },
            { label: 'Security & Compliance', collapsed: true, items: [{ autogenerate: { directory: 'on-premises/security', collapsed: true } }] },
            { label: 'Day-2 Operations', collapsed: true, items: [{ autogenerate: { directory: 'on-premises/operations', collapsed: true } }] },
            { label: 'Resilience & Migration', collapsed: true, items: [{ autogenerate: { directory: 'on-premises/resilience', collapsed: true } }] },
            { label: 'AI/ML Infrastructure', collapsed: true, items: [{ autogenerate: { directory: 'on-premises/ai-ml-infrastructure', collapsed: true } }] },
          ],
        },

        // ── 4. Advanced: practices + tools ──

        {
          label: 'Platform Engineering',
          collapsed: true,
          items: [
            { label: 'Platform Hub', link: '/platform/' },

            // ── Foundations (timeless theory) ──
            {
              label: 'Foundations',
              collapsed: true,
              items: [{ autogenerate: { directory: 'platform/foundations', collapsed: true } }],
            },

            // ── Disciplines (applied practices) ──
            {
              label: 'Disciplines',
              collapsed: true,
              items: [
                {
                  label: 'Core Platform',
                  collapsed: true,
                  items: [
                    { label: 'SRE', collapsed: true, items: [{ autogenerate: { directory: 'platform/disciplines/core-platform/sre', collapsed: true } }] },
                    { label: 'Platform Engineering', collapsed: true, items: [{ autogenerate: { directory: 'platform/disciplines/core-platform/platform-engineering', collapsed: true } }] },
                    { label: 'Platform Leadership', collapsed: true, items: [{ autogenerate: { directory: 'platform/disciplines/core-platform/leadership', collapsed: true } }] },
                  ],
                },
                {
                  label: 'Delivery & Automation',
                  collapsed: true,
                  items: [
                    { label: 'Release Engineering', collapsed: true, items: [{ autogenerate: { directory: 'platform/disciplines/delivery-automation/release-engineering', collapsed: true } }] },
                    { label: 'GitOps', collapsed: true, items: [{ autogenerate: { directory: 'platform/disciplines/delivery-automation/gitops', collapsed: true } }] },
                    { label: 'Infrastructure as Code', collapsed: true, items: [{ autogenerate: { directory: 'platform/disciplines/delivery-automation/iac', collapsed: true } }] },
                  ],
                },
                {
                  label: 'Reliability & Security',
                  collapsed: true,
                  items: [
                    { label: 'Networking', collapsed: true, items: [{ autogenerate: { directory: 'platform/disciplines/reliability-security/networking', collapsed: true } }] },
                    { label: 'Chaos Engineering', collapsed: true, items: [{ autogenerate: { directory: 'platform/disciplines/reliability-security/chaos-engineering', collapsed: true } }] },
                    { label: 'DevSecOps', collapsed: true, items: [{ autogenerate: { directory: 'platform/disciplines/reliability-security/devsecops', collapsed: true } }] },
                  ],
                },
                {
                  label: 'Data & AI',
                  collapsed: true,
                  items: [
                    {
                      label: 'Data Engineering',
                      collapsed: true,
                      items: [
                        { label: 'Overview', link: '/platform/disciplines/data-ai/data-engineering/' },
                        { label: '1.1: Stateful Workloads & Storage', link: '/platform/disciplines/data-ai/data-engineering/module-1.1-stateful-workloads/' },
                        { label: '1.2: Apache Kafka on K8s', link: '/platform/disciplines/data-ai/data-engineering/module-1.2-kafka/' },
                        { label: '1.3: Stream Processing with Flink', link: '/platform/disciplines/data-ai/data-engineering/module-1.3-flink/' },
                        { label: '1.4: Batch Processing with Spark', link: '/platform/disciplines/data-ai/data-engineering/module-1.4-spark/' },
                        { label: '1.5: Data Orchestration with Airflow', link: '/platform/disciplines/data-ai/data-engineering/module-1.5-airflow/' },
                        { label: '1.6: Building a Data Lakehouse', link: '/platform/disciplines/data-ai/data-engineering/module-1.6-lakehouse/' },
                        { label: '1.7: Event Streaming Fundamentals', link: '/platform/disciplines/data-ai/data-engineering/module-1.7-event-streaming-fundamentals/' },
                        { label: '1.8: CloudEvents & Event-Driven Architecture', link: '/platform/disciplines/data-ai/data-engineering/module-1.8-cloudevents-event-driven-arch/' },
                        { label: '1.9: NATS JetStream on Kubernetes', link: '/platform/disciplines/data-ai/data-engineering/module-1.9-nats-jetstream/' },
                      ],
                    },
                    { label: 'MLOps', collapsed: true, items: [{ autogenerate: { directory: 'platform/disciplines/data-ai/mlops', collapsed: true } }] },
                    { label: 'AIOps', collapsed: true, items: [{ autogenerate: { directory: 'platform/disciplines/data-ai/aiops', collapsed: true } }] },
                    { label: 'AI Infrastructure', collapsed: true, items: [{ autogenerate: { directory: 'platform/disciplines/data-ai/ai-infrastructure', collapsed: true } }] },
                  ],
                },
                { label: 'FinOps', collapsed: true, items: [{ autogenerate: { directory: 'platform/disciplines/business-value/finops', collapsed: true } }] },
              ],
            },

            // ── Toolkits (current tools) ──
            {
              label: 'Toolkits',
              collapsed: true,
              items: [
                { label: 'Toolkit Directory', link: '/platform/toolkits/' },
                {
                  label: 'CI/CD & Delivery',
                  collapsed: true,
                  items: [
                    { label: 'CI/CD Pipelines', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/cicd-delivery/ci-cd-pipelines', collapsed: true } }] },
                    { label: 'GitOps & Deployments', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/cicd-delivery/gitops-deployments', collapsed: true } }] },
                    { label: 'Source Control', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/cicd-delivery/source-control', collapsed: true } }] },
                    { label: 'Container Registries', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/cicd-delivery/container-registries', collapsed: true } }] },
                  ],
                },
                {
                  label: 'Observability',
                  collapsed: true,
                  items: [
                    { label: 'Observability Stack', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/observability-intelligence/observability', collapsed: true } }] },
                    { label: 'AIOps Tools', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/observability-intelligence/aiops-tools', collapsed: true } }] },
                  ],
                },
                {
                  label: 'Infrastructure',
                  collapsed: true,
                  items: [
                    { label: 'IaC Tools', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/infrastructure-networking/iac-tools', collapsed: true } }] },
                    { label: 'K8s Distributions', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/infrastructure-networking/k8s-distributions', collapsed: true } }] },
                    { label: 'Networking Tools', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/infrastructure-networking/networking', collapsed: true } }] },
                    { label: 'Platforms', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/infrastructure-networking/platforms', collapsed: true } }] },
                    { label: 'Storage', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/infrastructure-networking/storage', collapsed: true } }] },
                  ],
                },
                {
                  label: 'Security & Quality',
                  collapsed: true,
                  items: [
                    { label: 'Security Tools', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/security-quality/security-tools', collapsed: true } }] },
                    { label: 'Code Quality', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/security-quality/code-quality', collapsed: true } }] },
                  ],
                },
                {
                  label: 'Developer Experience',
                  collapsed: true,
                  items: [
                    { label: 'DevEx Tools', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/developer-experience/devex-tools', collapsed: true } }] },
                    { label: 'Scaling & Reliability', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/developer-experience/scaling-reliability', collapsed: true } }] },
                  ],
                },
                {
                  label: 'Data & AI Platforms',
                  collapsed: true,
                  items: [
                    { label: 'ML Platforms', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/data-ai-platforms/ml-platforms', collapsed: true } }] },
                    { label: 'Cloud-Native Databases', collapsed: true, items: [{ autogenerate: { directory: 'platform/toolkits/data-ai-platforms/cloud-native-databases', collapsed: true } }] },
                  ],
                },
              ],
            },
          ],
        },

        // ── Utility ──

        { label: "What's New", link: '/changelog/' },
        { label: 'Glossary', link: '/glossary/' },
      ],
    }),
    routeManifestIntegration(),
    progressIntegration(),
  ],
});
