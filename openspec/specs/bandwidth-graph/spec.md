# bandwidth-graph Specification

## Purpose

Defines missions, items, the seven item states and the recorded edges between them, the slot cap, stall arithmetic, the override limit, and the rule that only a human pulls work into their own time.

## Requirements

### Requirement: Missions
A context SHALL hold a list of missions. `fw mission add <slug> --title TEXT` SHALL append a `mission_created` event with `slug` (kebab-case string, unique in the context) and `title` (string). `fw mission list` SHALL print every mission with its count of items per state.

#### Scenario: Add mission
- **WHEN** `fw mission add ship-fw --title "Ship attention-firewall 1.0"` runs
- **THEN** a `mission_created` event is appended and `fw mission list` shows `ship-fw`

#### Scenario: Duplicate slug
- **WHEN** `fw mission add ship-fw` runs and `ship-fw` already exists
- **THEN** the command is refused with exit code 3 and nothing is written

#### Scenario: Invalid slug
- **WHEN** `fw mission add "Ship FW"` runs
- **THEN** the command is refused as a usage error with exit code 2

### Requirement: Item creation
`fw add TITLE [--mission SLUG]` SHALL append an `item_created` event with `id` (integer, 1 for the first item and increasing by 1), `title` (string), `mission` (string slug or null), and SHALL place the item in state `holding`. A mission given at creation SHALL exist. `fw map <id> <slug>` SHALL append an `item_mapped` event setting the item's mission; it SHALL be allowed in any non-terminal state.

#### Scenario: Add without mission
- **WHEN** `fw add "Review the Q4 deck"` runs
- **THEN** an `item_created` event with `mission: null` is appended and the item is in `holding`

#### Scenario: Add with unknown mission
- **WHEN** `fw add "x" --mission nope` runs and no mission `nope` exists
- **THEN** the command exits with code 4 and nothing is written

#### Scenario: Map later
- **WHEN** `fw map 1 ship-fw` runs on a holding item with no mission
- **THEN** an `item_mapped` event is appended and the item's mission is `ship-fw`

### Requirement: Item states and edges
Every item SHALL be in exactly one of: `holding`, `active`, `stalled`, `waiting`, `delegated`, `dropped`, `done`. `dropped` and `done` are terminal. Every state change SHALL be recorded as one `item_transitioned` event with `id`, `edge`, `from`, `to`, and, when the edge is `pull`, `override`, or `resume`, `until` (ISO 8601 date or null). The permitted edges are exactly:

| edge | from | to |
|---|---|---|
| pull | holding | active |
| override | holding | active |
| done | active, stalled, delegated | done |
| drop | holding, active, stalled, waiting, delegated | dropped |
| delegate | holding, active, stalled, waiting | delegated |
| wait | active, stalled | waiting |
| resume | waiting, stalled | active |
| stall | active | stalled |

Any command that would produce an edge not in this table SHALL be refused with exit code 3 and SHALL write nothing.

#### Scenario: Valid edge
- **WHEN** `fw done 1` runs on an active item
- **THEN** an `item_transitioned` event with `edge: done`, `from: active`, `to: done` is appended

#### Scenario: Invalid edge
- **WHEN** `fw done 1` runs on a holding item
- **THEN** the command reports that `done` is not permitted from `holding`, exits with code 3, and writes nothing

#### Scenario: Terminal state
- **WHEN** any transition command targets a `done` or `dropped` item
- **THEN** the command exits with code 3 and writes nothing

### Requirement: Slot cap on pull
`active` and `stalled` items SHALL each occupy one slot. `waiting`, `delegated`, and `holding` items SHALL occupy none. `fw pull <id> --until DATE` SHALL be refused with exit code 3 when the number of occupied slots equals or exceeds `slot_cap`, or when the item has no mission. `--until` SHALL be required on `pull` and `override` and optional on `resume`. `fw resume` from `waiting` SHALL be subject to the same slot check; from `stalled` it SHALL not, because the item already occupies a slot.

#### Scenario: Pull into free slot
- **WHEN** `fw pull 1 --until 2026-10-01` runs, item 1 is holding with a mission, and 2 of 3 slots are occupied
- **THEN** item 1 becomes `active`, the event records `until: 2026-10-01`, and 3 slots are occupied

#### Scenario: Pull into full column
- **WHEN** `fw pull 4 --until 2026-10-01` runs and 3 of 3 slots are occupied
- **THEN** the command reports the column is full, exits with code 3, and writes nothing

#### Scenario: Pull without mission
- **WHEN** `fw pull 2 --until 2026-10-01` runs and item 2 has `mission: null`
- **THEN** the command reports that the item is not mapped to a mission, exits with code 3, and writes nothing

#### Scenario: Wait frees a slot
- **WHEN** `fw wait 1` runs on an active item with 3 of 3 slots occupied
- **THEN** item 1 is `waiting` and 2 slots are occupied

