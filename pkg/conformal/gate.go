// Package conformal implements the conformal admission gate (paper Section IV, Eqs. cqr, admit, aci):
// a per-container calibrated upper bound on the peak memory of the next horizon, with adaptive
// conformal inference (ACI) so the long-run rate of peaks above the bound tracks the risk budget.
//
// It is a port of experiments/conformal_gate/src/cgate/conformal.py (aci_bounds, gate_requests in
// "modify" mode). Each decision sizes [t, t+Horizon); its outcome is scored once the horizon has
// elapsed, so the feedback delay is one decision, as in the offline evaluation.
package conformal

import (
	"math"
	"sort"
	"sync"
	"time"
)

// Config holds the gate parameters. Eps is the risk budget eps_c; Eta = 0 gives static split conformal.
type Config struct {
	Eps     float64
	Eta     float64
	Window  int           // calibration scores kept
	Horizon time.Duration // decision horizon H; at most one open decision per container
}

// DefaultConfig returns the parameters of the offline evaluation (hourly decisions, 7 days of scores).
// Below eps = 0.05 calibration is static: in the trace replay ACI exceeded eps = 0.01 for all envelopes but Holt-Winters
// (too few calibrated decisions for its long-run correction), while static calibration stayed within it.
func DefaultConfig(eps float64) Config {
	eta := 0.005
	if eps < 0.05 {
		eta = 0
	}
	return Config{Eps: eps, Eta: eta, Window: 168, Horizon: time.Hour}
}

// MinCalibration is the smallest number of scores for which the (1 - eps) conformal quantile is finite.
func MinCalibration(eps float64) int {
	return int(math.Ceil(1/eps)) - 1
}

// PeakFunc returns the maximum usage observed in [from, to), or ok = false when there are no samples.
type PeakFunc func(from, to time.Time) (peak float64, ok bool)

type decision struct {
	at           time.Time
	upper, bound float64
}

type state struct {
	eps    float64
	alpha  float64
	scores []float64
	open   *decision
}

// Gate keeps calibration state per container key. It is safe for concurrent use.
type Gate struct {
	mu     sync.Mutex
	states map[string]*state
}

// NewGate returns a gate with no calibration history.
func NewGate() *Gate {
	return &Gate{states: make(map[string]*state)}
}

// Bound returns the calibrated upper bound U_hat = upper + Q_{1-alpha}(scores) for the decision at now,
// where upper is the envelope being calibrated (any upper forecast of the next-horizon peak).
// NaN = cold start (no verdict); +Inf = no request can be certified; -Inf = any request is admitted.
// While the current decision's horizon is still open, the bound of that decision is returned unchanged.
func (g *Gate) Bound(cfg Config, key string, now time.Time, upper float64, peak PeakFunc) float64 {
	g.mu.Lock()
	defer g.mu.Unlock()
	st := g.states[key]
	if st == nil || st.eps != cfg.Eps { // a new budget restarts calibration
		st = &state{eps: cfg.Eps, alpha: cfg.Eps}
		g.states[key] = st
	}
	if d := st.open; d != nil {
		if now.Before(d.at.Add(cfg.Horizon)) {
			return d.bound
		}
		st.open = nil
		if y, ok := peak(d.at, d.at.Add(cfg.Horizon)); ok && !math.IsNaN(d.upper) {
			if !math.IsNaN(d.bound) { // any verdict incl. +/-Inf -> ACI step
				miss := 0.0
				if y > d.bound {
					miss = 1
				}
				st.alpha += cfg.Eta * (cfg.Eps - miss)
			}
			st.scores = append(st.scores, y-d.upper)
			if len(st.scores) > cfg.Window {
				st.scores = st.scores[len(st.scores)-cfg.Window:]
			}
		}
	}
	b := quantileBound(st, cfg.Eps, upper)
	st.open = &decision{at: now, upper: upper, bound: b}
	return b
}

func quantileBound(st *state, eps, upper float64) float64 {
	n := len(st.scores)
	if n < MinCalibration(eps) || math.IsNaN(upper) || math.IsInf(upper, 0) {
		return math.NaN()
	}
	if st.alpha >= 1 {
		return math.Inf(-1)
	}
	rank := n + 1
	if st.alpha > 0 {
		rank = int(math.Ceil(float64(n+1) * (1 - st.alpha)))
	}
	if rank > n {
		return math.Inf(1)
	}
	s := append([]float64(nil), st.scores...)
	sort.Float64s(s)
	return upper + s[rank-1]
}

// Verdict is the outcome of the admission rule for one candidate request.
type Verdict int

const (
	Admitted      Verdict = iota // candidate >= bound (or bound = -Inf)
	Raised                       // candidate below a finite bound, raised to it
	Held                         // bound = +Inf: no scale-down below the previous request
	NeedsApproval                // cold start: no verdict, a human must approve the candidate
)

// Admit applies R >= U_hat in "modify" mode, the mode recommended by the offline evaluation.
func Admit(candidate, previous, bound float64) (float64, Verdict) {
	switch {
	case math.IsNaN(bound):
		return candidate, NeedsApproval
	case math.IsInf(bound, 1):
		if previous > candidate {
			return previous, Held
		}
		return candidate, Admitted
	case candidate >= bound:
		return candidate, Admitted
	default:
		return bound, Raised
	}
}
