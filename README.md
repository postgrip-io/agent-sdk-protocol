# agent-sdk-protocol

Wire-format types and Ed25519 task-result signing for the PostGrip Agent
runtime service. **Single source of truth** for the runtime contract:
`agent-sdk-go` imports it directly, the `postgrip-web` runtime imports
it directly, and `agent-sdk-typescript` / `agent-sdk-python` mirror the
same shapes. `tools/check_drift.py` fails CI when the three language
type definitions diverge.

## Install

```sh
go get github.com/postgrip-io/agent-sdk-protocol
```

```go
import "github.com/postgrip-io/agent-sdk-protocol"

t := protocol.Task{ /* ... */ }
```

## Layout

```text
*.go                  # Go package "protocol" — types + signing + tests, at module root (idiomatic Go)
test/                 # reserved for future cross-language drift tests
doc/                  # reserved for longer-form prose docs
tools/check_drift.py  # cross-language type drift guard
.github/workflows/    # CI: gofmt + go vet + go test + drift check
```

The TypeScript and Python SDK repos place their source under `src/` per
each language's idiomatic layout. Only `test/`, `doc/`, and `.github/`
are uniformly nested across all four repos; Go's source lives at the
module root because that's what makes `go get` + a default `import`
work without a path-suffix footgun.

## Develop

```sh
go test ./...
python3 tools/check_drift.py            # local sibling working dirs
python3 tools/check_drift.py --from-github  # fetch ts / python from main
```
