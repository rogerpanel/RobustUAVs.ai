import { request } from './client';

/** Evaluation surface: robustness, ablations, ROC, statistics, calibration. */
export const evalApi = {
  robustness: () => request('/api/eval/robustness'),
  ablations: () => request('/api/eval/ablations'),
  roc: () => request('/api/eval/roc'),
  statistics: () => request('/api/eval/statistics'),
  calibration: () => request('/api/eval/calibration'),
  federated: () => request('/api/eval/federated'),
};
