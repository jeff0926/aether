/**
 * AETHER 2KB Edge Orchestrator
 * Discovers EDS slivers, connects to capsule SSE streams,
 * applies CSS Variable Patches (CVP), injects content into slots.
 *
 * Target: ≤2KB minified
 */
(function() {
  'use strict';

  // Configuration
  const RECONNECT_DELAY = 3000;
  const DEFAULT_REFRACTORY = 15000;

  // State
  const agents = {};
  const refractory = {};

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  function init() {
    // Discover all AETHER slivers in the DOM
    const slivers = document.querySelectorAll('[data-aether-agent]');
    slivers.forEach(el => {
      const id = el.dataset.aetherAgent;
      const endpoint = el.dataset.aetherEndpoint || `/api/stream/${id}`;
      const impulses = JSON.parse(el.dataset.aetherImpulses || '[]');

      agents[id] = { el, endpoint, source: null, impulses };

      // Setup impulse listeners
      setupImpulses(id, impulses);

      // Connect to SSE stream if auto-connect enabled
      if (el.dataset.aetherAutoconnect !== 'false') {
        connect(id);
      }
    });
  }

  // Connect to SSE stream
  function connect(id) {
    const agent = agents[id];
    if (!agent) return;

    // Close existing connection
    if (agent.source) {
      agent.source.close();
    }

    const source = new EventSource(agent.endpoint);
    agent.source = source;

    source.addEventListener('aether.css-delta', function(e) {
      try {
        const data = JSON.parse(e.data);
        applyDelta(agent.el, data);
      } catch(err) {
        console.warn('AETHER: parse error', err);
      }
    });

    source.onerror = function() {
      // EventSource auto-reconnects, but we track state
      agent.el.dataset.aetherConnected = 'false';
    };

    source.onopen = function() {
      agent.el.dataset.aetherConnected = 'true';
    };
  }

  // Apply CSS Variable Patch to target element
  function applyDelta(el, data) {
    // Use requestAnimationFrame for smooth updates
    requestAnimationFrame(function() {
      // Apply CSS variables (scoped to element, not :root)
      if (data.vars) {
        for (const [k, v] of Object.entries(data.vars)) {
          el.style.setProperty(k, v);
        }
      }

      // Inject content into named slots
      if (data.content !== null && data.content !== undefined) {
        const slots = el.querySelectorAll('[data-aether-slot]');
        slots.forEach(slot => {
          const name = slot.dataset.aetherSlot;
          if (name === 'content' || name === 'answer' || name === 'response') {
            // Use textContent for security (no innerHTML XSS)
            slot.textContent = data.content;
          }
        });
      }

      // Set phase as data attribute for CSS selectors
      if (data.phase) {
        el.dataset.aetherPhase = data.phase;
      }

      // Update metadata slots
      if (data.meta) {
        if (data.meta.aec_score !== null && data.meta.aec_score !== undefined) {
          const scoreSlot = el.querySelector('[data-aether-slot="confidence"]');
          if (scoreSlot) {
            scoreSlot.textContent = Math.round(data.meta.aec_score * 100) + '%';
          }
        }
        if (data.meta.agent) {
          const agentSlot = el.querySelector('[data-aether-slot="agent-name"]');
          if (agentSlot) {
            agentSlot.textContent = data.meta.agent;
          }
        }
      }

      // Set active flag
      el.dataset.aetherActive = 'true';

      // Dispatch custom event for external listeners
      el.dispatchEvent(new CustomEvent('aether:delta', { detail: data }));
    });
  }

  // Setup impulse routing
  function setupImpulses(id, impulses) {
    if (!impulses || !impulses.length) return;

    impulses.forEach(imp => {
      if (imp.source === 'dom') {
        const target = document.querySelector(imp.target || `[data-aether-agent="${id}"]`);
        if (!target) return;

        if (imp.event === 'intersection') {
          const obs = new IntersectionObserver(entries => {
            entries.forEach(entry => {
              if (entry.isIntersecting) {
                fireImpulse(id, imp);
              }
            });
          }, { threshold: imp.threshold || 0.5 });
          obs.observe(target);
        } else {
          target.addEventListener(imp.event, () => fireImpulse(id, imp));
        }
      } else if (imp.source === 'custom') {
        window.addEventListener(imp.event, (e) => fireImpulse(id, imp, e.detail));
      }
    });
  }

  // Fire an impulse with refractory period enforcement
  function fireImpulse(id, impulse, detail) {
    const now = Date.now();
    const agent = agents[id];
    if (!agent) return;

    const period = agent.el.dataset.aetherRefractory || DEFAULT_REFRACTORY;
    if (refractory[id] && (now - refractory[id]) < period) {
      return; // Still in refractory period
    }
    refractory[id] = now;

    // POST to query endpoint
    fetch(`/api/stream/${id}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: detail?.query || impulse.query || impulse.event,
        impulse: impulse
      })
    }).catch(err => console.warn('AETHER: impulse error', err));
  }

  // Expose public API
  window.aether = {
    // Manually fire a query to an agent
    fire: function(agentId, query) {
      fireImpulse(agentId, { source: 'api', event: 'manual' }, { query });
    },

    // Connect to an agent's SSE stream
    connect: connect,

    // Disconnect from an agent's SSE stream
    disconnect: function(agentId) {
      const agent = agents[agentId];
      if (agent && agent.source) {
        agent.source.close();
        agent.source = null;
        agent.el.dataset.aetherConnected = 'false';
      }
    },

    // Get all registered agents
    agents: function() {
      return Object.keys(agents);
    },

    // Apply a delta manually (for testing)
    applyDelta: function(agentId, data) {
      const agent = agents[agentId];
      if (agent) {
        applyDelta(agent.el, data);
      }
    }
  };
})();
