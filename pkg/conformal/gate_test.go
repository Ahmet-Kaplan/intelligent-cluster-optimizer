package conformal

import (
	"math"
	"testing"
	"time"
)

// pyBounds is aci_bounds(upper, y, ConformalConfig(eps=0.1, eta=0.05, window=20)) from
// experiments/conformal_gate/src/cgate/conformal.py on the series built in TestBoundMatchesPython.
var pyBounds = []float64{
	math.NaN(), math.NaN(), math.NaN(), math.NaN(), math.NaN(), math.NaN(), math.NaN(), math.NaN(), math.NaN(),
	116.36638000339728, 113.04950029404375, 109.94240943691516, 107.38715496971932, 105.66503491009098,
	104.96563075181932, 100.69931962249693, 102.15526845345251, 104.50657995168523, 107.49440738713905,
	111.98282078093359, 118.69669222851081, 121.5250459099865, 123.63014861898667, 124.78025779266234,
	124.84876238903243, 121.94499139753682, 119.9475624677205, 117.19323516900745, 113.98522267213737,
	109.24942091359956, 107.63183920769619, 105.18588749435764, 103.6080927482088, 103.07214825108285,
	math.Inf(1), math.Inf(1), math.Inf(1), math.Inf(1), math.Inf(1), 117.40987660488122, 120.14772158238537,
	122.12162232843562, 123.11427979356351, 123.01641618148085, 121.838804916295, math.Inf(1), math.Inf(1),
	math.Inf(1), math.Inf(1), 108.75672493382763, 106.42622582472893, 104.99672343751281, 104.62558612546474,
	105.35367095056807, 107.10082588859161, 109.67471345343516, 112.79198438227573, 116.1094704529379,
	119.26196253764657, 121.26522163887154,
}

func TestBoundMatchesPython(t *testing.T) {
	cfg := Config{Eps: 0.1, Eta: 0.05, Window: 20, Horizon: time.Hour}
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	upper := func(k int) float64 { return 100 + 10*math.Sin(float64(k)/3) }
	y := func(k int) float64 { return upper(k) + 8*math.Cos(float64(k)*1.7) + 2*float64(k%5) }
	peak := func(from, _ time.Time) (float64, bool) { return y(int(from.Sub(t0) / time.Hour)), true }

	g := NewGate()
	for k, want := range pyBounds {
		got := g.Bound(cfg, "c", t0.Add(time.Duration(k)*time.Hour), upper(k), peak)
		same := (math.IsNaN(want) && math.IsNaN(got)) || got == want || math.Abs(got-want) < 1e-9
		if !same {
			t.Fatalf("decision %d: bound %v, python %v", k, got, want)
		}
	}
}

func TestBoundHoldsWithinHorizon(t *testing.T) {
	cfg := Config{Eps: 0.5, Eta: 0, Window: 10, Horizon: time.Hour}
	t0 := time.Now()
	peak := func(time.Time, time.Time) (float64, bool) { return 3, true }
	g := NewGate()
	g.Bound(cfg, "c", t0, 1, peak)                           // decision 0, cold
	b1 := g.Bound(cfg, "c", t0.Add(time.Hour), 1, peak)      // scores {2}: finite bound 1 + 2
	b2 := g.Bound(cfg, "c", t0.Add(90*time.Minute), 9, peak) // same horizon: unchanged
	if b1 != 3 || b2 != 3 {
		t.Fatalf("bounds %v, %v; want 3, 3", b1, b2)
	}
}

func TestBudgetChangeRestartsCalibration(t *testing.T) {
	t0 := time.Now()
	peak := func(time.Time, time.Time) (float64, bool) { return 3, true }
	g := NewGate()
	g.Bound(Config{Eps: 0.5, Window: 10, Horizon: time.Hour}, "c", t0, 1, peak)
	if b := g.Bound(Config{Eps: 0.25, Window: 10, Horizon: time.Hour}, "c", t0.Add(time.Hour), 1, peak); !math.IsNaN(b) {
		t.Fatalf("bound %v after budget change; want cold start", b)
	}
}

func TestAdmit(t *testing.T) {
	cases := []struct {
		name                    string
		cand, prev, bound, want float64
		verdict                 Verdict
	}{
		{"cold start", 5, 8, math.NaN(), 5, NeedsApproval},
		{"admitted", 9, 8, 7, 9, Admitted},
		{"raised", 5, 8, 7, 7, Raised},
		{"uncertifiable holds", 5, 8, math.Inf(1), 8, Held},
		{"uncertifiable scale-up", 9, 8, math.Inf(1), 9, Admitted},
		{"any admitted", 1, 8, math.Inf(-1), 1, Admitted},
	}
	for _, c := range cases {
		got, v := Admit(c.cand, c.prev, c.bound)
		if got != c.want || v != c.verdict {
			t.Errorf("%s: Admit = (%v, %v), want (%v, %v)", c.name, got, v, c.want, c.verdict)
		}
	}
}
