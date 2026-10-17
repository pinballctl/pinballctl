# Pinball CTL Manual

Pinball CTL is a complete control stack for modern homebrew pinball machines. It links a Raspberry Pi web platform with an ESP32 real-time controller so you can design, configure, test, and run your machine from one system.

At a high level:

- The Pi side gives you the management layer: UI modules, configuration, rules, diagnostics, sync, and deployment.
- The ESP side gives you the real-time layer: fast I/O, output execution, and hardware safety enforcement.
- The bridge ties both together with a structured protocol so behaviour is predictable and debuggable.

The result is a platform that is practical for day-to-day machine development, but also robust enough for real gameplay logic, safety-critical outputs, and long-running operation.

## Why It Is Powerful

Pinball CTL is designed to solve real integration pain:

- One place to manage hardware mapping, rules, events, lighting, and runtime state.
- A clear split between orchestration (Pi) and hard real-time control (ESP).
- Offline-first authoring: build and adjust configuration even when hardware is not currently connected.
- Visual preview workflows: test lighting and playfield behaviour before touching live machine outputs.
- Confident rollout: once validated, push your authored configuration to runtime in a controlled way.
- Safety-first behaviour for coils and high-power outputs.
- A web-based workflow so setup and maintenance can happen without custom tooling on every client machine.
- A system that can grow from simple cabinet tests to full game mode logic and scene-based lighting.

In short: you can move quickly without losing control of reliability and safety.

## Manual Structure

This manual is split into two main sections.

### 1. User Guides

User Guides are written for machine owners, operators, and builders who want clear instructions in plain English. They focus on:

- [Getting started](1-user-guide/getting-started.md) and first-time setup
- Using the platform confidently
- Common workflows and troubleshooting
- Operational best practice

### 2. Technical Documentation

Technical docs are for developers and advanced maintainers. They explain how the system works and why it is designed this way, including:

- Architecture and component responsibilities
- Bridge and protocol design
- Runtime models and behaviour rules
- Data formats, compilation paths, and sync lifecycle
- Implementation constraints and design trade-offs
