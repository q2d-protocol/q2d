// The verifier's acceptable set — local configuration, never a message.
//
// P-003 issue 4, and its §9 item 1: this is the entire downgrade defence. §4.2 step 2
// rejects unless the declared suite is a member of this set, and a verifier that
// verifies with whatever the header names has agility in the same sense that an
// unlocked door has a lock.
//
// # Why there is no constructor taking a message
//
// There is no code path from received data to a SuitePolicy. That is the
// property, and it is carried by the type rather than by a comment: the only
// constructor takes a registry and a list of identifiers an operator wrote down,
// and nothing in this package produces such a list from a message.
//
// # The floor, and why lowering it fails rather than clamps
//
// P-003 §10 settled the source: a config file, over a compiled-in floor that
// configuration may raise and may never lower. Environment variables were
// rejected as a source — invisible in review, trivially altered by anything
// sharing the process, and a downgrade that lands via one leaves no artifact
// anyone would think to check.
//
// The floor is meetsFloor: a suite must be registered, and its status must
// permit verification. Configuration may name fewer suites than the floor
// admits, which is raising it. Naming one the floor excludes is a startup
// failure, not a silently dropped entry, because a clamped misconfiguration
// reads as success — the operator believes they configured something they did
// not, and the belief survives until the day it matters.
package q2d

import (
	"fmt"
	"sort"
)

// DefaultAcceptable is the suite a build accepts when configuration names none.
//
// The mandatory-to-implement suite, alone. A default that accepted everything
// registered would make adding a suite to the registry a change in what every
// unconfigured deployment accepts.
const DefaultAcceptable = "eddsa-jws-2026"

// SuitePolicy is the set of suites this verifier accepts.
type SuitePolicy struct {
	acceptable map[string]struct{}
}

// Implemented is the set of suites this build can actually execute.
//
// Not the same question as which suites are registered. A registry is data and
// may name a suite whose algorithm this code does not implement; SignCompact
// produces Ed25519 whatever identifier it is handed, so accepting such a suite
// would mean signing one thing while calling it another — and crypto-suites.md
// §1 makes the identifier name the algorithm, the serialization and the hash as
// one unit, which is exactly the coupling that would break.
//
// Adding an identifier here is a code change, and it is the change that adds the
// code. Adding one to the registry is not.
var Implemented = []string{"eddsa-jws-2026"}

// ImplementsSuite reports whether this build implements the suite an identifier
// names.
func ImplementsSuite(id string) bool {
	for _, known := range Implemented {
		if known == id {
			return true
		}
	}
	return false
}

// meetsFloor is the compiled-in floor: registered, implemented, and permitted to
// verify by its status.
//
// Configuration cannot reach below this. A withdrawn suite is excluded here
// rather than at verification time so that a deployment naming one fails to
// start — the operator finds out when they change the configuration rather than
// when a message arrives.
func meetsFloor(registry SuiteRegistry, id string) bool {
	if !ImplementsSuite(id) {
		return false
	}
	entry, err := registry.Resolve(id)
	return err == nil && entry.status.MayVerify()
}

// NewSuitePolicy builds a policy from configuration.
//
// configured is what an operator wrote in a config file. An empty list means
// they wrote nothing, which is DefaultAcceptable.
func NewSuitePolicy(registry SuiteRegistry, configured []string) (SuitePolicy, error) {
	wanted := configured
	if len(wanted) == 0 {
		wanted = []string{DefaultAcceptable}
	}

	acceptable := make(map[string]struct{}, len(wanted))
	for _, id := range wanted {
		if !meetsFloor(registry, id) {
			// Named, because this is the operator's own configuration and they
			// need to know which line is wrong. Nothing here comes from a
			// message.
			return SuitePolicy{}, fmt.Errorf(
				"configuration accepts `%s`, which is below this build's floor "+
					"— it is unregistered, this build does not implement it, or "+
					"its status does not permit verification. Startup fails "+
					"rather than dropping it, because a dropped entry reads as "+
					"a policy that was applied", id)
		}
		acceptable[id] = struct{}{}
	}

	if len(acceptable) == 0 {
		return SuitePolicy{}, fmt.Errorf("an empty acceptable set would reject every message")
	}
	return SuitePolicy{acceptable: acceptable}, nil
}

// Accepts answers §4.2 step 2. The only question this type answers.
func (p SuitePolicy) Accepts(id string) bool {
	_, ok := p.acceptable[id]
	return ok
}

// Advertised returns the configured set, for operator tooling and capability
// discovery.
//
// Never for a rejection message — §4.5: a rejection names no alternative,
// because suggesting a suite the verifier would accept turns every rejection
// into a probe of local policy. Advertising is a deliberate choice made once, in
// capability discovery, rather than leaked one rejection at a time.
func (p SuitePolicy) Advertised() []string {
	ids := make([]string, 0, len(p.acceptable))
	for id := range p.acceptable {
		ids = append(ids, id)
	}
	// Sorted, because map iteration order must never reach an output.
	sort.Strings(ids)
	return ids
}
