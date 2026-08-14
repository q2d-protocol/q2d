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
// No dependencies. encoding/json already refuses NaN and Infinity; it does not
// refuse duplicate object keys, and keeps the last silently. RFC 8259 calls
// that behaviour unpredictable, and a runner that resolved a duplicate one way
// while its judge resolved it another would disagree about a vector neither
// could point at — so the token walk below refuses them, which is the only
// reading two implementations can share.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
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

// parseStrictly reads the document as RFC 8259 JSON rather than as what
// encoding/json tolerates.
func parseStrictly(data []byte) (map[string]any, error) {
	if err := refuseDuplicateKeys(json.NewDecoder(strings.NewReader(string(data)))); err != nil {
		return nil, err
	}

	dec := json.NewDecoder(strings.NewReader(string(data)))
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
