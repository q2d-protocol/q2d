package q2d

import (
	"strings"
	"testing"
)

// These mirror src/freshness.rs's tests case for case. Two readings of
// spec/freshness.md that disagree would be a specification ambiguity found, so
// the cases are deliberately the same and the code deliberately is not shared.

const (
	freshIssued  int64 = 1000000
	freshExpires int64 = freshIssued + 300
)

func TestARequestInsideItsWindowIsFresh(t *testing.T) {
	if err := DefaultFreshnessPolicy().Check(freshIssued, freshExpires, freshIssued+1); err != nil {
		t.Errorf("fresh request rejected: %v", err)
	}
}

func TestBothBoundariesAreInclusiveToTheSecond(t *testing.T) {
	// §2's comparisons are strict, so the tolerance instants themselves are
	// inside. This is the assertion P-004 §7 asks for, and the one place two
	// implementations most easily disagree while both looking right.
	p := DefaultFreshnessPolicy()
	if err := p.Check(freshIssued, freshExpires, freshExpires+SkewSeconds); err != nil {
		t.Errorf("exactly at the expiry tolerance: %v", err)
	}
	if err := p.Check(freshIssued, freshExpires, freshExpires+SkewSeconds+1); err != RequestExpired {
		t.Errorf("one second past: %v, want RequestExpired", err)
	}
	if err := p.Check(freshIssued, freshExpires, freshIssued-SkewSeconds); err != nil {
		t.Errorf("exactly at the issue tolerance: %v", err)
	}
	if err := p.Check(freshIssued, freshExpires, freshIssued-SkewSeconds-1); err != RequestFutureDated {
		t.Errorf("one second before: %v, want RequestFutureDated", err)
	}
}

func TestTheWindowIsARangeAndNotACeiling(t *testing.T) {
	// The lower end is what E-49 added, and it is not decoration: a negative
	// window is above no ceiling, and there is an interval in which the other two
	// conditions both pass.
	p := DefaultFreshnessPolicy()
	for _, c := range []struct{ expires int64 }{
		{freshIssued + 301}, {freshIssued}, {freshIssued - 10},
	} {
		if err := p.Check(freshIssued, c.expires, freshIssued); err != RequestWindowOutOfRange {
			t.Errorf("expires %d: %v, want RequestWindowOutOfRange", c.expires, err)
		}
	}
}

func TestANegativeWindowWouldOtherwiseBeFresh(t *testing.T) {
	// The counterexample spec/freshness.md §2 states, executed. With the window
	// condition removed, every now across a skew-length interval passes the other
	// two — so this is the interval the range closed, and the test exists to fail
	// if the lower bound is ever dropped.
	issued, expires := freshIssued, freshIssued-10
	wouldHavePassed := 0
	for now := issued - 200; now < issued+200; now++ {
		expired := now > expires+SkewSeconds
		future := now < issued-SkewSeconds
		if !expired && !future {
			wouldHavePassed++
			if err := DefaultFreshnessPolicy().Check(issued, expires, now); err != RequestWindowOutOfRange {
				t.Fatalf("now=%d: %v", now, err)
			}
		}
	}
	if wouldHavePassed != 111 {
		t.Errorf("the interval §2 describes is %d seconds, expected 111", wouldHavePassed)
	}
}

