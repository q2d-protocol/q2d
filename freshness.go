// Freshness, skew, and the nonce floor — spec/freshness.md.
//
// P-004 issues 1 and 4. Two checks that happen at different steps and are here
// together because one document states both: the nonce floor at core-model.md §4
// step 5, freshness at step 6.
//
// # Nothing here reads a clock
//
// now is a parameter. A responder's clock is the caller's to supply, which is
// what lets a corpus vector state it (P-001 §4.3) and what stops two runs of one
// vector disagreeing. A function here that called time.Now could not be pinned by
// a vector at all, and the boundary cases are exactly where the two
// implementations have to agree.
//
// # Why the comparisons are integers
//
// Timestamps become seconds (TimestampToEpochSeconds) and every comparison is
// integer. freshness.md §2 states the conditions as strict inequalities on exact
// instants, and a floating-point second would make "exactly at the boundary"
// depend on rounding.
package q2d

import "fmt"

// SkewSeconds is freshness.md §1's clock-skew tolerance.
const SkewSeconds int64 = 60

// MaxWindowSeconds is freshness.md §1's maximum validity window.
const MaxWindowSeconds int64 = 300

// MinNonceBytes is freshness.md §1's minimum nonce length, in decoded bytes.
//
// On the decoded bytes and not on the string. Sixteen bytes is twenty-two
// base64url characters, so a check against the string would accept a twelve-byte
// nonce — §3 states which, because the two differ and nothing in a message says
// which a responder applied.
const MinNonceBytes = 16

// FreshnessPolicy is the set of bounds this responder applies.
//
// Configuration may only make a responder stricter — freshness.md §1 — and a
// value on the wrong side of a bound fails at startup rather than being clamped.
// Same rule and same reason as SuitePolicy: a clamped misconfiguration reads as
// success, and the operator's belief that they configured something survives
// until the day it matters.
//
// Fields are unexported so the only origin is DefaultFreshnessPolicy or
// NewFreshnessPolicy. A caller able to write FreshnessPolicy{window: 86400}
// would have the laxness the constructor exists to refuse.
type FreshnessPolicy struct {
	skew          int64
	window        int64
	minNonceBytes int
}

// DefaultFreshnessPolicy is the specification's bounds, which is what a
// deployment that configures nothing gets.
func DefaultFreshnessPolicy() FreshnessPolicy {
	return FreshnessPolicy{
		skew:          SkewSeconds,
		window:        MaxWindowSeconds,
		minNonceBytes: MinNonceBytes,
	}
}

// FreshnessConfig is what an operator wrote, with absent distinguished from
// zero.
//
// Pointers rather than zero-value sentinels, and the difference is not
// cosmetic: a zero window is not "configured nothing", it is a configuration
// that rejects every request, and freshness.md §1 requires a value on the wrong
// side of a bound to fail at startup. With a sentinel this file would silently
// substitute the default for it — accepting a misconfiguration the Rust side
// refuses, since Option<i64> tells None from Some(0). Review found exactly that
// divergence.
type FreshnessConfig struct {
	Skew          *int64
	Window        *int64
	MinNonceBytes *int
}

