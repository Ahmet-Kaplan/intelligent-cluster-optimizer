package controller

import (
	"testing"
	"time"

	optimizerv1alpha1 "intelligent-cluster-optimizer/pkg/apis/optimizer/v1alpha1"
	"intelligent-cluster-optimizer/pkg/conformal"
	"intelligent-cluster-optimizer/pkg/storage"
)

func TestWorkloadContainerPeakTakesMaxAcrossPods(t *testing.T) {
	store := storage.NewStorage()
	low := func(int) int64 { return 100 * mib }
	high := func(i int) int64 { return 150*mib + int64(i)*mib }
	for _, pm := range append(podSeries("web-0", 3*time.Hour, map[string]func(int) int64{"app": low, "sidecar": high}),
		podSeries("web-1", 3*time.Hour, map[string]func(int) int64{"app": high})...) {
		store.Add(pm)
	}
	peak := workloadContainerPeak(store, "default", "web", "app")

	from := time.Now().Add(-3 * time.Hour).Add(-time.Minute) // includes sample 0
	got, ok := peak(from, from.Add(time.Hour))               // samples 0..11 of web-1 "app" (12 is at from + 61 min)
	if !ok || got != float64(161*mib) {
		t.Fatalf("peak = %v, %v; want %d", got, ok, 161*mib)
	}
	if _, ok := peak(time.Now().Add(time.Hour), time.Now().Add(2*time.Hour)); ok {
		t.Fatal("expected no samples in a future window")
	}
	if _, ok := workloadContainerPeak(store, "default", "web", "missing")(from, time.Now()); ok {
		t.Fatal("expected no samples for an unknown container")
	}
}

func TestMemoryRiskBudget(t *testing.T) {
	c := &optimizerv1alpha1.OptimizerConfig{}
	if memoryRiskBudget(c) != 0 {
		t.Fatal("gate must be off without a recommendations block")
	}
	c.Spec.Recommendations = &optimizerv1alpha1.RecommendationConfig{MemoryRiskBudget: 0.05}
	if memoryRiskBudget(c) != 0.05 {
		t.Fatal("budget not read from the spec")
	}
}

// The gate over real storage: the first decision is a cold start, the second raises a candidate
// that the first horizon's realized peak exceeded.
func TestAdmissionGateRaisesUnderSizedCandidate(t *testing.T) {
	store := storage.NewStorage()
	for _, pm := range podSeries("web-0", 3*time.Hour, map[string]func(int) int64{"app": func(int) int64 { return 200 * mib }}) {
		store.Add(pm)
	}
	cfg := conformal.DefaultConfig(0.5) // MinCalibration(0.5) = 1 score
	peak := workloadContainerPeak(store, "default", "web", "app")
	gate := conformal.NewGate()
	t0 := time.Now().Add(-3 * time.Hour)
	candidate := float64(100 * mib)

	if _, v := conformal.Admit(candidate, candidate, gate.Bound(cfg, "k", t0, candidate, peak)); v != conformal.NeedsApproval {
		t.Fatalf("first decision verdict %v; want NeedsApproval", v)
	}
	req, v := conformal.Admit(candidate, candidate, gate.Bound(cfg, "k", t0.Add(time.Hour), candidate, peak))
	if v != conformal.Raised || req != float64(200*mib) {
		t.Fatalf("second decision = (%v, %v); want (%d, Raised)", req, v, 200*mib)
	}
}
