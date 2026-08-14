// Command q2d-conform is the Go conformance runner: it implements the
// contract and answers nothing yet.
//
//	q2d-conform <vector-file.json>   →  result JSON on stdout
//
// See conformance/RUNNER-CONTRACT.md. This is the Go half of the pair
// `harness cross` compares. It exists before either implementation does, so
// that the contract is demonstrably implementable in both languages and so that
// P-001 issue 19's cross-verification has two runners to put an artefact
// between.
//
// It implements no Q2D behaviour, and adding some is a deliberate act. Every
// operation reports error. What it does implement is the half of the contract
// that is not protocol: read the projection, parse it as RFC 8259 JSON rather
// than as what a library tolerates, recognise the operation or exit 1, and emit
// a well-formed result. That much has to be right, because the harness is
// entitled to assume it.
//
// Unlike conformance/runners/stub/, this one may learn to answer — it is the
// reference implementation's runner, and the corpus exists to be run against
// it. The stub may not, because it shares an author with the harness.
//
// No dependencies, and two places where the standard library is not strict
// enough on its own.
//
// encoding/json refuses NaN and Infinity already. It does not refuse duplicate
// object keys — it keeps the last, silently. RFC 8259 calls that behaviour
// unpredictable, and a runner resolving a duplicate one way while its judge
// resolved it another would disagree about a vector neither could point at, so
// the token walk below refuses them: the only reading two implementations can
// share.
//
// Converting bytes to a string does not refuse malformed UTF-8 either — it
// substitutes U+FFFD, which would let this runner answer a file the Rust one
// rejects outright. parseStrictly checks the bytes before decoding them.
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
	"unicode/utf8"
)

const (
	name    = "q2d-go"
	version = "0.0.0"

	exitResultProduced = 0
	exitCannotProcess  = 1
	exitInternal       = 2
)

// projectedFields is P-001 §6's VectorInput, and nothing else.
var projectedFields = []string{"id", "operation", "input"}

// knownOperations is P-001 §4.5's vocabulary, embedded rather than read from
// vector.schema.json.
//
// A runner reads the vector it was given and nothing else. One that consulted
// the schema would answer differently depending on the checkout it ran in, and
// this binary ships without the corpus beside it. Drift is caught where it
// should be: an operation a runner does not recognise is exit 1 and the vector
// fails loudly.
var knownOperations = map[string]bool{
	"sign_query":         true,
	"sign_response":      true,
	"verify_query":       true,
	"verify_response":    true,
	"digest":             true,
	"resolve_predicate":  true,
	"effective_domain":   true,
	"capacity_debit":     true,
	"policy_decide":      true,
	"evaluate_predicate": true,
	"process_query":      true,
}

// refuseDuplicateKeys walks every object in the document and fails on a
// repeated name, at any depth: a duplicate three levels down is still a vector
// to refuse.
//
// It is a second pass over the same bytes rather than a custom Unmarshaler,
// because a custom one would have to model the whole vector — and the runner
// deliberately models none of it.
func refuseDuplicateKeys(dec *json.Decoder) error {
	token, err := dec.Token()
	if err != nil {
		return err
	}
	delim, isDelim := token.(json.Delim)
	if !isDelim {
		return nil
	}
	switch delim {
	case '{':
		seen := map[string]bool{}
		for dec.More() {
			keyToken, err := dec.Token()
			if err != nil {
				return err
			}
			key, ok := keyToken.(string)
			if !ok {
				return fmt.Errorf("object key is not a string")
			}
			if seen[key] {
				return fmt.Errorf("duplicate object key %q", key)
			}
			seen[key] = true
			if err := refuseDuplicateKeys(dec); err != nil {
				return err
			}
		}
	case '[':
		for dec.More() {
			if err := refuseDuplicateKeys(dec); err != nil {
				return err
			}
		}
	}
	// Consume the closing delimiter.
	_, err = dec.Token()
	return err
}

// refuseLoneSurrogates walks the raw text and fails on a \uXXXX escape that is
// half of a surrogate pair.
//
// encoding/json substitutes U+FFFD for an unpaired surrogate and says nothing,
// which is indistinguishable from a document that legitimately contained
// U+FFFD — and the Rust runner refuses the escape outright. RFC 8259 §8.2 calls
// text containing unpaired surrogates not interoperable, so refusing is the
// reading both can share; substituting is the one that cannot be agreed on,
// because the substitute is a valid character.
//
// A raw scan rather than a Decoder walk, because a Decoder has already resolved
// the escape by the time a token is handed over.
func refuseLoneSurrogates(data []byte) error {
	inString := false
	for i := 0; i < len(data); i++ {
		switch {
		case !inString:
			if data[i] == '"' {
				inString = true
			}
		case data[i] == '"':
			inString = false
		case data[i] == '\\':
			if i+1 >= len(data) {
				return fmt.Errorf("unterminated escape")
			}
			if data[i+1] != 'u' {
				i++ // A two-character escape; skip what it escapes.
				continue
			}
			code, err := hexEscape(data, i)
			if err != nil {
				return err
			}
			i += 5
			if code >= 0xdc00 && code < 0xe000 {
				return fmt.Errorf("a low surrogate with no high surrogate before it")
			}
			if code < 0xd800 || code >= 0xdc00 {
				continue
			}
			if i+6 >= len(data) || data[i+1] != '\\' || data[i+2] != 'u' {
				return fmt.Errorf("a high surrogate with no low surrogate after it")
			}
			low, err := hexEscape(data, i+1)
			if err != nil {
				return err
			}
			if low < 0xdc00 || low >= 0xe000 {
				return fmt.Errorf("a high surrogate followed by something that is not a low one")
			}
			i += 6
		}
	}
	return nil
}