func TestEveryFreshnessRejectionIsOneWireValueAtOneStep(t *testing.T) {
	// §5.2.1 gives `expired` for all three, so a requester cannot tell a clock
	// disagreement from a window it built wrongly. Asserted across the causes
	// rather than per cause — per-case assertions pass while the values diverge.
	p := DefaultFreshnessPolicy()
	rejections := []error{
		p.Check(freshIssued, freshExpires, freshExpires+1000),
		p.Check(freshIssued, freshExpires, freshIssued-1000),
		p.Check(freshIssued, freshIssued+1000, freshIssued),
	}
	internal := map[string]struct{}{}
	external := map[string]struct{}{}
	steps := map[string]struct{}{}
	for _, err := range rejections {
		rejected, ok := err.(Rejected)
		if !ok {
			t.Fatalf("%v is not a Rejected", err)
		}
		internal[rejected.Error()] = struct{}{}
		external[rejected.ExternalReason()] = struct{}{}
		steps[rejected.Step()] = struct{}{}
	}
	if len(internal) != 3 {
		t.Errorf("%d internal reasons, an operator cannot tell them apart", len(internal))
	}
	if len(external) != 1 {
		t.Errorf("%d wire values, want 1", len(external))
	}
	if _, ok := external["expired"]; !ok {
		t.Error("the wire value is not `expired`")
	}
	if _, ok := steps["6"]; !ok || len(steps) != 1 {
		t.Errorf("steps %v, want only 6", steps)
	}
}

func TestRetentionIsTheInstantTheRequestStopsBeingAcceptable(t *testing.T) {
	// The two have to agree or the cache and the freshness check disagree at
	// exactly one second, which is the defect E-49's review found. Asserted as a
	// relationship rather than as a number.
	p := DefaultFreshnessPolicy()
	through := p.RetainThrough(freshExpires)
	if err := p.Check(freshIssued, freshExpires, through); err != nil {
		t.Errorf("still acceptable at the retention instant: %v", err)
	}
	if err := p.Check(freshIssued, freshExpires, through+1); err == nil {
		t.Error("acceptable after the retention instant")
	}
}

func TestAnEntryIsNeverRetainedBeyondTheDerivedBound(t *testing.T) {
	// window + 2×skew is what the derivation bounds an entry to, which is the
	// memory argument. Checked against the earliest instant the request could have
	// been accepted, not against entry creation.
	p := DefaultFreshnessPolicy()
	for window := int64(1); window <= MaxWindowSeconds; window++ {
		held := p.RetainThrough(freshIssued+window) - (freshIssued - SkewSeconds)
		if held > MaxWindowSeconds+2*SkewSeconds {
			t.Fatalf("window %d held for %d", window, held)
		}
	}
}

func TestTheNonceFloorIsOnDecodedBytes(t *testing.T) {
	// Sixteen bytes is twenty-two base64url characters. A check against the string
	// would accept the second of these, which carries twelve bytes.
	p := DefaultFreshnessPolicy()
	if err := p.CheckNonce(EncodeBase64URL(make([]byte, 16))); err != nil {
		t.Errorf("sixteen bytes rejected: %v", err)
	}
	if err := p.CheckNonce(EncodeBase64URL(make([]byte, 12))); err != CoreObjectNonceTooShort {
		t.Errorf("twelve bytes: %v, want CoreObjectNonceTooShort", err)
	}
	if got := len(EncodeBase64URL(make([]byte, 16))); got != 22 {
		t.Errorf("the length a string check would have compared is %d, not 22", got)
	}
}

func TestANonceOfZeroBytesPassesAndThatIsThePoint(t *testing.T) {
	// spec/freshness.md §3: the floor is necessary and not sufficient. This nonce
	// has no entropy at all and there is nothing here that could notice — a
	// responder holds one nonce and no distribution. The test exists so nobody
	// later reads the floor as an entropy check.
	if err := DefaultFreshnessPolicy().CheckNonce(EncodeBase64URL(make([]byte, 32))); err != nil {
		t.Errorf("thirty-two zero bytes rejected: %v", err)
	}
}

func TestANonceThatIsNotBase64URLIsADifferentReason(t *testing.T) {
	// Two mistakes in a requester's own message: an encoding fault, and a
	// generator asked for too few bytes. One wire value, because both are visible
	// in the bytes the requester produced.
	err := DefaultFreshnessPolicy().CheckNonce("****not base64url****")
	if err != CoreObjectNonceNotBase64URL {
		t.Fatalf("%v, want CoreObjectNonceNotBase64URL", err)
	}
	rejected := err.(Rejected)
	if rejected.ExternalReason() != "malformed" || rejected.Step() != "5" {
		t.Errorf("%s at step %s, want malformed at 5", rejected.ExternalReason(), rejected.Step())
	}
}

