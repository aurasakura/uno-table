# UNO rules (classic) and how `game.py` follows them

## The classic rules

**Deck (108 cards).** Four colours: red, yellow, green, blue. Each colour has one 0, two each of 1-9, two Skip, two Reverse and two Draw Two (25 per colour, 100 in total). There are also 4 Wild and 4 Wild Draw Four cards.

**Deal.** Each player gets 7 cards. The rest go face down as the draw pile. The top card is turned over to start the discard pile. Play starts with the player to the dealer's left and goes left (clockwise).

**Starting card.** If the first turned card is an action card, it acts as if the dealer had played it:
- Skip: the first player is skipped.
- Reverse: the dealer plays first, and play goes right (counter-clockwise).
- Draw Two: the first player draws 2 and is skipped.
- Wild: the first player names the colour and plays.
- Wild Draw Four: put it back in the deck and turn another card.

**Your turn.** Play one card that matches the top of the discard pile by colour, number or symbol, or play a Wild. If you can't play, or don't want to, draw one card. If that card can be played, you may play it at once. Otherwise your turn ends.

**Action cards.**
- **Skip:** the next player loses their turn.
- **Reverse:** play changes direction. With 2 players it works like Skip.
- **Draw Two:** the next player draws 2 and loses their turn.
- **Wild:** you name the next colour. You may play it at any time.
- **Wild Draw Four:** you name the next colour, and the next player draws 4 and loses their turn. You may only play it if you have no card of the current colour. The next player may challenge you. If you played it illegally, you draw 4 instead. If it was legal, the challenger draws 6.

**UNO.** When you play your second-last card, you must say "UNO". If another player catches you before the next player starts their turn, you draw 2.

**Winning.** The first player with no cards left wins the round.

## Human rule -> code rule

Seats are P1-P4 in turn order (`config.SEAT_NAMES`). The dealer is the seat before `FIRST_SEAT` (P1). "next" means the next seat in the current `direction`.

| human rule | code (`game.py`) |
|---|---|
| Deal 7 each | `hands = [7, 7, 7, 7]`, `current = P1`, `direction = +1` |
| Starting card is a number | `top = card`, `colour = card.colour`, P1 to play |
| Starting Skip | P1 skipped, `current -> P2` |
| Starting Reverse | `direction = -1`, `current -> P4` (dealer) |
| Starting Draw Two | `hands[P1] += 2`, P1 skipped, `current -> P2` |
| Starting Wild | `colour = None` (unknown), P1 plays and that card names the colour |
| Starting Wild Draw Four | event `reject` "put it back", game not started, the next card read is the new starting card |
| P1 plays a matching card | `hands[P1] -= 1`, `top = card`, `colour = card.colour`, `current -> P2` |
| Match check | legal if card is wild/+4, or `colour` is unknown, or `card.colour == colour`, or same symbol as top |
| Symbol not read (`None`) | match by colour only, and log it |
| P1 plays an illegal card | event `warn`, card still recorded (`REJECT_ILLEGAL = False`). With `True`: event `reject`, nothing changes |
| P1 plays Skip | `hands[P1] -= 1`, P2 skipped, `current -> P3` |
| P1 plays Reverse | `hands[P1] -= 1`, `direction *= -1`, `current -> P4` (with 2 seats: acts as skip) |
| P1 plays Draw Two | `hands[P1] -= 1`, `hands[P2] += 2`, P2 skipped, `current -> P3` |
| P1 plays Wild | `hands[P1] -= 1`, `colour = None`, `current -> P2`. P2's card names the colour and is always legal |
| P1 plays Wild Draw Four | `hands[P1] -= 1`, `hands[P2] += 4`, P2 skipped, `current -> P3`, `colour = None` until P3's card names it |
| Can't or won't play (key `d`) | `hands[current] += 1`, `current -> next` |
| Say UNO (key `u`) | `called.add(seat)`: the seat that just went down to 1 card, or else the current player (calling before playing their second-last card) |
| Forgot UNO, caught | P1 reaches 1 card without a call. When the next player plays or draws: `hands[P1] += 2`, log "P1 forgot UNO, +2" (`UNO_PENALTY`) |
| Last card played | `hands[P1] == 0`, `winner = P1`, event `win`. Any +2/+4 effect on that card is still applied first |
| New game (key `n`) | fresh `Game()`, and the next card read is the starting card |

The engine counts forced draws (+2, +4, UNO penalty) by itself. The HUD shows "(+4)" next to that seat as a reminder to pick up. Do not press `d` for these draws.

## Rules we do not enforce (on purpose)

- **Who played.** The camera can't see whose card it is, so the engine assumes everyone plays in turn order.
- **Playing the drawn card.** Key `d` always draws one card and passes the turn. The official rule lets you play a drawn card straight away, but here the turn has already moved on. A card put down now would count for the next seat and the counts would go wrong. So keep the drawn card for your next turn.
- **Wild Draw Four legality and challenge.** Checking it needs the hidden hand, so it is not enforced. Players can still challenge at the table, but the engine won't change the counts.
- **Naming the wild colour.** The engine doesn't hear the call. The colour stays unknown until the next card, and that card's colour becomes the colour.
- **Stacking** (+2 on +2, +4 on +4): a house rule, off. The next player always draws and is skipped.
- **Seven-0** (swap hands on 7, rotate on 0), **jump-in**, and **draw until you can play**: house rules, off.
- **Scoring across rounds** (card points to 500): not tracked. A round ends at the win.
- **Reshuffling an empty draw pile:** happens at the table and does not change the counts.
