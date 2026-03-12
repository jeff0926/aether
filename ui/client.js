/**
 * AETHER UI Client - Reference implementation for CVP (CSS-Var Patch Protocol)
 *
 * This is a drop-in vanilla JavaScript client for consuming AETHER UI projection
 * events over Server-Sent Events (SSE). No framework required. No build step.
 *
 * Usage:
 *   const aether = AetherUI.connect({
 *     url: '/aether/stream',
 *     scope: 'document',
 *     ghostThreshold: 60000,
 *     onPhaseChange: (phase) => console.log('Phase:', phase),
 *     onGhost: (reason) => console.log('GHOST:', reason),
 *     onRecover: () => console.log('Recovered')
 *   });
 *
 *   aether.disconnect();
 */

const AetherUI = (function() {
  'use strict';

  // Security: Allowed CSS variable namespace patterns
  const ALLOWED_NAMESPACES = [/^--kinetic-/, /^--surface-/, /^--aether-/];

  // Security: Rejected patterns (prevent injection)
  const REJECTED_PATTERNS = [/url\(/, /^--aether-inject/];

  // Security: Maximum variables per frame (prevent DoS)
  const MAX_VARS_PER_FRAME = 50;

  /**
   * Validate a CSS variable key-value pair for security.
   * @param {string} key - CSS variable name
   * @param {string} value - CSS variable value
   * @returns {boolean} True if allowed
   */
  function isAllowedVar(key, value) {
    // Check rejected patterns first
    if (REJECTED_PATTERNS.some(p => p.test(key) || p.test(String(value)))) {
      console.warn('[AetherUI] Rejected var:', key);
      return false;
    }
    // Check allowed namespaces
    return ALLOWED_NAMESPACES.some(p => p.test(key));
  }

  /**
   * Check if prefers-reduced-motion is active.
   * @returns {boolean}
   */
  function prefersReducedMotion() {
    return window.matchMedia &&
           window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  /**
   * Filter vars based on prefers-reduced-motion.
   * Removes kinetic vars, keeps surface vars (communicate state, not decoration).
   * @param {Object} vars - CSS variables object
   * @returns {Object} Filtered vars
   */
  function filterForReducedMotion(vars) {
    if (!prefersReducedMotion()) return vars;

    const filtered = {};
    for (const [key, value] of Object.entries(vars)) {
      // Keep surface vars (state communication)
      // Remove kinetic vars (animation/motion)
      if (!key.startsWith('--kinetic-')) {
        filtered[key] = value;
      }
    }
    return filtered;
  }

  /**
   * Connect to an AETHER UI stream.
   * @param {Object} options - Connection options
   * @returns {Object} Connection handle with disconnect()
   */
  function connect(options = {}) {
    const {
      url,
      scope = 'document',
      ghostThreshold = 60000,
      pulseMap = null,
      onPhaseChange = () => {},
      onGhost = () => {},
      onRecover = () => {}
    } = options;

    if (!url) throw new Error('[AetherUI] url is required');

    let eventSource = null;
    let lastSequence = 0;
    let ghostTimer = null;
    let pendingVars = {};
    let rafScheduled = false;
    let currentPhase = null;
    let isGhost = false;

    // Get target element for CSS vars
    const target = scope === 'document'
      ? document.documentElement
      : document.querySelector(scope);

    if (!target) {
      console.warn('[AetherUI] Scope not found:', scope);
    }

    /**
     * Apply pending CSS variables in a single rAF callback (coalescing).
     */
    function applyVars() {
      rafScheduled = false;
      if (!target) return;

      const vars = filterForReducedMotion(pendingVars);
      let count = 0;

      for (const [key, value] of Object.entries(vars)) {
        if (count >= MAX_VARS_PER_FRAME) {
          console.warn('[AetherUI] Max vars per frame exceeded');
          break;
        }
        if (isAllowedVar(key, value)) {
          target.style.setProperty(key, value);
          count++;
        }
      }

      pendingVars = {};
    }

    /**
     * Schedule CSS variable application via rAF.
     * @param {Object} vars - CSS variables to apply
     */
    function scheduleApply(vars) {
      Object.assign(pendingVars, vars);
      if (!rafScheduled) {
        rafScheduled = true;
        requestAnimationFrame(applyVars);
      }
    }

    /**
     * Reset GHOST watchdog timer.
     */
    function resetGhostTimer() {
      if (ghostTimer) clearTimeout(ghostTimer);
      ghostTimer = setTimeout(() => {
        if (!isGhost) {
          isGhost = true;
          onGhost('heartbeat_timeout');
          // Apply ghost vars from pulse map if available
          if (pulseMap && pulseMap.ghost) {
            scheduleApply(pulseMap.ghost);
          }
        }
      }, ghostThreshold);
    }

    /**
     * Handle incoming SSE event.
     * @param {MessageEvent} event - SSE message event
     */
    function handleEvent(event) {
      resetGhostTimer();

      let data;
      try {
        data = JSON.parse(event.data);
      } catch (e) {
        console.warn('[AetherUI] Invalid JSON:', e);
        return;
      }

      // Sequence gap detection
      if (data.meta && data.meta.sequence) {
        const seq = data.meta.sequence;
        if (lastSequence > 0 && seq > lastSequence + 1) {
          console.warn('[AetherUI] Sequence gap:', lastSequence, '->', seq);
        }
        lastSequence = seq;
      }

      // Handle state snapshot (full replace on reconnect)
      if (data.type === 'aether.state-snapshot') {
        if (target) {
          // Clear pending and apply full state
          pendingVars = {};
          scheduleApply(data.vars || {});
        }
        if (data.meta && data.meta.phase) {
          currentPhase = data.meta.phase;
          onPhaseChange(currentPhase);
        }
        return;
      }

      // Handle css-delta events
      if (data.type === 'aether.css-delta') {
        // Check for recovery from GHOST
        if (isGhost && data.meta && data.meta.phase !== 'ghost') {
          isGhost = false;
          onRecover();
        }

        // Apply CSS vars
        if (data.vars && Object.keys(data.vars).length > 0) {
          scheduleApply(data.vars);
        }

        // Phase change callback
        if (data.meta && data.meta.phase && data.meta.phase !== currentPhase) {
          currentPhase = data.meta.phase;
          onPhaseChange(currentPhase);

          // Handle GHOST phase
          if (currentPhase === 'ghost') {
            isGhost = true;
            onGhost(data.meta.reason || 'unknown');
          }
        }
      }
    }

    /**
     * Handle SSE errors and reconnection.
     */
    function handleError() {
      console.warn('[AetherUI] Connection error, will reconnect...');
      // EventSource auto-reconnects with Last-Event-ID header
    }

    // Create EventSource connection
    eventSource = new EventSource(url);
    eventSource.onmessage = handleEvent;
    eventSource.onerror = handleError;

    // Start GHOST watchdog
    resetGhostTimer();

    // Return connection handle
    return {
      /**
       * Disconnect from the stream.
       */
      disconnect() {
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
        if (ghostTimer) {
          clearTimeout(ghostTimer);
          ghostTimer = null;
        }
      },

      /**
       * Get current phase.
       * @returns {string|null}
       */
      get currentPhase() {
        return currentPhase;
      },

      /**
       * Check if in GHOST state.
       * @returns {boolean}
       */
      get isGhost() {
        return isGhost;
      }
    };
  }

  // Public API
  return { connect };
})();

// Export for module systems (optional)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = AetherUI;
}
