# agent-sdk-protocol

[![Go Reference](https://pkg.go.dev/badge/github.com/postgrip-io/agent-sdk-protocol.svg)](https://pkg.go.dev/github.com/postgrip-io/agent-sdk-protocol)
[![CI](https://github.com/postgrip-io/agent-sdk-protocol/actions/workflows/ci.yml/badge.svg)](https://github.com/postgrip-io/agent-sdk-protocol/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/postgrip-io/agent-sdk-protocol?label=release&color=2563EB)](https://github.com/postgrip-io/agent-sdk-protocol/releases)
[![License](https://img.shields.io/github/license/postgrip-io/agent-sdk-protocol?color=2563EB)](LICENSE)

Wire-format types and Ed25519 task-result signing for the PostGrip Agent
runtime service. **Single source of truth** for the runtime contract:
`agent-sdk-go` imports it directly, the `postgrip-web` runtime imports
it directly, and `agent-sdk-typescript` / `agent-sdk-python` mirror the
same shapes. `tools/check_drift.py` fails CI when the three language
type definitions diverge.

## Customer SDKs

This package is **not** intended to be imported directly by application
code. It's the internal wire contract; consume it through one of the
SDKs that wraps it:

- [`agent-sdk-go`](https://github.com/postgrip-io/agent-sdk-go)
- [`agent-sdk-typescript`](https://github.com/postgrip-io/agent-sdk-typescript)
- [`agent-sdk-python`](https://github.com/postgrip-io/agent-sdk-python)
