#!/usr/bin/env python3
"""Economy audit: no repeatable conversion may turn bits into more bits.

Reads content/items, content/tables/{economy,shops,cards}.json and the card trades of the scripts (constants below, from
story/base: DemiMeramon, ClearAgumon, the Trash Mountain swap), works out what every item and card is worth at its best
way out (a shop's sell price, merit at the merit shop's best rate, Mojyamon, the NPCs that take cards), and checks:

  - Mojyamon gains require an explicit, identity-pinned daily or once-per-save exception;
    every uncapped trade still pays no more than selling its input;
  - vending prices, bonus payouts and slot odds, taken from the actual story handlers, including chained trades;
  - a card pack, the item shop's card machine and each card of the daily card shop cost more than what they give back.

Reviewed capped gains are reported separately; their edges never enter unlimited-conversion valuations.
    tools/economy_audit.py            the report; exit 1 when an unlimited loop gains
"""
import json, sys
from vending_audit import check_vending, conversion_changes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / 'content' / 'tables'
DEMIMERAMON = {30: 1500}                      # lava-cave/s121-125: card 30 -> 1500 bits, no flag
CLEARAGUMON = ((19, 24, 57), 107)             # toy-town/s138-144: cards 19 + 24 + 57 -> X Bandage, no flag
CARD_SWAPS = {21: 14}                         # trash-mountain/s159-165: card 21 -> card 14
# treasure-hunt/s169-209, libraries/s205: Drimogemon's plans, [(percent, item)] without and with Gabumon; with Gabumon
# 5 % of the hunts roll another item, over and over
HUNT_REPEAT = 5
HUNTS = {'Normal plan': (2000, [(20, 9), (20, 10), (10, 18), (10, 19), (10, 20), (10, 21), (5, 11), (5, 73), (5, 82), (5, 90)],
                        [(15, 9), (15, 18), (15, 10), (10, 19), (10, 20), (10, 21), (10, 11), (5, 73), (5, 82), (5, 90)]),
         'Special plan': (5000, [(10, 11), (20, 73), (20, 82), (20, 90), (5, 27), (5, 28), (5, 23), (5, 24), (5, 26), (5, 25)],
                          [(10, 11), (10, 73), (10, 82), (10, 90), (10, 27), (10, 28), (10, 23), (10, 24), (10, 26), (10, 25)])}


# Runtime contracts: row 8 checks permanent completion flag 13; all other rows
# check their saved daily bit. Pair identity is pinned so a new trade is uncapped
# until it is reviewed here and in the engine tests.
MOJYAMON_CAPS = {
    0: (69, 46, 'daily'), 1: (67, 70, 'daily'), 2: (63, 47, 'daily'),
    3: (41, 6, 'daily'), 4: (42, 2, 'daily'), 5: (48, 7, 'daily'),
    6: (44, 22, 'daily'), 7: (39, 64, 'daily'), 8: (0, 124, 'save'),
}
# Explicit exceptions to the output <= input sale rule. A matching, pinned cap
# is mandatory; Dolph Fin must be once per save, never a daily exception.
MOJYAMON_GAIN_EXCEPTIONS = {
    0: (69, 46, 'daily'),
    2: (63, 47, 'daily'), 3: (41, 6, 'daily'), 4: (42, 2, 'daily'),
    5: (48, 7, 'daily'), 6: (44, 22, 'daily'), 8: (0, 124, 'save'),
}


def audit_mojyamon(shops, items, sell_pc, caps=None, exceptions=None):
    caps = MOJYAMON_CAPS if caps is None else caps
    exceptions = MOJYAMON_GAIN_EXCEPTIONS if exceptions is None else exceptions
    def sell(i):
        return items[i]['value'] * sell_pc // 100 if items[i]['droppable'] else 0
    rows = []
    for n, (g, t) in enumerate(zip(shops['mojyamonGives'], shops['mojyamonTakes'])):
        if not (g or t):
            continue
        contract = caps.get(n)
        limit = contract[2] if contract and contract[:2] == (g, t) else 'unlimited'
        rows.append(dict(row=n, input=g, output=t, limit=limit))
    # Only uncapped edges belong in unlimited-conversion valuations. A finite
    # daily or save reward must never inflate vending EV as if it paid forever.
    worth = {i: sell(i) for i in items}
    for _ in range(len(rows) + 1):
        for row in rows:
            if row['limit'] == 'unlimited':
                g, t = row['input'], row['output']
                worth[g] = max(worth[g], worth[t])
    fails = []
    for row in rows:
        n, g, t, limit = (row[k] for k in ('row', 'input', 'output', 'limit'))
        exception = exceptions.get(n)
        if n in MOJYAMON_GAIN_EXCEPTIONS and (g, t) == MOJYAMON_GAIN_EXCEPTIONS[n][:2]:
            required = MOJYAMON_GAIN_EXCEPTIONS[n][2]
            if limit != required:
                fails.append(f'Mojyamon row {n + 1}: requires {required} cap, got {limit}')
        if worth[t] > sell(g) and (exception != (g, t, limit) or limit not in ('daily', 'save')):
            fails.append(f'Mojyamon {items[g]["name"]} -> {items[t]["name"]}: '
                         f'unapproved gain {worth[t] - sell(g)} per exchange ({limit})')
    return dict(rows=rows, worth=worth, fails=fails,
                daily_gross=sum(worth[r['output']] for r in rows if r['limit'] == 'daily'),
                once_gross=sum(worth[r['output']] for r in rows if r['limit'] == 'save'),
                daily_gain=sum(sell(r['output']) - sell(r['input']) for r in rows if r['limit'] == 'daily'),
                daily_gain_ceiling=sum(max(0, sell(r['output']) - sell(r['input'])) for r in rows if r['limit'] == 'daily'),
                once_gain=sum(sell(r['output']) - sell(r['input']) for r in rows if r['limit'] == 'save'))


