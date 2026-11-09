"""The Motor must wait for Shellmon's plea without closing either quest route."""
from types import SimpleNamespace
import unittest

from test_factory import Dummy, handler
from test_story import Counter


ENGINE = 'story/mods/what-the-island-forgot/arcs/canyon/engine-room.py'
BRIDGE = 'story/base/zones/great-canyon-bridge/s039-39/script.py'
CANYON = 'story/base/zones/great-canyon/s122-127/script.py'


class Shellmon(unittest.TestCase):
    def scene(self, plea=False, joined=False, answer=True):
        dummy = Dummy()
        prompts, joins, stages = [], [], []
        env = {name: Counter() for name in (
            'shellmon_plea_heard', 'root1', 'invisible_bridge_rumor_heard',
            'invisible_bridge_crossed', 'glances')}
        env['shellmon_plea_heard'].set(plea)
        residents = {35} if joined else set()

        def recruit(species, prosperity=0):
            residents.add(species)
            joins.append((species, prosperity))

        def ask(**options):
            prompts.append(options)
            return answer

        env.update(tamer=dummy, partner=dummy, narrator=dummy, camera=dummy,
                   sound=dummy, wait=dummy, fade_to_white=dummy, fade_from_white=dummy,
                   ask=ask, recruit=recruit, recruited=residents.__contains__,
                   Species=SimpleNamespace(Shellmon=35), Canyon=SimpleNamespace(SETTLED=2),
                   advance=stages.append)
        choice = handler(ENGINE, 'the_choice', env)
        return env, choice, prompts, joins, stages

    def hear_plea(self, env):
        dummy = Dummy()
        env.update(ogre_fortress_cleared=True, canyon_elevator_ridden=True,
                   ogre_fortress_elevator_ridden=False, t51=dummy, anim=dummy)
        handler(BRIDGE, 'step0', env)()
        self.assertTrue(env['shellmon_plea_heard'])

    def test_machine_first_defers_destruction_and_recruitment(self):
        env, choice, prompts, joins, stages = self.scene()
        choice()
        self.assertEqual(prompts, [])
        self.assertFalse(env['root1'])
        self.assertFalse(env['invisible_bridge_crossed'])
        self.assertEqual(joins, [])
        self.assertEqual(stages, [2], 'the rest of the chase must continue')

    def test_machine_first_then_plea_then_return(self):
        env, choice, prompts, joins, stages = self.scene()
        choice()
        self.hear_plea(env)
        # The existing settled/notebook/not-root1 entry handler retries the choice.
        handler(ENGINE, 'the_motor_again', env)()
        self.assertEqual(len(prompts), 1)
        self.assertTrue(env['root1'])
        self.assertTrue(env['invisible_bridge_crossed'])
        self.assertEqual(joins, [(35, 2)])

    def test_plea_first_can_break_motor(self):
        env, choice, prompts, joins, stages = self.scene(plea=True)
        choice()
        self.assertTrue(env['root1'])
        self.assertEqual(joins, [(35, 2)])
        self.assertEqual(len(prompts), 1)

    def test_declining_keeps_original_recruitment(self):
        env, choice, prompts, joins, stages = self.scene(plea=True, answer=False)
        choice()
        self.assertFalse(env['root1'])
        self.assertEqual(joins, [])
        dummy = Dummy()
        env.update(shellmon=dummy, t5=dummy, anim=dummy, say=dummy, walk_away=dummy)
        handler(CANYON, 'talk', env, 'shellmon.')()
        self.assertEqual(joins, [(35, 2)])

    def test_declining_can_be_reversed_on_revisit(self):
        env, choice, prompts, joins, stages = self.scene(plea=True, answer=False)
        choice()
        env['ask'] = lambda **options: True
        handler(ENGINE, 'the_motor_again', env)()
        self.assertTrue(env['root1'])
        self.assertEqual(joins, [(35, 2)])

    def test_existing_recruit_is_preserved_without_duplicate_reward(self):
        for plea in (False, True):
            with self.subTest(plea=plea):
                env, choice, prompts, joins, stages = self.scene(plea=plea, joined=True)
                choice()
                self.assertTrue(env['recruited'](35))
                self.assertEqual(joins, [])


if __name__ == '__main__':
    unittest.main()
