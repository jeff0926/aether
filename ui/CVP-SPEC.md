# CVP — CSS-Var Patch Protocol Specification

**Version:** 1.0.0
**Status:** Stable

---

## 1. Overview

CVP (CSS-Var Patch Protocol) is a lightweight protocol for projecting agent cognitive state into any user interface via CSS custom property (CSS variable) updates. It enables real-time visual feedback of agent processing phases without coupling to any specific design system or component library.

**What CVP solves:**
- Decouples agent state from UI implementation
- Enables any design system to respond to agent phases
- Provides consistent timing for UI transitions across implementations
- Supports accessibility requirements (reduced motion, color contrast)

**What CVP is not:**
- A component library
- A rendering engine
- A replacement for existing design systems

---

## 2. Design System Agnosticism

CVP follows a **three-contract model**:

1. **State Contract** — The agent emits phase transitions with associated CSS variables
2. **Mapping Contract** — A pulse-map file translates phases to design-system-specific tokens
3. **Rendering Contract** — The UI applies CSS variables to pre-loaded components

The **pulse-map** is the only file that knows which design system is in use. The agent core never sees design system tokens directly.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Agent Core    │────▶│   Pulse Map     │────▶│   Design System │
│ (emits phases)  │     │ (maps to vars)  │     │ (applies vars)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## 3. Event Schema

### 3.1 CSS Delta Event

Emitted on phase transitions. Contains CSS variables to apply.

```json
{
  "type": "aether.css-delta",
  "id": "frame-a1b2c3d4e5f6",
  "ts": 1712345678901,
  "scope": "document",
  "vars": {
    "--kinetic-tempo": "200ms",
    "--surface-accent": "#FF9800",
    "--surface-opacity": "0.90"
  },
  "meta": {
    "phase": "deliberation",
    "capsule": "scholar-buffett-v1.0.0",
    "sequence": 42,
    "heartbeat": false,
    "reason": null
  }
}
```

**Field descriptions:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Event type identifier. Always `"aether.css-delta"` for delta events. |
| `id` | string | Unique frame identifier. Format: `"frame-{hash}"`. |
| `ts` | number | Unix timestamp in milliseconds. |
| `scope` | string | CSS selector or `"document"` for root-level application. |
| `vars` | object | CSS custom properties to apply. Empty object `{}` for heartbeats. |
| `meta.phase` | string | Current cognitive phase name. |
| `meta.capsule` | string | Identifier of the active capsule/agent. |
| `meta.sequence` | number | Monotonically increasing sequence number. |
| `meta.heartbeat` | boolean | `true` if this is a heartbeat event, `false` otherwise. |
| `meta.reason` | string\|null | Reason for special transitions (e.g., `"aec_failed_twice"`). |

### 3.2 State Snapshot Event

Emitted on client reconnection. Contains full current CSS state.

```json
{
  "type": "aether.state-snapshot",
  "scope": "document",
  "vars": {
    "--kinetic-tempo": "200ms",
    "--surface-accent": "#FF9800",
    "--surface-opacity": "0.90"
  },
  "meta": {
    "phase": "deliberation",
    "sequence": 42
  }
}
```

On receipt, clients should **replace** (not merge) their current CSS state.

---

## 4. Scope Model

The `scope` field determines where CSS variables are applied:

| Scope Value | Behavior |
|-------------|----------|
| `"document"` | Apply to `document.documentElement` (`:root`). Single-agent default. |
| CSS selector | Apply to matching element. Enables multi-agent isolation. |

**Single-agent deployment:**
```json
{ "scope": "document" }
```

**Multi-agent deployment:**
```json
{ "scope": "#agent-panel-1" }
{ "scope": "#agent-panel-2" }
```

---

## 5. Security

### 5.1 Namespace Validation

Clients MUST validate CSS variable names before application.

**Allowed namespaces:**
- `--kinetic-*` — Animation timing variables
- `--surface-*` — Visual surface variables
- `--aether-*` — Reserved for future AETHER extensions

**Rejected patterns:**
- `url(` — Prevents CSS injection via url() functions
- `--aether-inject*` — Reserved rejection pattern

### 5.2 Rate Limiting

Clients SHOULD enforce a maximum variables-per-frame limit to prevent DoS:

```javascript
const MAX_VARS_PER_FRAME = 50;
```

### 5.3 Server-Side Considerations

- Emit only from trusted agent processes
- Do not expose CVP endpoints to untrusted clients
- Consider authentication for production SSE streams

---

## 6. Transport

CVP events are transported as **Server-Sent Events (SSE)**.

### 6.1 SSE Format

```
event: message
id: frame-a1b2c3d4e5f6
data: {"type":"aether.css-delta",...}

```

### 6.2 HTTP Recommendations

| Protocol | Recommendation |
|----------|----------------|
| HTTP/2 | Recommended. Multiplexed streams, no connection limits. |
| HTTP/1.1 | Usable. Be aware of browser connection limits (6 per domain). |

### 6.3 Content Type

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

---

## 7. Heartbeat Protocol

Heartbeats signal liveness without state change.

### 7.1 Server Emission

- **Interval:** Every `HEARTBEAT_INTERVAL` seconds (default: 20)
- **Format:** CSS delta event with `vars: {}` and `meta.heartbeat: true`

```json
{
  "type": "aether.css-delta",
  "vars": {},
  "meta": {
    "phase": "deliberation",
    "heartbeat": true
  }
}
```

### 7.2 Client GHOST Detection

Clients maintain a watchdog timer:

- **Threshold:** `HEARTBEAT_INTERVAL × GHOST_MULTIPLIER` (default: 20 × 3 = 60 seconds)
- **Action:** If no event received within threshold, enter client-side GHOST state
- **Recovery:** Reset timer on any event receipt

---

