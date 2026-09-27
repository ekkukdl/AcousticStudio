# -*- coding: utf-8 -*-
"""
Undo/Redo state management for Acoustic Control Studio.

Extracted from AcousticStudioMain.push_state / undo / redo methods.
Pure Python — no Qt dependency required.
"""

from __future__ import annotations


class StateManager:
    """Manages undo/redo state stacks.

    Stores snapshots of application state (as dicts) and provides
    push / undo / redo / clear operations with a configurable maximum
    stack depth.
    """

    def __init__(self, max_undo: int = 20):
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []
        self._max_undo = max_undo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def push(self, state: dict) -> None:
        """Push a new state snapshot.

        Only pushes if *state* differs from the most recent entry on the
        undo stack.  Clears the redo stack on every push.
        """
        # Only push if different from last state
        if not self.undo_stack or self.undo_stack[-1] != state:
            self.undo_stack.append(state)
            self.redo_stack.clear()

            # limit stack size
            if len(self.undo_stack) > self._max_undo:
                self.undo_stack.pop(0)

    def undo(self, current_state: dict) -> dict | None:
        """Return the previous state, or ``None`` if nothing to undo.

        *current_state* is the live application state at the moment the
        user requests an undo.  If it differs from the top of the undo
        stack it is pushed first so that no work is lost.
        """
        if len(self.undo_stack) < 1:
            return None

        # If the current live state differs from what's on top, capture it
        if self.undo_stack[-1] != current_state:
            self.undo_stack.append(current_state)
            self.redo_stack.clear()

        if len(self.undo_stack) > 1:
            current = self.undo_stack.pop()
            self.redo_stack.append(current)
            return self.undo_stack[-1]

        return None

    def redo(self) -> dict | None:
        """Return the next (redo) state, or ``None`` if nothing to redo."""
        if self.redo_stack:
            next_state = self.redo_stack.pop()
            self.undo_stack.append(next_state)
            return next_state
        return None

    def clear(self) -> None:
        """Discard all undo and redo history."""
        self.undo_stack.clear()
        self.redo_stack.clear()
