# StatsBomb → Neo4j Schema Mapping

This document describes the canonical StatsBomb JSON event schema (fields we ingest) and the Neo4j data model used in this project. It is concise and technical so developers can reason about mappings, constraints, and common Cypher queries.

---

## 1. StatsBomb Events (canonical fields)
StatsBomb match JSON contains an `events` array where each element is an event object. The most important fields we ingest are:

- `event_uuid` / `id` (string): unique event identifier
- `type` (object): { `id`: int, `name`: string } — high-level type (Pass, Shot, Carry, Duel, Clearances, Substitution, etc.)
- `subtype` (object) (optional): finer-grained classification
- `minute`, `second` (int): timestamp within match
- `period` (int): half / extra-time period
- `team` (object): { `id`, `name` }
- `player` (object) (optional): { `id`, `name` }
- `location` (array of two floats) (optional): [x, y] start location (0-120 × 0-80 typical)
- `pass` (object) (for Pass events): may include `receiver` (player id/name), `length`, `angle`, `height`, `end_location`
- `shot` (object) (for Shot events): includes `outcome`, `xg`, `end_location` etc.
- `outcome` (object) (optional): { `id`, `name` }
- `positions` / `related_events` / `tags` (arrays): additional metadata (e.g., set-piece, head/foot, deflection)
- `possession` (not always explicit): possession boundaries are inferred by event sequence and team changes

Notes:
- Not every event has `player` (e.g., some team/period markers) — ingestion normalizes and skips non-event markers.
- Location coordinates are normalized by ingest; code expects floats under `location` or `pass.end_location`.

---

## 2. High-level Goals for Graph Mapping
- Represent events as first-class nodes with type-specific properties (Shot, Pass, Carry, etc.).
- Link events temporally to reconstruct sequences and to assemble possessions.
- Model `Player`, `Team`, and `Match` as nodes and connect events to these entities.
- Provide convenience nodes like `Possession` and `FormationSnapshot` to attach derived metadata.
- Maintain indexes and uniqueness constraints for fast lookups by `event_id`, `player_id`, and `match_id`.

---

## 3. Neo4j Schema (nodes & relationships)
Below is the concise model used by the codebase.

Nodes (labels) and primary properties:

- `:Match`
  - `match_id` (string) — unique
  - `competition`, `season`, `date` (optional metadata)

- `:Team`
  - `team_id` (int), `name` (string)

- `:Player`
  - `player_id` (int), `name` (string), `position` (optional)

- `:Event` (generic event node, type indicated in `event_type`)
  - `event_id` (string) — unique (from StatsBomb `id`/`event_uuid`)
  - `event_type` (string) — e.g. `Pass`, `Shot`, `Carry`, `Duel`
  - `minute` (int), `second` (int), `period` (int)
  - `timestamp_ms` (int) — optional normalized epoch/offset
  - `x` (float), `y` (float) — primary location (start)
  - `end_x`, `end_y` (float) — for passes/shots (if available)
  - `outcome` (string) — textual outcome when present
  - `xg` (float) — for shots (when available)
  - `raw` (map) — optional: raw JSON blob for debugging

- `:Possession`
  - `possession_id` (string)
  - `team_id` (int)
  - `start_event_id`, `end_event_id` (optional convenience props)
  - `start_time`, `end_time` (optional)
  - `event_count`, `pass_count`, `duration_s` (derived metrics)

- `:FormationSnapshot` (optional)
  - `snapshot_id`, `minute`, `period`, `team_id`, `players` (map of player->location)

Relationships (type and properties):

- `(:Match)-[:HAS_EVENT]->(:Event)`
  - Connects all events to the match

- `(:Team)-[:HAS_PLAYER]->(:Player)`
  - Team membership

- `(:Player)-[:PERFORMED]->(:Event)`
  - Performed/owned event (most events)

- `(:Event)-[:NEXT]->(:Event)`
  - Temporal ordering between consecutive events in the match timeline. Properties: `delta_ms` (optional)

- `(:Event)-[:PART_OF]->(:Possession)`
  - Assign event to derived possession node

- `(:Possession)-[:PRECEDES]->(:Possession)`
  - Temporal adjacency of possessions