func TestConfigurationMayOnlyMakeAResponderStricter(t *testing.T) {
	if _, err := NewFreshnessPolicy(FreshnessConfig{
		Skew: seconds(30), Window: seconds(120), MinNonceBytes: count(32),
	}); err != nil {
		t.Errorf("a stricter configuration was refused: %v", err)
	}
	// Each direction, because getting one backwards reads as tightening.
	for _, c := range []FreshnessConfig{
		{Skew: seconds(SkewSeconds + 1)},
		{Window: seconds(MaxWindowSeconds + 1)},
		{MinNonceBytes: count(MinNonceBytes - 1)},
	} {
		if _, err := NewFreshnessPolicy(c); err == nil {
			t.Errorf("%+v was accepted", c)
		}
	}
}

func TestALaxerConfigurationFailsStartupRatherThanBeingClamped(t *testing.T) {
	// The important half. A clamped misconfiguration reads as success.
	_, err := NewFreshnessPolicy(FreshnessConfig{Window: seconds(600)})
	if err == nil {
		t.Fatal("a 600s window was accepted")
	}
	for _, want := range []string{"600", "300"} {
		if !strings.Contains(err.Error(), want) {
			t.Errorf("%q does not name %s", err, want)
		}
	}
}

func TestAnUnreadableTimestampIsMalformedAndNotExpired(t *testing.T) {
	// A spelling §2.2 refuses is a fault in the requester's serializer, and
	// calling it `expired` would send them to their clock.
	err := CheckFreshnessText(DefaultFreshnessPolicy(),
		"2026-07-31T09:00:00+00:00", "2026-07-31T09:05:00Z", "2026-07-31T09:01:00Z")
	if err != CoreObjectMalformed {
		t.Fatalf("%v, want CoreObjectMalformed", err)
	}
	if err.(Rejected).ExternalReason() != "malformed" {
		t.Errorf("wire value %s", err.(Rejected).ExternalReason())
	}
}

func TestCheckTextAgreesWithCheck(t *testing.T) {
	p := DefaultFreshnessPolicy()
	if err := CheckFreshnessText(p, "2026-07-31T09:00:00Z", "2026-07-31T09:05:00Z", "2026-07-31T09:06:00Z"); err != nil {
		t.Errorf("one minute past expiry is exactly the skew tolerance: %v", err)
	}
	if err := CheckFreshnessText(p, "2026-07-31T09:00:00Z", "2026-07-31T09:05:00Z", "2026-07-31T09:06:01Z"); err != RequestExpired {
		t.Errorf("%v, want RequestExpired", err)
	}
}

func TestAnExplicitZeroIsNotAnAbsentValue(t *testing.T) {
	// The divergence review found. A zero window is not "configured nothing" —
	// it is a configuration that rejects every request — and a zero nonce floor
	// is below the specification's. A sentinel-based signature would silently
	// substitute the default for both, accepting what the Rust side refuses,
	// because Option<i64> tells None from Some(0).
	if _, err := NewFreshnessPolicy(FreshnessConfig{Window: seconds(0)}); err == nil {
		t.Error("an explicit zero window was accepted")
	}
	if _, err := NewFreshnessPolicy(FreshnessConfig{MinNonceBytes: count(0)}); err == nil {
		t.Error("an explicit zero nonce floor was accepted")
	}
	// And an explicit zero skew is legal: it is stricter, not laxer.
	if _, err := NewFreshnessPolicy(FreshnessConfig{Skew: seconds(0)}); err != nil {
		t.Errorf("an explicit zero skew was refused: %v", err)
	}
}

func seconds(v int64) *int64 { return &v }
func count(v int) *int       { return &v }
