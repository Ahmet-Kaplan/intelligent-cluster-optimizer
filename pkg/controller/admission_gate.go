package controller

import (
	"time"

	optimizerv1alpha1 "intelligent-cluster-optimizer/pkg/apis/optimizer/v1alpha1"
	"intelligent-cluster-optimizer/pkg/conformal"
	"intelligent-cluster-optimizer/pkg/storage"
)

// memoryRiskBudget returns the configured eps_c for memory requests; 0 disables the conformal admission gate.
func memoryRiskBudget(config *optimizerv1alpha1.OptimizerConfig) float64 {
	if config.Spec.Recommendations == nil {
		return 0
	}
	return config.Spec.Recommendations.MemoryRiskBudget
}

// workloadContainerPeak returns the realized next-horizon target of the gate: the peak memory of one
// container across all pods of a workload, since every replica shares the container's request.
func workloadContainerPeak(store *storage.InMemoryStorage, namespace, workload, container string) conformal.PeakFunc {
	return func(from, to time.Time) (float64, bool) {
		peak, ok := 0.0, false
		for _, pm := range store.GetMetricsByWorkload(namespace, workload, time.Since(from)) {
			if pm.Timestamp.Before(from) || !pm.Timestamp.Before(to) {
				continue
			}
			for _, c := range pm.Containers {
				if c.ContainerName == container && (!ok || float64(c.UsageMemory) > peak) {
					peak, ok = float64(c.UsageMemory), true
				}
			}
		}
		return peak, ok
	}
}
