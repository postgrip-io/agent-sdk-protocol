# agent-sdk-protocol

Wire-format types and Ed25519 task-result signing for the PostGrip Agent
runtime service. **Single source of truth** for the runtime contract:
`agent-sdk-go` imports it directly, the `postgrip-web` runtime imports
it directly, and `agent-sdk-typescript` / `agent-sdk-python` mirror the
same shapes (with a planned CI drift guard).

## Install

```sh
go get github.com/postgrip-io/agent-sdk-protocol/src
```

```go
import protocol "github.com/postgrip-io/agent-sdk-protocol/src"

t := protocol.Task{...}
```

The package files live under `src/` to keep this repo's layout
consistent with the sibling SDK repos (`agent-sdk-go`,
`agent-sdk-typescript`, `agent-sdk-python`). Go's `package protocol`
declaration means consumer code references `protocol.Task` etc. — only
the import path picks up the `/src` segment.

## Layout

```text
src/                  # Go package "protocol" — types + signing + tests
test/                 # reserved for future cross-language drift tests
doc/                  # reserved for longer-form prose docs
.github/workflows/    # CI: gofmt + go vet + go test
```

## Develop

```sh
go test ./src/...
```
