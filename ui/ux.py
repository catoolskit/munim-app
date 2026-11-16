"""Small helpers that make forms quicker: Enter moves to the next field, type-to-find in lists."""


def inner(w):
    """The real text widget inside a CTkEntry / CTkComboBox."""
    return getattr(w, "_entry", w)


class Autocomplete:
    """Type part of a name in a combo box; Enter/Tab completes it to the first match."""
    SKIP = {"Return", "Tab", "Up", "Down", "Left", "Right", "Escape", "Shift_L", "Shift_R",
            "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock"}

    def __init__(self, combo, names, on_pick=None):
        self.combo, self.names, self.on_pick = combo, list(names), on_pick
        combo._ac = self
        e = inner(combo)
        e.bind("<KeyRelease>", self._filter, add="+")
        e.bind("<FocusOut>", lambda _e: self.commit(), add="+")

    def set_names(self, names):
        self.names = list(names)
        self.combo.configure(values=self.names)

    def _filter(self, event):
        if event.keysym in self.SKIP:
            return
        text = self.combo.get().strip().lower()
        self.combo.configure(values=[n for n in self.names if text in n.lower()] or self.names)

    def commit(self):
        text = self.combo.get().strip()
        if text and text not in self.names:
            low = text.lower()
            hits = [n for n in self.names if n.lower().startswith(low)] or \
                   [n for n in self.names if low in n.lower()]
            if hits:
                self.combo.set(hits[0])
        self.combo.configure(values=self.names)
        if self.on_pick and self.combo.get() in self.names:
            self.on_pick(self.combo.get())


def chain_enter(widgets, on_last=None):
    """Pressing Enter in a field moves to the next one; after the last, calls on_last."""
    for i, w in enumerate(widgets):
        nxt = widgets[i + 1] if i + 1 < len(widgets) else None

        def go(_e, w=w, nxt=nxt):
            ac = getattr(w, "_ac", None)
            if ac:
                ac.commit()
            if nxt is not None:
                inner(nxt).focus_set()
            elif on_last:
                on_last()
            return "break"
        inner(w).bind("<Return>", go)


def focus_later(widget, ms=200):
    widget.after(ms, lambda: inner(widget).focus_set())
