package controller

import (
	"sort"
	"time"

	"intelligent-cluster-optimizer/pkg/leakdetector"
	"intelligent-cluster-optimizer/pkg/models"
)

// leakWindow is the memory history the leak gate inspects. It must exceed the detector's
// MinDuration (1 h, measured first-to-last sample); a 1 h window never yields a verdict.
const leakWindow = 6 * time.Hour

// leakVerdict identifies the container whose memory trend was classified as a leak.
type leakVerdict struct {
	Pod       string
	Container string
	Analysis  *leakdetector.LeakAnalysis
}

// detectWorkloadLeak runs the leak detector on every (pod, container) memory series of a workload
// and returns the first leaking one in a deterministic order, or nil when none leaks.
func detectWorkloadLeak(detector *leakdetector.Detector, metrics []models.PodMetric) *leakVerdict {
	type key struct{ pod, container string }
	series := make(map[key][]leakdetector.MemorySample)
	for _, pm := range metrics {
		for _, c := range pm.Containers {
			k := key{pm.PodName, c.ContainerName}
			series[k] = append(series[k], leakdetector.MemorySample{Timestamp: pm.Timestamp, Bytes: c.UsageMemory})
		}
	}
	keys := make([]key, 0, len(series))
	for k := range series {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		if keys[i].pod != keys[j].pod {
			return keys[i].pod < keys[j].pod
		}
		return keys[i].container < keys[j].container
	})
	for _, k := range keys {
		if analysis := detector.Analyze(series[k]); analysis.IsLeak {
			return &leakVerdict{Pod: k.pod, Container: k.container, Analysis: analysis}
		}
	}
	return nil
}