#### Scenario: Resume from waiting into full column
- **WHEN** `fw resume 1` runs on a waiting item and 3 of 3 slots are occupied
- **THEN** the command exits with code 3 and writes nothing

### Requirement: Pull is a human decision
The edges `pull`, `override`, and `resume` commit the human's time. When the actor is `agent:<name>`, these edges SHALL be refused with exit code 3 unless the invocation includes `--human-allowed`, in which case the event SHALL carry `human_allowed: true`. Events from a `human` actor SHALL not carry `human_allowed`. All other edges SHALL be permitted to any actor.

#### Scenario: Agent pull refused
- **WHEN** `fw pull 1 --until 2026-10-01 --actor agent:claude` runs
- **THEN** the command reports that pull requires a human, exits with code 3, and writes nothing

#### Scenario: Agent pull with permission
- **WHEN** `fw pull 1 --until 2026-10-01 --actor agent:claude --human-allowed` runs and the graph rules pass
- **THEN** the event has `actor: agent:claude` and `human_allowed: true`

#### Scenario: Agent drop permitted
- **WHEN** `fw drop 1 --actor agent:claude` runs on a holding item
- **THEN** the item is `dropped` and the event has `actor: agent:claude`

### Requirement: Override bypasses the cap and is limited
`fw override <id> --until DATE` SHALL move a holding item with a mission to `active` even when slots are full, recording `edge: override`. Occupied slots MAY then exceed `slot_cap` and `status` SHALL show the true count. An item's override count is the number of its `override` events. When an item's override count exceeds 2, every edge except `delegate` and `drop` SHALL be refused with exit code 3.

#### Scenario: Override into full column
- **WHEN** `fw override 4 --until 2026-10-01` runs with 3 of 3 slots occupied
- **THEN** item 4 is `active` and status reports 4 slots occupied of a cap of 3

#### Scenario: Override without mission
- **WHEN** `fw override 4 --until 2026-10-01` runs and item 4 has no mission
- **THEN** the command exits with code 3 and writes nothing

#### Scenario: Third override locks the item
- **WHEN** item 4 has 3 `override` events and `fw done 4` runs
- **THEN** the command reports that only `delegate` or `drop` remain, exits with code 3, and writes nothing

#### Scenario: Locked item can be dropped
- **WHEN** item 4 has 3 `override` events and `fw drop 4` runs
- **THEN** item 4 is `dropped`

### Requirement: Stall by timestamp arithmetic
Before executing any command, the tool SHALL evaluate every `active` item against `now`. If the item's most recent event is older than `stall_after_days` days at `now`, the tool SHALL append an `item_transitioned` event with `edge: stall`, `actor: system`, and `ts` equal to `now`. `now` SHALL default to the current UTC time and SHALL be overridable by the global `--now TIMESTAMP` option. The stall decision SHALL use only timestamps; no other input may influence it.

#### Scenario: Stall after threshold
- **WHEN** item 1 became active on 2026-09-01, `stall_after_days` is 7, and `fw status --now 2026-09-09T00:00:00Z` runs
- **THEN** an `item_transitioned` event with `edge: stall` and `actor: system` is appended and item 1 shows as `stalled`

#### Scenario: Not yet stalled
- **WHEN** item 1 became active on 2026-09-01 and `fw status --now 2026-09-07T00:00:00Z` runs
- **THEN** no event is appended and item 1 is `active`

#### Scenario: Long absence replayed
- **WHEN** two items became active on 2026-09-01 and the next command runs with `--now 2026-09-20T00:00:00Z`
- **THEN** both receive a `stall` event in a single invocation

#### Scenario: Activity resets the clock
- **WHEN** item 1 became active on 2026-09-01, `fw map 1 ship-fw` ran on 2026-09-06, and `fw status --now 2026-09-10T00:00:00Z` runs
- **THEN** item 1 is still `active`

### Requirement: Status and the honest number
`fw status` SHALL print the Active column (active and stalled items, with `until`), the Holding column (holding items), the counts of waiting and delegated items, `slots_used`, `slot_cap`, `slots_free` (never below 0), and `next_open`: `now` if `slots_free` is greater than 0, otherwise the earliest `until` among occupied items, or null if none has one.

#### Scenario: Free slot
- **WHEN** 2 of 3 slots are occupied
- **THEN** `slots_free` is 1 and `next_open` equals `now`

#### Scenario: Full column with dates
- **WHEN** 3 of 3 slots are occupied with `until` values 2026-10-01, 2026-09-20, and 2026-11-15
- **THEN** `slots_free` is 0 and `next_open` is 2026-09-20

#### Scenario: Overridden column
- **WHEN** 4 items occupy slots and `slot_cap` is 3
- **THEN** `slots_used` is 4 and `slots_free` is 0