- `(:Event)-[:ASSISTS]->(:Event)` (optionally)
  - Link related events (key pass → shot)

- `(:Event)-[:TO_PLAYER {role:'recipient'}]->(:Player)`
  - For pass/shot end recipients where explicit

- `(:Team)-[:PLAYED_MATCH]->(:Match)`
  - Match participation

Relationship properties commonly stored:
- `length`, `angle` (for pass relationships or in `Event`)
- `is_key_pass`, `is_corner`, `is_set_piece`, `is_deflection` (boolean flags)

---

## 4. Constraints & Indexes (example Cypher)
Create uniqueness and indexes used in the codebase for fast lookups.

```cypher
CREATE CONSTRAINT match_unique IF NOT EXISTS
  FOR (m:Match) REQUIRE m.match_id IS UNIQUE;

CREATE CONSTRAINT event_unique IF NOT EXISTS
  FOR (e:Event) REQUIRE e.event_id IS UNIQUE;

CREATE CONSTRAINT player_unique IF NOT EXISTS
  FOR (p:Player) REQUIRE p.player_id IS UNIQUE;

CREATE INDEX event_type_idx IF NOT EXISTS
  FOR (e:Event) ON (e.event_type);

CREATE INDEX event_time_idx IF NOT EXISTS
  FOR (e:Event) ON (e.minute, e.second);
```

---

## 5. Derived Data & Heuristics
We compute and persist a number of derived artifacts to support fast tactical queries:

- Possession detection: contiguous `Event` sequences where `team.id` is constant and possession switches when team changes or for restart events. We create a `:Possession` node and link events with `:PART_OF`.

- Pass network edges: aggregated `(:Player)-[:PASSED_TO {count, avg_length}] ->(:Player)` relationships computed per match or per half.

- Highlights & last-touch fallback: `get_highlights` uses heuristics to identify anomalies (long-ball chains, quick counters, xG mismatches) and — when the last touch is missing inside a possession (e.g., goalkeeper distribution) — falls back to the most recent prior `Event` across the timeline (`last_event`) to avoid missing last-touch data.

- Goal/shot linking: Shots link to preceding `Pass` via `:ASSISTS` when the pass `key_pass` tag or matching coordinates/time indicate an assisting action.

---

## 6. Example Cypher snippets (common queries)

- Find an event by id:
```cypher
MATCH (e:Event {event_id: $event_id}) RETURN e;
```

- Get possession chain for an event (events in same possession ordered):
```cypher
MATCH (p:Possession)-[:HAS_EVENT]->(e:Event {event_id: $event_id})
MATCH (p)-[:HAS_EVENT]->(ev:Event)
RETURN ev ORDER BY ev.minute, ev.second
```

- Get last touch for a possession (heuristic):
```cypher
MATCH (p:Possession)-[:HAS_EVENT]->(e:Event)
WITH p, e ORDER BY e.minute DESC, e.second DESC LIMIT 1
RETURN e
```

- Aggregate passing pairs (top N):
```cypher
MATCH (a:Player)-[r:PASSED_TO]->(b:Player)
WHERE r.match_id = $match_id
RETURN a.name AS passer, b.name AS recipient, r.count AS passes
ORDER BY r.count DESC LIMIT $n
```

---

## 7. Ingest notes (what we persist)
- Always persist `event_id`, `event_type`, `minute`, `second`, `team_id`, `player_id` (when present), `x/y` coordinates.
- For `Pass` events also persist `end_x`, `end_y`, `length`, `angle`, and `receiver` when present.
- For `Shot` events persist `outcome`, `xg`, and `end_location` when available.
- Save raw JSON under `Event.raw` only when `DEBUG` or `--save-raw` ingest flag is enabled.

---

## 8. Notes for Developers
- The ingestion pipeline (`src/db/ingest.py`) normalizes StatsBomb coordinates and computes possession boundaries; changes there must keep compatibility with the `:Event` properties listed above.
- When adding new derived nodes (e.g., `TransitionSegment`) include a migration step to compute and link existing events.
- Keep indexes & constraints synchronized with `schema.py`.

---