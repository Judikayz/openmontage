import type { JobInput, Provider } from './types';
export function routeJob(job: JobInput): Provider {
  if (job.compute === 'github') return 'github';
  if (job.compute === 'kaggle') { if (!job.requiresGpu) throw new Error('Kaggle is reserved for GPU production tasks; this job does not require GPU'); return 'kaggle'; }
  if (job.compute && job.compute !== 'automatic') throw new Error('Unsupported compute mode');
  return job.requiresGpu ? 'kaggle' : 'github';
}

export const TOOL_BRANCHES = ['ai-video-generation','character-consistency','lip-sync','cinematic-realism','openmontage-integration','narrated-demo'] as const;
// Credentials a GitHub runner may read (over the authenticated callback token). Nothing else is ever exposed.
export const WORKER_READABLE_CREDENTIALS = ['gemini'];
export function validateToolBranch(tool: string): string {
  if (!TOOL_BRANCHES.includes(tool as typeof TOOL_BRANCHES[number])) throw new Error(`Unsupported tool branch: ${tool}`);
  return tool;
}

// Only tools whose workers were exercised against real video are enabled by default.
// The rest need a GPU, model weights or checkpoints and have NOT been tested end to end.
export const VERIFIED_TOOLS = ['cinematic-realism','openmontage-integration','narrated-demo'] as const;
export function assertToolEnabled(tool: string, experimental: boolean, compute?: string): void {
  if (experimental) return;
  if (!VERIFIED_TOOLS.includes(tool as typeof VERIFIED_TOOLS[number])) throw new Error(`${tool} is experimental and untested, so it is disabled. Set EXPERIMENTAL_TOOLS=true on the Worker to enable it at your own risk.`);
  if (compute === 'kaggle') throw new Error('Kaggle GPU execution is untested and disabled. Set EXPERIMENTAL_TOOLS=true to enable it.');
}