// NewFreshnessPolicy builds from configuration, refusing anything laxer than the
// specification.
//
// A nil field means the operator configured nothing. The directions differ per
// bound and they are not arbitrary: a smaller skew or window is stricter, and a
// larger nonce floor is. That is the shape freshness.md §1's table states, and
// getting one backwards would let configuration widen the interval a captured
// envelope stays replayable in while looking like tightening.
func NewFreshnessPolicy(config FreshnessConfig) (FreshnessPolicy, error) {
	policy := DefaultFreshnessPolicy()
	if config.Skew != nil {
		policy.skew = *config.Skew
	}
	if config.Window != nil {
		policy.window = *config.Window
	}
	if config.MinNonceBytes != nil {
		policy.minNonceBytes = *config.MinNonceBytes
	}

	// Named values, because this is the operator's own configuration file and
	// they need to know which line is wrong. Nothing here comes from a message.
	if policy.skew > SkewSeconds {
		return FreshnessPolicy{}, fmt.Errorf(
			"configured clock skew %ds is above freshness.md §1's %ds, which would "+
				"accept requests the specification does not", policy.skew, SkewSeconds)
	}
	if policy.window > MaxWindowSeconds {
		return FreshnessPolicy{}, fmt.Errorf(
			"configured validity window %ds is above freshness.md §1's %ds, which would "+
				"leave a captured envelope replayable for longer than the specification "+
				"permits", policy.window, MaxWindowSeconds)
	}
	if policy.minNonceBytes < MinNonceBytes {
		return FreshnessPolicy{}, fmt.Errorf(
			"configured nonce floor %d bytes is below freshness.md §1's %d",
			policy.minNonceBytes, MinNonceBytes)
	}
	if policy.skew < 0 || policy.window <= 0 {
		return FreshnessPolicy{}, fmt.Errorf(
			"a negative skew or a non-positive window would reject every request")
	}
	return policy, nil
}

// RetainThrough is the instant a replay-cache entry for this request must be
// retained through — freshness.md §1.
//
// Inclusive, and that is the whole point of the method existing. §2's first
// condition rejects only when now is strictly past expires_at + skew, so the
// request is still acceptable at that instant and an entry evicted then is
// evicted one second early. Deriving the instant here rather than letting the
// cache compute a duration is what stops the two drifting apart.
func (p FreshnessPolicy) RetainThrough(expiresAt int64) int64 {
	return expiresAt + p.skew
}

// Check is freshness.md §2, at core-model.md §4 step 6.
//
// Takes seconds, not text: the caller has the verified core object and has
// already read its timestamps, and a second parse here would be a second
// definition of what a Q2D timestamp is.
func (p FreshnessPolicy) Check(issuedAt, expiresAt, now int64) error {
	// The window first, because it is a property of the message alone and the
	// other two involve the responder's clock. A message whose window is unusable
	// is wrong however good the clock is, and reporting a clock disagreement for
	// it would send an operator to the wrong place.
	window := expiresAt - issuedAt
	if window <= 0 || window > p.window {
		return RequestWindowOutOfRange
	}
	if now > expiresAt+p.skew {
		return RequestExpired
	}
	if now < issuedAt-p.skew {
		return RequestFutureDated
	}
	return nil
}

// CheckNonce is freshness.md §3's floor, at core-model.md §4 step 5.
//
// The floor and nothing else. Entropy is the requester's obligation and no check
// here can establish it — sixteen zero bytes pass this function. That is not a
// shortcoming to be fixed later: a responder holds one nonce and no distribution,
// so there is nothing to measure.
func (p FreshnessPolicy) CheckNonce(nonce string) error {
	decoded, err := DecodeBase64URL(nonce)
	if err != nil {
		return CoreObjectNonceNotBase64URL
	}
	if len(decoded) < p.minNonceBytes {
		return CoreObjectNonceTooShort
	}
	return nil
}

// CheckFreshnessText is Check over the text a core object carries.
//
// A convenience for a caller holding strings rather than seconds. A timestamp
// that will not convert is not a freshness failure: it is a core object that
// never satisfied core-model.md §2.2, caught at step 5, and reporting it as
// expired would tell a requester its clock is wrong when its serializer is.
func CheckFreshnessText(policy FreshnessPolicy, issuedAt, expiresAt, now string) error {
	issued, ok := TimestampToEpochSeconds(issuedAt)
	if !ok {
		return CoreObjectMalformed
	}
	expires, ok := TimestampToEpochSeconds(expiresAt)
	if !ok {
		return CoreObjectMalformed
	}
	at, ok := TimestampToEpochSeconds(now)
	if !ok {
		return CoreObjectMalformed
	}
	return policy.Check(issued, expires, at)
}
