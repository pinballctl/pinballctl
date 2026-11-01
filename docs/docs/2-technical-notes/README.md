# Advanced Reference

Use this section when you need implementation contracts, runtime boundaries or development information. For first installation and everyday workflows, start with [Quick Start](../1-user-guide/0-quick-start.md) or [Detailed Setup](../1-user-guide/1-getting-started.md).

## Follow the implementation

1. Read [Architecture](1-architecture.md) and [App Layout](2-app-layout.md) for component responsibilities and source paths.
2. Follow [Bridge Event Flow](3-bridge-event-flow.md), then [Bridge Protocol](bridge-protocol.md) for event delivery and frames-only JSON transport.
3. Use [Event Dispatch Internals](event-manager.md) and [Modules API Surface](modules-api-surface.md) to locate the relevant runtime and API code.
4. Read [Development Platform](../3-build-notes/1-development-platform.md) for the development/test context and component-cost model.

**Expected result:** you can locate the responsible code without treating an internal API or roadmap as an end-user workflow. Verify details against the exact installed revision; this manual follows current committed main.

## Roadmap and safety

The [ESP Development Plan](ESP-Plan.md) describes goals and proposed implementation phases. It is not a list of shipped features. Preserve arming, watchdog, pulse/hold and fault requirements when working on the bridge or firmware. New serial commands must remain framed JSON; newline-delimited transport is not supported.

If an implementation detail disagrees with a running machine, record its revision and inspect the current code and logs before changing behaviour. See [Troubleshooting](../1-user-guide/26-troubleshooting.md) for user-level diagnosis.
