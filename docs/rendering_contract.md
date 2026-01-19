# Rendering Contract (64x32 RGB LED Matrix)

## Scope
This contract defines the rendering lifecycle for a 64x32 RGB LED matrix app with:
- a single backbuffer canvas,
- exactly one `SwapOnVSync` per frame,
- multiple scenes grouped into mode-based scene sets (including two scrolling text scenes),
- a mode switch between `default`, `flight`, and `off`,
- a shared data index for scene data.

## Definitions
- **Backbuffer**: the single canvas that all scenes draw into each frame.
- **Frame**: one full render cycle that ends with exactly one `SwapOnVSync`.
- **Scene**: a drawable unit that may have scheduled update/render work.
- **Scene set**: the collection of scenes eligible to run for a given mode.
- **Active mode**: one of `default`, `flight`, or `off`, selecting which scene set is eligible (if any).
- **Shared data index**: an integer pointer into shared data used by scenes.

## Rules (Enforceable)
1) **Swap Policy**  
   A frame MUST call `SwapOnVSync` exactly once if any scene drew during that frame (i.e., the backbuffer is dirty).  
   If no scene drew, the frame MUST NOT swap.

2) **Clear Ownership**  
   The frame controller (not scenes) MUST own clearing the backbuffer.  
   Scenes MUST NOT clear the full canvas.  
   Scenes MAY clear only the pixels they own if their effect requires local erasure.

3) **Full Clears**  
   A full clear MUST occur:
   - at app startup, before the first frame swap;
   - immediately after any mode switch;
   - immediately after any scene switch.
   Full clears MUST NOT be used for routine data updates (e.g., temperature/forecast refreshes).

4) **Scene Scheduling**  
   The controller MUST allow each scene to declare its own schedule (every frame, every N frames, or event-driven).  
   Schedules are a per-scene implementation detail, but MUST be deterministic and stable.

5) **Data Update Redraws**  
   When a scene updates its data on its own schedule, it MUST redraw only its owned region(s) and mark the frame dirty.  
   Data updates MUST NOT trigger a full clear.

6) **Post-Swap Redraw**  
   A `SwapOnVSync` replaces the backbuffer.  
   If the active scene set does not fully redraw the canvas every frame, the controller MUST full clear the backbuffer on the next frame, then all active scenes MUST redraw their owned regions (even if their data did not change).

7) **Scene Set Execution**  
   For each frame, the controller MUST:
   - compute the active mode;
   - select the active scene set within that mode;
   - run scheduled work for each eligible scene in that set;
   - call `SwapOnVSync`.
   No scene outside the active set may render in that frame.

8) **Scrolling Text Scenes**  
   There MUST be exactly two scrolling text scenes.  
   Each scrolling scene MUST:
   - update its scroll position in `update()`;
   - render only its own pixels in `render()`;
   - avoid full clears (rule 2).

9) **Flight Background Coverage**  
   Flight mode MUST include a background scene that redraws the full canvas every frame.  
   The background MUST render before other flight scenes.  
   This background establishes the base frame so stale pixels cannot reappear after swaps.

10) **Default Scene Ordering**  
    Default mode SHOULD render stable background widgets before dynamic widgets (e.g., date/temperature before clock ticks).  
    If ordering dependencies exist, they MUST be expressed via explicit scheduling order (not name sorting).

11) **Network Error Mode**  
    If a network error is detected, the controller MUST switch to a dedicated status scene set and pause default/flight rendering.  
    The status scene MUST clear the full canvas and render a clear error indicator.  
    When the error clears, the controller MUST resume the prior mode on the next frame.

12) **Mode Switch Semantics**  
   The active mode MAY change only at frame boundaries.  
   When a mode switch is detected, the controller MUST:
   - perform a full clear (rule 3);
   - reset per-mode scene timers;
   - reset any mode-scoped indices (including shared data index if applicable).
   The new mode takes effect on the next frame.

13) **Off Mode Behavior**  
   In `off` mode, the controller MUST render no scenes.  
   Each frame in `off` mode MUST full clear the backbuffer, then call `SwapOnVSync`.  
   `update()` and `render()` MUST NOT be called for any scene while in `off` mode.

14) **Shared Data Index Advancement**  
   The shared data index MUST be advanced by exactly one designated owner.  
   The owner MUST be the scrolling scene with the longest active text (by render width).  
   If there is a tie, the owner MUST be the bottom-most scrolling scene in the active mode.  
   The cadence MUST be scene-driven: the owner advances the index only when its active scroller wraps.  
   All other scenes MUST treat the index as read-only and MUST NOT modify it.

## Compliance
Any deviation from these rules is a contract violation. The controller is responsible for enforcement.
