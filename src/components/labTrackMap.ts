/**
 * Index-page Killercoda lab progress denominators.
 * Totals count frontmatter `lab.id` values, not curriculum modules.
 */
export interface LabTrack {
  prefix: string;
  total: number;
}

export const labTrackMap: Record<string, LabTrack> = {
  'prerequisites/zero-to-terminal': { prefix: 'prereq-0.', total: 5 },
  // EN audit 2026-09-15: five prereq-k8s-* labs (modules 1.1–1.5). 1.6–1.8 have none.
  'prerequisites/kubernetes-basics': { prefix: 'prereq-k8s-', total: 5 },
  'linux/foundations/everyday-use': { prefix: 'linux-0.', total: 5 },
  'linux/foundations/system-essentials': { prefix: 'linux-1.', total: 4 },
  'linux/foundations/networking': { prefix: 'linux-3.', total: 4 },
  'k8s/cka/part0-environment': { prefix: 'cka-0.', total: 5 },
  'k8s/cka/part1-cluster-architecture': { prefix: 'cka-1.', total: 7 },
  'k8s/cka/part2-workloads-scheduling': { prefix: 'cka-2.', total: 9 },
  'k8s/cka/part3-services-networking': { prefix: 'cka-3.', total: 8 },
  'k8s/cka/part4-storage': { prefix: 'cka-4.', total: 5 },
  'k8s/cka/part5-troubleshooting': { prefix: 'cka-5.', total: 7 },
  'k8s/ckad/part0-environment': { prefix: 'ckad-0.', total: 2 },
  'k8s/ckad/part1-design-build': { prefix: 'ckad-1.', total: 4 },
  'k8s/ckad/part2-deployment': { prefix: 'ckad-2.', total: 4 },
  'k8s/ckad/part3-observability': { prefix: 'ckad-3.', total: 5 },
  'k8s/ckad/part4-environment': { prefix: 'ckad-4.', total: 6 },
  'k8s/ckad/part5-networking': { prefix: 'ckad-5.', total: 3 },
  'k8s/cks/part0-environment': { prefix: 'cks-0.', total: 4 },
  'k8s/cks/part1-cluster-setup': { prefix: 'cks-1.', total: 5 },
  'k8s/cks/part2-cluster-hardening': { prefix: 'cks-2.', total: 5 },
  'k8s/cks/part3-system-hardening': { prefix: 'cks-3.', total: 4 },
  'k8s/cks/part4-microservice-vulnerabilities': { prefix: 'cks-4.', total: 4 },
  'k8s/cks/part5-supply-chain-security': { prefix: 'cks-5.', total: 4 },
  'k8s/cks/part6-runtime-security': { prefix: 'cks-6.', total: 4 },
  'linux/security/hardening': { prefix: 'linux-4.', total: 4 },
  'linux/operations/performance': { prefix: 'linux-5.', total: 4 },
  'linux/operations/troubleshooting': { prefix: 'linux-6.', total: 4 },
  'linux/operations/shell-scripting': { prefix: 'linux-7.', total: 4 },
  'linux/operations': { prefix: 'linux-8.', total: 4 },
};
