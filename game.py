"""
Classic UNO rules for 4 seats, as pure logic (no camera, no drawing).

The camera only sees cards landing on the discard pile, not who played them,
so the engine assumes everyone plays in turn order. rules.md lists the rules
and the exact state change each one makes here.

Every method returns a list of Event(kind, text). Kinds:
  "info", "start" (starting card accepted), "play", "warn" (illegal but recorded),
  "reject" (illegal, refused), "draw" (someone picks up cards), "penalty" (forgot UNO),
  "uno", "uno_due", "unsure" (symbol not read), "win"
"""
from collections import namedtuple

import config as C

Event = namedtuple("Event", "kind text")

COLOURS = ("red", "yellow", "green", "blue")
WILDS = ("wild", "wild4")


def card_kind(card):
    """'wild4', 'wild', a number/action symbol, or None if the symbol was not read."""
    if card.symbol in WILDS:
        return card.symbol
    if card.colour == "wild":
        return "wild"           # black card with an unread symbol: treat it as a plain wild
    return card.symbol


class Game:
    def __init__(self):
        self.names = list(C.SEAT_NAMES)
        self.hands = [C.START_HAND] * len(self.names)
        self.current = C.FIRST_SEAT
        self.direction = 1          # +1 = P1 -> P2 -> P3 -> P4, -1 = the other way
        self.colour = None          # colour to match; None after a wild until the next card names it
        self.top = None             # top card of the discard pile
        self.pending_draw = None    # (seat, n): reminder for the HUD that this seat must pick up n cards
        self.uno_watch = None       # seat that just went down to 1 card; checked when the next player acts
        self.called = set()         # seats that have called UNO
        self.uno_since = None       # time uno_watch went down to 1 card (for the UNO? countdown)
        self.winner = None
        self.started = False
        self.unsure = False         # last card's symbol was not read (HUD shows "?" until the next action)
        self.log = []

    @property
    def colour_unknown(self):
        return self.started and self.colour is None

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    def name(self, seat):
        return self.names[seat]

    def seat_after(self, seat, steps=1):
        return (seat + steps * self.direction) % len(self.hands)

    def _say(self, events, kind, text):
        self.log.append(text)
        events.append(Event(kind, text))

    def _give(self, seat, n):
        self.hands[seat] += n
        self.called.discard(seat)   # more than one card again: a new UNO call is needed later

    def _to_play(self, events):
        self._say(events, "info", f"{self.name(self.current)} to play")

    def _check_uno(self, events):
        """The next player is acting now: catch whoever is on 1 card without having called UNO."""
        seat, self.uno_watch, self.uno_since = self.uno_watch, None, None
        if seat is None or seat in self.called or self.hands[seat] != 1:
            return
        if not C.UNO_PENALTY:
            self._say(events, "info", f"{self.name(seat)} forgot UNO (penalty off)")
            return
        n = C.UNO_PENALTY_CARDS
        self._give(seat, n)
        self.pending_draw = (seat, n)
        self._say(events, "penalty", f"{self.name(seat)} forgot UNO, +{n} -> {self.hands[seat]} cards")

    def _note_unsure(self, events, card):
        """An unread symbol is played as a number / plain wild. Say so, so a missed action can be fixed."""
        self.unsure = card.symbol is None and not card.fake
        if self.unsure:
            self._say(events, "unsure", f"symbol of {card} not read: if it was an action card "
                                        f"press Z then enter it with 1-4")

    def _illegal(self, card, kind):
        """Why this card may not be played on the top card, or None if it may."""
        if kind in WILDS:
            return None             # always allowed (whether a +4 was honest is not checked)
        if self.colour is None:
            return None             # after a wild, the next card names the colour
        if card.colour == self.colour:
            return None
        top_kind = card_kind(self.top)
        if kind is not None and kind == top_kind:
            return None             # same number or same action symbol
        return f"needs {self.colour}" + (f" or {top_kind}" if top_kind else "")

    # -----------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------
    def start(self, card):
        """First card turned from the deck onto the discard pile."""
        events = []
        kind = card_kind(card)
        self.unsure = False
        if kind == "wild4":
            self._say(events, "reject", "First card is a Wild Draw Four: put it back in the deck and turn another.")
            return events
        self.started = True
        self.top = card
        self.colour = None if kind == "wild" else card.colour
        first = self.current
        self._say(events, "start", f"New game: starting card {card}")
        self._note_unsure(events, card)
        if kind == "skip":
            self._say(events, "info", f"{self.name(first)} is skipped")
            self.current = self.seat_after(first)
        elif kind == "reverse":
            self.direction = -1     # the dealer (seat before P1) plays first, going the other way
            self.current = self.seat_after(first)
            self._say(events, "info", "Direction reversed")
        elif kind == "draw2":
            self._give(first, 2)
            self.pending_draw = (first, 2)
            self._say(events, "draw", f"{self.name(first)} draws 2 and is skipped -> {self.hands[first]} cards")
            self.current = self.seat_after(first)
        elif kind == "wild":
            self._say(events, "info", f"{self.name(first)} names the colour by playing it")
        self._to_play(events)
        return events

    def play(self, card, now=None):
        """The current player puts `card` on the discard pile."""
        if not self.started:
            return self.start(card)
        events = []
        if self.winner is not None:
            self._say(events, "info", f"Game over, {self.name(self.winner)} won. Press N for a new game.")
            return events
        seat, kind = self.current, card_kind(card)
        who = self.name(seat)

        problem = self._illegal(card, kind)
        if problem and C.REJECT_ILLEGAL:     # before the UNO check, so a refused card changes nothing
            self._say(events, "reject", f"{who}: {card} is not allowed ({problem}). Take it back.")
            return events
        self._check_uno(events)
        if problem:
            self._say(events, "warn", f"WARNING {who}: {card} does not match ({problem}), recorded anyway")
        self._note_unsure(events, card)

        if self.colour is None and kind not in WILDS:
            self._say(events, "info", f"Colour is now {card.colour}")
        self.hands[seat] -= 1
        self.pending_draw = None
        self.top = card
        self.colour = None if kind in WILDS else card.colour
        self._say(events, "play", f"{who} plays {card} -> {self.hands[seat]} left")

        steps = 1
        nxt = self.seat_after(seat)
        if kind == "skip":
            self._say(events, "info", f"{self.name(nxt)} is skipped")
            steps = 2
        elif kind == "reverse":
            self.direction *= -1
            steps = 2 if len(self.hands) == 2 else 1      # with 2 players reverse acts like skip
            self._say(events, "info", "Direction reversed")
        elif kind in ("draw2", "wild4"):
            n = 2 if kind == "draw2" else 4
            self._give(nxt, n)
            self.pending_draw = (nxt, n)
            self._say(events, "draw", f"{self.name(nxt)} draws {n} and is skipped -> {self.hands[nxt]} cards")
            steps = 2
        if kind in WILDS:
            self._say(events, "info", "Colour unknown until the next card is played")

        if self.hands[seat] == 0:
            self.winner = seat
            self._say(events, "win", f"{who} wins!")
            return events
        if self.hands[seat] == 1:
            self.uno_watch, self.uno_since = seat, now
            if seat not in self.called:
                self._say(events, "uno_due", f"{self.name(seat)} is on 1 card: press U to call UNO!")
        else:
            self.called.discard(seat)   # an early UNO call does not carry over
        self.current = self.seat_after(seat, steps)
        self._to_play(events)
        return events

    def draw(self, n=1):
        """Key D: the current player draws n cards and the turn passes (simple rule, see rules.md)."""
        events = []
        if not self.started or self.winner is not None:
            self._say(events, "info", "Draw ignored: no game running")
            return events
        self._check_uno(events)
        self.unsure = False
        seat = self.current
        self._give(seat, n)
        self.pending_draw = None
        self._say(events, "draw", f"{self.name(seat)} draws {n} and passes -> {self.hands[seat]} cards")
        self.current = self.seat_after(seat)
        self._to_play(events)
        return events

    def tick(self, now):
        """Called every frame: the UNO? window ran out without a call -> penalty."""
        if (self.uno_watch is None or self.uno_since is None or C.UNO_WINDOW_SECONDS <= 0
                or self.uno_watch in self.called or now - self.uno_since < C.UNO_WINDOW_SECONDS):
            return []
        events = []
        self._check_uno(events)
        return events

    def uno_left(self, now):
        """Seconds left to call UNO for the seat on 1 card, or None if no call is due."""
        if self.uno_watch is None or self.uno_watch in self.called or self.uno_since is None:
            return None
        if C.UNO_WINDOW_SECONDS <= 0:
            return 0.0
        return max(0.0, C.UNO_WINDOW_SECONDS - (now - self.uno_since))

    def call_uno(self, now=None):
        """Key U: the player who just went down to 1 card calls UNO,
        or, if nobody is on 1 card, the current player calls it before playing their second-last card."""
        events = self.tick(now) if now is not None else []
        if events:                  # the UNO? window ran out first: the penalty stands
            self._say(events, "info", "UNO call too late: the window had already run out")
            return events
        open_call = self.uno_watch is not None and self.uno_watch not in self.called
        seat = self.uno_watch if open_call else self.current
        self.called.add(seat)
        self._say(events, "uno", f"{self.name(seat)} calls UNO!")
        return events

    def snapshot(self, now=None):
        return {
            "uno_seat": self.uno_watch,
            "uno_left": self.uno_left(now) if now is not None else None,
            "names": list(self.names),
            "hands": list(self.hands),
            "current": self.current,
            "direction": self.direction,
            "colour": self.colour,
            "colour_unknown": self.colour_unknown,
            "top": str(self.top) if self.top else None,
            "pending_draw": self.pending_draw,
            "called": sorted(self.called),
            "winner": self.winner,
            "started": self.started,
            "unsure": self.unsure,
        }