## 8. Reconnection Protocol

### 8.1 Client Reconnection

On SSE reconnection, clients send the `Last-Event-ID` header with the last received event `id`.

### 8.2 Server Response

On reconnection with `Last-Event-ID`:
1. Emit `aether.state-snapshot` event with full current CSS state
2. Resume normal delta emission

### 8.3 Sequence Gap Handling

Clients track `meta.sequence`. On gap detection:
- Log warning for diagnostics
- Do not attempt replay
- Continue with new sequence

---

## 9. GHOST Protocol

GHOST (Grounded Hallucination or Speculative Termination) indicates unverifiable agent state.

### 9.1 Server-Initiated GHOST

Emitted when agent verification fails twice:

```json
{
  "type": "aether.css-delta",
  "vars": { "--surface-accent": "#9E9E9E" },
  "meta": {
    "phase": "ghost",
    "reason": "aec_failed_twice"
  }
}
```

### 9.2 Client-Initiated GHOST

Triggered by heartbeat timeout. Apply local ghost vars from pulse-map.

### 9.3 Reason Field Values

| Reason | Meaning |
|--------|---------|
| `null` | Normal phase transition |
| `"aec_failed_twice"` | Agent verification failed after retry |
| `"new_query"` | New query arriving during recovery |
| `"heartbeat_timeout"` | Client-side GHOST (documentation only) |

### 9.4 Recovery Flow

```
ghost → recovering → discovery → (normal flow)
```

---

## 10. Multi-Agent Guidance

### 10.1 Scope Isolation

Each agent MUST use a unique `scope` value:

```json
// Agent 1
{ "scope": "#agent-alpha" }

// Agent 2
{ "scope": "#agent-beta" }
```

### 10.2 Parallel Agents

Multiple agents can emit concurrently to different scopes. Each agent maintains its own sequence counter.

### 10.3 Last-Write-Wins Warning

If multiple agents target the same scope, last-write-wins applies. This is usually a configuration error. Consider:
- Using unique scopes per agent
- Implementing client-side arbitration if needed

---

## 11. Design System Integration Guide

### 11.1 The Three Contracts

1. **Implement a pulse-map** — Map AETHER phases to your design system tokens
2. **Load components** — Pre-load all components that respond to CSS variables
3. **Apply variables** — Use CSS custom property inheritance

### 11.2 Pulse-Map Override

Create `pulse-map.json` in your project:

```json
{
  "deliberation": {
    "--kinetic-tempo": "var(--fiori-animation-fast)",
    "--surface-accent": "var(--sapHighlightColor)"
  }
}
```

### 11.3 ARIA Requirements

- Use `aria-busy="true"` during active phases (discovery, deliberation, validation)
- Use `aria-busy="false"` on delivery
- Announce GHOST state to screen readers: `"Agent response could not be verified"`

### 11.4 Prefers-Reduced-Motion

When `prefers-reduced-motion: reduce` is active:
- **Remove:** `--kinetic-tempo`, `--kinetic-scale`
- **Keep:** `--surface-accent`, `--surface-opacity` (state communication, not decoration)

```css
@media (prefers-reduced-motion: reduce) {
  :root {
    --kinetic-tempo: 0ms !important;
    --kinetic-scale: 1.0 !important;
  }
}
```

---

## 12. Adapter Pattern

CVP is the internal protocol. Adapters translate outward to other ecosystems.

### 12.1 Adapter Location

Adapters live **outside** the AETHER core repository:
- `aether-adapters/ag-ui/` — AG-UI protocol adapter
- `aether-adapters/langgraph/` — LangGraph streaming adapter

### 12.2 Adapter Contract

An adapter:
1. Consumes CVP events
2. Transforms to target protocol format
3. Emits in target protocol

Adapters MUST NOT modify AETHER core behavior.

---

## Appendix A: Phase Reference

| Phase | Description | Default Accent |
|-------|-------------|----------------|
| `discovery` | Distill + Augment running | Blue (#2196F3) |
| `deliberation` | Generate running (LLM thinking) | Orange (#FF9800) |
| `validation` | Review/AEC running | Purple (#9C27B0) |
| `delivery` | Pipeline complete, response ready | Green (#4CAF50) |
| `ghost` | Verification failed, response unverifiable | Gray (#9E9E9E) |
| `recovering` | New query after GHOST | Blue (#2196F3) |
| `alive` | Heartbeat only, no state change | (current phase) |

---

## Appendix B: Default CSS Variables

| Variable | Purpose | Discovery | Deliberation | Validation | Delivery | Ghost |
|----------|---------|-----------|--------------|------------|----------|-------|
| `--kinetic-tempo` | Animation duration | 400ms | 200ms | 100ms | 0ms | 600ms |
| `--kinetic-scale` | Transform scale | 1.0 | 1.0 | 1.0 | 1.0 | 0.95 |
| `--surface-accent` | Primary accent color | #2196F3 | #FF9800 | #9C27B0 | #4CAF50 | #9E9E9E |
| `--surface-opacity` | Surface transparency | 0.85 | 0.90 | 0.95 | 1.0 | 0.60 |

---

## Appendix C: Example Implementation

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    :root {
      --kinetic-tempo: 400ms;
      --surface-accent: #2196F3;
      --surface-opacity: 0.85;
    }

    .agent-panel {
      transition: all var(--kinetic-tempo) ease-out;
      border-color: var(--surface-accent);
      opacity: var(--surface-opacity);
    }
  </style>
</head>
<body>
  <div class="agent-panel">Agent Response</div>

  <script src="client.js"></script>
  <script>
    const aether = AetherUI.connect({
      url: '/aether/stream',
      onPhaseChange: (phase) => {
        console.log('Phase:', phase);
      }
    });
  </script>
</body>
</html>
```
