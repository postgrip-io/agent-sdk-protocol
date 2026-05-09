// Package protocol carries the wire-format types and Ed25519 task-result
// signing logic for the PostGrip Agent runtime service. It is the single
// source of truth shared by the postgrip-web runtime, the customer-facing
// agent-sdk-go, and (via hand-mirrored type definitions) agent-sdk-typescript
// and agent-sdk-python.
//
// # Import path
//
// Package files live under the repository's src/ directory so this repo's
// layout matches the sibling SDK repos (agent-sdk-go, agent-sdk-typescript,
// agent-sdk-python). Consumer Go code therefore imports the /src subpath:
//
//	import protocol "github.com/postgrip-io/agent-sdk-protocol/src"
//
// The declared package name stays "protocol", so usage at the call site is
// unchanged from the original postgrip-web/postgrip-agent/protocol package
// — only the import path picked up the /src segment.
//
// # Stability
//
// Types in this package are the on-the-wire contract. Any change here lands
// simultaneously in the postgrip-web runtime and is implicitly contracted
// against the TS/Python SDK type mirrors. A drift guard in
// tools/check-drift.sh fails CI when a Go type's exported field set does
// not match the TS/Python equivalents.
package protocol
