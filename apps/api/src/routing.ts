import type { JobInput, Provider } from './types';
export function routeJob(job: JobInput): Provider {
  if (job.compute === 'github') return 'github';
  if (job.compute === 'kaggle') { if (!job.requiresGpu) throw new Error('Kaggle is reserved for GPU production tasks; this job does not require GPU'); return 'kaggle'; }
  if (job.compute && job.compute !== 'automatic') throw new Error('Unsupported compute mode');
  return job.requiresGpu ? 'kaggle' : 'github';
}

export const TOOL_BRANCHES = ['ai-video-generation','character-consistency','lip-sync','cinematic-realism','openmontage-integration'] as const;
export function validateToolBranch(tool: string): string {
  if (!TOOL_BRANCHES.includes(tool as typeof TOOL_BRANCHES[number])) throw new Error(`Unsupported tool branch: ${tool}`);
  return tool;
}