// hexEscape reads the four hex digits of the \u escape beginning at at.
func hexEscape(data []byte, at int) (uint32, error) {
	if at+6 > len(data) {
		return 0, fmt.Errorf("truncated \\u escape")
	}
	var code uint32
	for _, b := range data[at+2 : at+6] {
		var digit uint32
		switch {
		case b >= '0' && b <= '9':
			digit = uint32(b - '0')
		case b >= 'a' && b <= 'f':
			digit = uint32(b-'a') + 10
		case b >= 'A' && b <= 'F':
			digit = uint32(b-'A') + 10
		default:
			return 0, fmt.Errorf("invalid \\u escape")
		}
		code = code<<4 | digit
	}
	return code, nil
}

// parseStrictly reads the document as RFC 8259 JSON rather than as what
// encoding/json tolerates.
func parseStrictly(data []byte) (map[string]any, error) {
	// RFC 8259 §8.1: a JSON text is Unicode. Converting bytes to a string
	// silently replaces malformed UTF-8 with U+FFFD, so a runner that skipped
	// this would answer a file the Rust runner refuses — a divergence about
	// encoding, which is precisely what `harness cross` must never report.
	if !utf8.Valid(data) {
		return nil, fmt.Errorf("the vector file is not valid UTF-8")
	}

	if err := refuseLoneSurrogates(data); err != nil {
		return nil, err
	}

	if err := refuseDuplicateKeys(json.NewDecoder(bytes.NewReader(data))); err != nil {
		return nil, err
	}

	dec := json.NewDecoder(bytes.NewReader(data))
	var value any
	if err := dec.Decode(&value); err != nil {
		return nil, err
	}
	// Anything after the first document is not part of it.
	if _, err := dec.Token(); err != io.EOF {
		return nil, fmt.Errorf("trailing content after the JSON document")
	}
	object, ok := value.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("the vector file is not an object")
	}
	return object, nil
}

func fail(message string, code int) int {
	fmt.Fprintf(os.Stderr, "q2d-conform: %s\n", message)
	return code
}

func run(args []string) int {
	if len(args) != 2 {
		return fail("usage: q2d-conform <vector-file.json>", exitCannotProcess)
	}

	data, err := os.ReadFile(args[1])
	if err != nil {
		return fail(fmt.Sprintf("cannot read the vector: %v", err), exitCannotProcess)
	}
	vector, err := parseStrictly(data)
	if err != nil {
		return fail(fmt.Sprintf("cannot read the vector: %v", err), exitCannotProcess)
	}

	// Both present *and* strings. A non-string id copied into vector_id would
	// be a result the harness cannot judge — the runner reporting that it
	// functioned when it did not.
	for _, field := range []string{"id", "operation"} {
		if _, ok := vector[field].(string); !ok {
			return fail(fmt.Sprintf("the vector carries no string %s", field), exitCannotProcess)
		}
	}

	var missing []string
	for _, field := range projectedFields {
		if _, ok := vector[field]; !ok {
			missing = append(missing, field)
		}
	}
	if len(missing) > 0 {
		return fail("the vector carries no "+strings.Join(missing, ", "), exitCannotProcess)
	}

	var extra []string
	for key := range vector {
		known := false
		for _, field := range projectedFields {
			if key == field {
				known = true
				break
			}
		}
		if !known {
			extra = append(extra, key)
		}
	}
	sort.Strings(extra)
	if len(extra) > 0 {
		// The extra field that matters is `expect`. A runner holding an
		// expectation was handed the authored vector, so the harness failed to
		// project it — and the corpus stops being evidence the moment an
		// implementation can read the answer. Refusing is the second lock on a
		// door the harness holds the first key to.
		for _, key := range extra {
			if key == "expect" {
				return fail("the vector carries an expectation -- it was not projected; "+
					"refusing to answer a vector whose answer it was given", exitCannotProcess)
			}
		}
		return fail("the vector carries unexpected field(s): "+strings.Join(extra, ", "),
			exitCannotProcess)
	}

	operation := vector["operation"].(string)
	if !knownOperations[operation] {
		return fail(fmt.Sprintf("unknown operation %q", operation), exitCannotProcess)
	}

	// A result was produced, so exit 0. The vector fails on its outcome, which
	// is the harness's call and not this runner's.
	result := map[string]any{
		"vector_id": vector["id"],
		"outcome":   "error",
		"detail":    "the Go runner implements no Q2D behaviour yet",
		"implementation": map[string]string{
			"name":    name,
			"version": version,
		},
	}
	encoded, err := json.Marshal(result)
	if err != nil {
		return fail(fmt.Sprintf("cannot encode the result: %v", err), exitInternal)
	}
	fmt.Println(string(encoded))
	return exitResultProduced
}

func main() {
	// The contract's exit 2: a fault so early that no result could be written,
	// distinguished from exit 1 so the harness can tell "this runner cannot
	// process the vector" from "this runner broke".
	defer func() {
		if r := recover(); r != nil {
			os.Exit(fail(fmt.Sprintf("internal error: %v", r), exitInternal))
		}
	}()
	os.Exit(run(os.Args))
}
