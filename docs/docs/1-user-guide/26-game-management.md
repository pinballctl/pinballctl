# Game Management

Game Management owns credits, players, logical turns, ball number, extra balls and ball-save policy. Scoring owns each player's score and bonus finalisation. Ball Management owns physical observations. Rules connects inputs and reactions using typed requests and read-only manager conditions.

<img src="./media/screenshot-feature-game.webp" data-source='{"url": "/login", "dark_mode": true, "settle_ms": 800, "click": [{"action": "type", "selector": "input[name=\"username\"]"}, {"action": "type", "selector": "input[name=\"password\"]"}, {"action": "click", "selector": "button[type=\"submit\"]", "wait_for": "[data-menu-toggle]"}], "next_url": "/game/"}' alt="Game Management player and turn overview" style="width:100%;height:auto;">

## Set up a game

Open **Game Management → Settings** while no game is running. Choose maximum players, balls per player, credits per player and free play. Changes are rejected during an active, paused or recovering game. Free play bypasses credit spending; it does not create fictitious credits.

Optionally select a mapped start input. Its active edge requests a new game, or adds a player when **Start button during a game** allows joining. Joining can be limited to the first logical ball, before first launch, or disabled. A rejected request does not spend credits. A successful player entry spends the configured credit cost atomically with the transition.

Under Advanced, configure accepted coin denominations as integer monetary units and map each coin input to its denomination. For example, with 100 units per credit, four 25-unit coin pulses produce one credit. The remaining partial units persist. Operator test credits and input simulation are disabled by default; enabling the test setting permits the explicitly labelled test controls.

**Save settings, then Sync Rules** to deploy the manager's input watches. These watches contain no output actions and are not editable gameplay rules. Configuration saves compile them into the existing framed Rules bundle; there is no automatic sync or arming. Update Pi and ESP firmware together: physical observations carry an explicit provenance marker, and controlled movement uses the firmware runtime-clock query.

## Play and monitor

The overview shows game status, current player, logical ball, credits and partial coin units. Players have independent scores, combo progress, multipliers and extra-ball counts. A turn waits in Preparing until shooter departure is observed. The manager then enters Ball Active.

With only shooter-departure and drain inputs, in-play count is an **estimate**. Drain confirms passage, not trough occupancy. A drain with no corresponding launch estimate requires reconciliation. Multiple observed departures increase the estimate; one drain does not end multiball while another ball remains or a movement is unresolved.

When play finishes, Scoring finalises the outgoing player's configured fixed end-of-turn bonus inside the same transaction as turn advancement. Extra balls take precedence over changing player. After all players finish, the next logical ball begins; after the last ball, the game ends and per-player high scores/history are recorded once. A delayed score explicitly associated with an earlier turn is rejected.

The ball-save window starts on the first launch of the turn. A saved drain keeps the same player and logical turn and waits for another physical launch. Relaunching does not extend the original window. An explicit **Activate ball save** request can start a new bounded window. No automatic launch is performed.

Pause and Resume control logical progression. Observations continue while paused; if a drain completes play, bonus finalisation and the next turn wait for explicit Resume. **End game** is an operator command, with confirmation. Ending a game does not remove physical balls: reconcile outstanding balls before starting again. None of these controls arms hardware.

## Rules boundaries

Use **Game Management** triggers for committed result events, **Game Management** conditions for read-only state, and manager actions for supported requests such as start, add player, extra ball and ball save. The manager may reject a request. Privileged credit/end/pause/resume controls are operator/adapter operations, not generic Rules actions.

Legacy writable game flags/counters and legacy ball/credit events are deliberately removed in this beta. Rules lists affected records with instructions to recreate them. Custom counters such as BUMPER_HITS remain supported. Generic Emit Event cannot forge manager result events; generic state actions cannot modify manager-owned state. The authoritative registry drives editor options and execution validation.

## Recovery and payment boundary

Runtime coordinator takeover, bridge restart, event overload and restored state require physical reconciliation for an interrupted game. The UI shows the reason. Use Ball Management to inspect and reconcile, then explicitly resume. Nothing automatically energises coils during recovery.

NFC can identify an input through existing Rules; identity alone is not payment. A verified payment adapter can submit a settlement through the trusted Python adapter interface with a stable settlement ID. Duplicate IDs cannot award credit again. No live payment-provider integration is included; generic event names or caller-supplied source strings cannot authorise credits.

Physical Pi/ESP timing, real coin inputs, actuators, service failover under load and screen-reader use still require target-machine validation. Desktop tests verify the software state transitions, transaction ownership and simulated workflows.
