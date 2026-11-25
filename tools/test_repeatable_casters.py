"""Every technique of the five new rows is cast by a wild Digimon in a fight that can be had again: the gym gives the
last of a row rarely, so a technique nobody casts in a repeatable fight is close to unobtainable."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import caster_audit


class RepeatableCasters(unittest.TestCase):
    def test_every_new_row_technique_has_a_repeatable_caster(self):
        found = caster_audit.casters()
        missing = [t['name'] for t in caster_audit.techniques()
                   if t['id'] >= caster_audit.NEW_ROW_FIRST and not found.get(t['name'], {}).get('again')]
        self.assertEqual(missing, [])

    def test_a_slot_nothing_fills_is_not_a_fight(self):
        # Coela Point: the Coelamon of the .MAP are scenery of the crossing scene, nobody fights them
        found = caster_audit.casters()
        again = [c for places in found.values() for c in places.get('again', [])]
        self.assertFalse([c for c in again if c.startswith('Coelamon@MAYO05/')])


if __name__ == '__main__':
    unittest.main()
