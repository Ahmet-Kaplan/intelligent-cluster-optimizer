package controller

import (
	"testing"
	"time"

	"intelligent-cluster-optimizer/pkg/leakdetector"
	"intelligent-cluster-optimizer/pkg/models"
)

const mib = int64(1024 * 1024)

// podSeries builds one pod's samples every 5 minutes over span, with memory(i) per container.
func podSeries(pod string, span time.Duration, mem map[string]func(i int) int64) []models.PodMetric {
	start := time.Now().Add(-span)
	var out []models.PodMetric
	for i := 0; time.Duration(i)*5*time.Minute <= span; i++ {
		pm := models.PodMetric{PodName: pod, Namespace: "default", Timestamp: start.Add(time.Duration(i) * 5 * time.Minute)}
		for name, f := range mem {
			pm.Containers = append(pm.Containers, models.ContainerMetric{ContainerName: name, UsageMemory: f(i)})
		}
		out = append(out, pm)
	}
	return out
}

func leaking(i int) int64 { return 200*mib + int64(i)*5*mib } // +60 MiB/h, steady
func flat(i int) int64    { return 200*mib + int64(i%3)*mib } // noise around 200 MiB

func TestDetectWorkloadLeakFindsLeakingContainer(t *testing.T) {
	metrics := podSeries("web-0", 4*time.Hour, map[string]func(int) int64{"app": flat, "sidecar": leaking})
	v := detectWorkloadLeak(leakdetector.NewDetector(), metrics)
	if v == nil || v.Pod != "web-0" || v.Container != "sidecar" || !v.Analysis.IsLeak {
		t.Fatalf("expected leak in web-0/sidecar, got %+v", v)
	}
}

func TestDetectWorkloadLeakIgnoresHealthyMemory(t *testing.T) {
	metrics := podSeries("web-0", 4*time.Hour, map[string]func(int) int64{"app": flat})
	if v := detectWorkloadLeak(leakdetector.NewDetector(), metrics); v != nil {
		t.Fatalf("expected no leak, got %+v", v)
	}
}

func TestDetectWorkloadLeakNeedsMoreThanMinDuration(t *testing.T) {
	// 55 minutes of a clear leak is below the detector's 1 h MinDuration: no verdict.
	metrics := podSeries("web-0", 55*time.Minute, map[string]func(int) int64{"app": leaking})
	if v := detectWorkloadLeak(leakdetector.NewDetector(), metrics); v != nil {
		t.Fatalf("expected no verdict below MinDuration, got %+v", v)
	}
}

func TestLeakWindowExceedsDetectorMinDuration(t *testing.T) {
	if leakWindow <= leakdetector.NewDetector().MinDuration {
		t.Fatalf("leakWindow %v must exceed MinDuration %v", leakWindow, leakdetector.NewDetector().MinDuration)
	}
}

func TestDetectWorkloadLeakSeparatesPods(t *testing.T) {
	metrics := append(podSeries("web-0", 4*time.Hour, map[string]func(int) int64{"app": flat}),
		podSeries("web-1", 4*time.Hour, map[string]func(int) int64{"app": leaking})...)
	v := detectWorkloadLeak(leakdetector.NewDetector(), metrics)
	if v == nil || v.Pod != "web-1" {
		t.Fatalf("expected leak in web-1, got %+v", v)
	}
}
