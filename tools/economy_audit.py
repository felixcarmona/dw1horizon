#!/usr/bin/env python3
"""Economy audit: no repeatable conversion may turn bits into more bits.

Reads content/items, content/tables/{economy,shops,cards}.json and the card trades of the scripts (constants below, from
story/base: DemiMeramon, ClearAgumon, the Trash Mountain swap), works out what every item and card is worth at its best
way out (a shop's sell price, merit at the merit shop's best rate, Mojyamon, the NPCs that take cards), and checks:

  - every Mojyamon trade: what it gives is worth no more than what it takes (so neither a chain of trades nor a trade fed
    by bought, fished or picked-up items is worth more than selling the input);
  - a card pack, the item shop's card machine and each card of the daily card shop cost more than what they give back.

Daily-limited gains (the daily card shop: 6 cards a day, one copy each) are reported, not failed.
    tools/economy_audit.py            the report; exit 1 when an unlimited loop gains
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / 'content' / 'tables'
DEMIMERAMON = {30: 1500}                      # lava-cave/s121-125: card 30 -> 1500 bits, no flag
CLEARAGUMON = ((19, 24, 57), 107)             # toy-town/s138-144: cards 19 + 24 + 57 -> X Bandage, no flag
CARD_SWAPS = {21: 14}                         # trash-mountain/s159-165: card 21 -> card 14


def main():
    econ = json.load(open(T / 'economy.json'))['economy']
    shops = json.load(open(T / 'shops.json'))
    cards_t = json.load(open(T / 'cards.json'))
    items = {}
    for f in (ROOT / 'content' / 'items').glob('*.json'):
        it = json.load(open(f))
        items[it['id']] = it
    sell_pc = econ['shop'].get('sellPercent', 100)
    def sell(i):
        it = items[i]
        return it['value'] * sell_pc // 100 if it['droppable'] else 0
    name = lambda i: items[i]['name']

    # merit: the best bits a merit point buys at the merit shop and sells for
    rate, best = 0.0, None
    for i, it in items.items():
        if it['meritValue'] > 0 and sell(i) / it['meritValue'] > rate:
            rate, best = sell(i) / it['meritValue'], i
    print(f'merit: 1 merit = {rate:.2f} bits ({name(best)}: {items[best]["meritValue"]} merit, sells {sell(best)})')

    # items: the best way out, a sale or a Mojyamon trade (and that one's best way out)
    trades = [(g, t) for g, t in zip(shops['mojyamonGives'], shops['mojyamonTakes']) if g or t]
    worth = {i: sell(i) for i in items}
    for _ in range(len(trades) + 1):
        for g, t in trades:
            worth[g] = max(worth[g], worth[t])
    fails = []
    print('Mojyamon (gives -> gets: the input sells for, the output is worth):')
    for g, t in trades:
        ok = worth[t] <= sell(g)
        print(f'  {"ok  " if ok else "GAIN"} {name(g)} -> {name(t)}: {sell(g)} -> {worth[t]}')
        if not ok:
            fails.append(f'Mojyamon {name(g)} -> {name(t)} (+{worth[t] - sell(g)} a unit, 99 a talk)')

    # cards: the best way out of each, then what a draw of a rarity is worth on average
    cards = cards_t['cards']
    prices = cards_t['cardPrices']
    cworth = {}
    for c, card in enumerate(cards):
        r = card['rarity']
        if r > 4:
            continue
        cworth[c] = max(prices[r] * sell_pc // 100, card['merit'] * rate, DEMIMERAMON.get(c, 0))
    for a, b in CARD_SWAPS.items():
        cworth[a] = max(cworth[a], cworth[b])
    by_rarity = {r: [c for c in cworth if cards[c]['rarity'] == r] for r in range(5)}
    def draw_value(odds):
        """bits a card drawn with these rarity odds (per cent) is worth on average, and the expected copies of each card"""
        copies = {c: odds[cards[c]['rarity']] / 100 / len(by_rarity[cards[c]['rarity']]) for c in cworth}
        v = sum(copies[c] * cworth[c] for c in cworth)
        set_cards, item = CLEARAGUMON            # the sets the draws make, each worth the item over its three cards
        sets = min(copies[c] for c in set_cards)
        v += sets * max(0, sell(item) - sum(cworth[c] for c in set_cards))
        return v
    cuts = econ['cardPack']['rarityBelow']
    pack_odds = [cuts[0]] + [cuts[k] - cuts[k - 1] for k in range(1, 4)] + [100 - cuts[3]]
    price = econ['cardPack']['price']
    pack = 3 * draw_value(pack_odds)
    print(f'card pack: {price} bits -> {pack:.0f}')
    if pack >= price:
        fails.append(f'card pack {price} -> {pack:.0f}')
    mc = econ['cardMachine']['rarityBelow']
    m_price, m_odds = econ['cardMachine']['price'], [mc[0]] + [mc[k] - mc[k - 1] for k in range(1, 4)] + [100 - mc[3]]
    m = draw_value(m_odds)
    print(f'card machine: {m_price} bits -> {m:.0f} (odds {m_odds})')
    if m >= m_price:
        fails.append(f'card machine {m_price} -> {m:.0f}')
    print('daily card shop (6 a day, one copy each: reported only):')
    for c in sorted(cworth):
        r = cards[c]['rarity']
        if cworth[c] > prices[r]:
            print(f'  card {c} (rarity {r}): {prices[r]} -> {cworth[c]:.0f} (+{cworth[c] - prices[r]:.0f} a day)')

    if fails:
        print('\nunlimited gains:\n  ' + '\n  '.join(fails))
        return 1
    print('\nno unlimited gain')
    return 0


if __name__ == '__main__':
    sys.exit(main())
