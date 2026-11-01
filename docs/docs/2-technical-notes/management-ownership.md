# Game and Ball ownership contract

The versioned contract is `pinballctl.game.registry`. Game/Ball editor options, request validation and condition fields derive from this contract. `utils/audit-management.py` checks editor/action parity, command-handler coverage and available wizard actions and produces a semantic identifier inventory. The pre-edit inventory is `docs/media/management-identifier-audit-before.json`, tied to baseline `cadd170b5934ec3ec9f1cb040893c0f559e8aaed`. The current JSON inventory is under `docs/media/management-identifier-audit.json`; source line numbers describe the audited checkout, not stable API locations.

## One owner per value

| Owner | Authoritative values | Other modules |
|---|---|---|
| Game | Session, credits/partial units, policy, players, turn ID, logical ball, extra balls/save | Read snapshots; submit typed requests |
| Ball | Sensor evidence, zone counts/confidence, estimated in-play, pending movements, alerts | Submit trusted observations; request/reconcile movements |
| Scoring | Per-player awards, combo state, multiplier, bonus finalisation, history/high scores | Run existing scoring configuration in the current committed turn |
| Rules | Custom flags/counters, trigger matching and reactions | Cannot write manager state or emit manager facts |
| ESP | Physical input observation, output execution, arming/recovery/watchdog/coil limits | Pi requests go through the existing framed safety path |
| Media/Audio/Lighting | Presentation | Consume committed events/read-model values |

Legacy game flags/counters and lifecycle aliases are rejected, not migrated. LCD `GAME_STATUS` and the player/ball/credit overlays are read models, not alternate state owners. A Rules list warning identifies obsolete beta records; saving, compilation and execution all reject unsupported ownership paths.

## Processes and transactions

```text
Bridge framed ingress -> bounded ordered host worker -> manager transaction
Web command API -------------------------------------> manager transaction
Rules typed request ---------------------------------> manager transaction

BEGIN IMMEDIATE -> check durable command ID -> validate policy
                -> update owned documents + Scoring calculation
                -> append result outbox -> store receipt -> COMMIT

One kernel-locked runtime coordinator -> timer checks + outbox dispatch
                                     -> existing EventBus / Event Manager / Rules
                                     -> presentation and published read model
```

SQLite's write transaction is the cross-process execution claim. There is no expiring lease around a transition: another process cannot execute the same request while the transaction is held; process death rolls it back. A repeated ID with identical request/authority returns its stored result; different data is rejected. Scoring and sensor observation use stable ingress identities, including physical source/sequence/ESP timestamp for physical retransmission.

The coordinator uses a per-installation POSIX file lock. Other web/bridge processes can submit transactions and read state; only the lock holder dispatches timers/outbox. Kernel lock release permits takeover after death, and takeover marks an interrupted game for reconciliation. No extra broker, network service or parallel event engine is introduced.

Bridge receive does not run database or scoring calculations. The existing host executor is ordered and bounded at 128 pending operations; exhaustion uses the existing overload/disarm path. Media effects cannot change score/player attribution. Raw scoring is applied before a drain changes the turn. Explicitly delayed score work carries the captured turn ID and is rejected after that turn.

## Turn finalisation

Scoring's `finalize_turn` applies the configured fixed bonus once for the turn ID. The same transaction records `BALL_TURN_ENDED`, resolves extra-ball/player/ball precedence and publishes the next `BALL_TURN_STARTED`. There is no asynchronous interval in which the next player is active but the prior bonus is unfinished. Game history/high scores commit once per game ID. Existing scoring award and combo calculations operate on each player's private scoring document; they do not keep a second game lifecycle.

## Delivery and physical side effects

State and result intent commit together. Outbox delivery is **at least once**, not exactly-once transport. Stable result IDs let Rules consume state actions once, scoring commands deduplicate and later delivery retry safely. Audit IDs and state versions are retained. Arbitrary third-party listeners must also implement idempotency; external presentation effects are not claimed to be crash-atomic.

A physical release is deliberately **not retried** after an uncertain send. A durable receipt is reserved before RPC; a crash can lose a send but cannot cause automatic re-fire. A fresh `GET_RUNTIME_CLOCK` response supplies ESP time for the existing 250 ms `RULE_ACTIONS` guard. Only a mapped, explicitly configured output/pulse is requested; existing recovery, arming and coil checks remain authoritative. Rejection, missing clock support, timeout or restart enters recovery rather than energising outputs. No automatic ball search, coil re-arm or retry loop is added.

Physical sensor frames carry `physical:true`; host `EVENT_FIRE` frames carry `synthetic:true`. Only trusted physical ingress drives bound coins/start inputs or physical observations. The generic Events API rejects reserved names and internal metadata. New firmware is required for this provenance distinction.

## Restart, restore and storage

`game/management.sqlite` contains separately owned documents, command receipts and committed outbox. Game, Ball and Scoring backups are logical partitions of this database. Restoring a partition stages a consistent SQLite copy, preserves unselected owner documents and publishes it through the existing restore journal/barrier. Physical evidence is invalidated, pending output/event work is cleared and an interrupted game enters recovery. Trusted coin/payment replay guards are unioned with existing guards so restoring an older balance cannot make the same settlement credit twice.

The restore barrier covers manager transactions and dispatch. Snapshots include durable credits/configuration and scoring data; they are not evidence of current physical occupancy. Configuration changes are limited to idle/ended state. Input watch compilation changes the Rules blob; deployment is explicit Sync Rules, with no automatic arming.

## Validation and limits

Tests cover multiple processes racing/retrying starts, process death with an uncommitted write, command schema/replay conflicts, coin accumulation/trust, per-player awards, late-turn rejection, save-window lifetime, extra-ball precedence, bonus/history finalisation, individual occupancy sensors, multiball drain estimates, movement timeout, one-shot guarded release, outbox state-action replay and restore reconciliation. Browser checks use an isolated installation; no live restore or output activation is performed.

Physical Pi/ESP latency, coin wiring, mechanical arrivals, USB reconnect timing, service supervision under load, power-loss/filesystem failure and screen-reader use remain target-machine validation. NFC/payment-provider integrations and mechanism-specific search/retry strategies are separate work. No unavailable wizard is advertised as a functioning mechanical driver.