def mojyamon_input_prices(items, econ):
    """Known shop offers, reading generic shop stock and the actual vending handlers.

    A missing price means no shop offer, rather than the item's nominal value.
    The regular File City item shop stocks Small Recovery. Vegiemon's fixed-price
    roots are also available at the generic city stalls; its price stays 500.
    """
    import ast
    from vending_audit import item_ids, menu_paths, run_handler, MACHINES
    ids = item_ids()
    prices = {}
    baby_pc = econ['shop'].get('babyBuyPercent', 100)
    def offer(i, normal, baby):
        old = prices.get(i, (normal, baby))
        prices[i] = (min(normal, old[0]), min(baby, old[1]))
    offer(0, items[0]['value'], items[0]['value'] * baby_pc // 100)
    paths = list((ROOT / 'story/base/zones').rglob('script.py'))
    paths += list((ROOT / 'story/mods/what-the-island-forgot').rglob('*.py'))
    for path in paths:
        for call in ast.walk(ast.parse(path.read_text())):
            if not isinstance(call, ast.Call):
                continue
            fn = call.func
            if not (isinstance(fn, ast.Name) and fn.id == 'shop'
                    or isinstance(fn, ast.Attribute) and fn.attr == 'shop'):
                continue
            for arg in call.args:
                if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and arg.value.id == 'Item':
                    i = ids[arg.attr]; value = items[i]['value']
                    offer(i, value, value * baby_pc // 100)
    # Vegiemon is a scripted purchase, not the generic shop's baby discount.
    for i in (41, 42):
        offer(i, 500, 500)
    for sid in MACHINES:
        if sid == 12:  # Prize draw outcomes are not fixed-price shop offers.
            continue
        source = next((ROOT / 'story/base/zones').glob(f'*/s{sid:03d}-*/script.py')).read_text()
        for path in menu_paths(source):
            paid, got, _, _ = run_handler(source, path, 99)
            # Fixed offers only; random/bonus menus do not establish a unit price.
            if paid and len(got) == 1:
                i, count = next(iter(got.items()))
                if count == 1:
                    offer(i, paid, paid)
    return prices


def purchase_ceiling(rows, prices, sell, baby=False):
    daily = [r for r in rows if r['limit'] == 'daily']
    unsold = sorted({r['input'] for r in daily if r['input'] not in prices})
    cost = sum(prices[r['input']][int(baby)] for r in daily if r['input'] in prices)
    gross = sum(sell(r['output']) for r in daily)
    return dict(cost=cost, gross=gross, net=gross - cost, unsold=unsold,
                buyable_net=sum(sell(r['output']) - prices[r['input']][int(baby)] for r in daily if r['input'] in prices),
                buyable_ceiling=sum(max(0, sell(r['output']) - prices[r['input']][int(baby)]) for r in daily if r['input'] in prices),
                mixed_ceiling=sum(max(0, sell(r['output']) - (prices[r['input']][int(baby)] if r['input'] in prices else 0)) for r in daily))


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

    result = audit_mojyamon(shops, items, sell_pc)
    worth, fails = result['worth'], result['fails']
    print('Mojyamon (input sale -> output best unlimited exit; limits are per row):')
    for row in result['rows']:
        print(f"  {row['limit']:9} {name(row['input'])} -> {name(row['output'])}: "
              f"{sell(row['input'])} -> {worth[row['output']]}")
    print(f"Mojyamon daily reward sales (gross, not gains): {result['daily_gross']} bits with free inputs; "
          f"one-time rewards: {result['once_gross']} bits, excluded from daily gains")
    print(f"Mojyamon gain over selling inputs: all eight rows {result['daily_gain']}/day; "
          f"positive rows only {result['daily_gain_ceiling']}/day (ceiling); "
          f"after 1500 travel: {result['daily_gain_ceiling'] - 1500}; once-only gain {result['once_gain']}")
    prices = mojyamon_input_prices(items, econ)
    for baby in (False, True):
        scenario = purchase_ceiling(result['rows'], prices, sell, baby)
        print(f"Mojyamon {'baby' if baby else 'normal'} cheapest purchases + free fishing: "
              f"inputs {scenario['cost']}, rewards {scenario['gross']}, net {scenario['net']}; "
              f"after 1500-bit Birdramon trip: {scenario['net'] - 1500}")
        print(f"  Bought inputs only: all seven {scenario['buyable_net']}/day; "
              f"positive rows only {scenario['buyable_ceiling']}/day; after travel {scenario['buyable_ceiling'] - 1500}. "
              f"With free Digiseabass: positive-row cash net {scenario['mixed_ceiling']}/day; its sale value is not counted as a cost.")
    print('Inputs without a shop offer are fished for free in this calculation: '
          + ', '.join(name(i) for i in scenario['unsold']))

    vending_fails, sold = check_vending(worth, {i: name(i) for i in items})
    fails.extend(vending_fails)
    fails.extend(conversion_changes(sold))

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
        v += sets * max(0, worth[item] - sum(cworth[c] for c in set_cards))
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
    for plan, (hunt_price, plain, gabumon) in HUNTS.items():
        worth_of = lambda odds: sum(pc * sell(i) for pc, i in odds) / 100
        hunt = max(worth_of(plain), worth_of(gabumon) * 100 / (100 - HUNT_REPEAT))
        print(f'{plan}: {hunt_price} bits -> {hunt:.0f}')
        if hunt >= hunt_price:
            fails.append(f'{plan} {hunt_price} -> {hunt:.0f}')
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
