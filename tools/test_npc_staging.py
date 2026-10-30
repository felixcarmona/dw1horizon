#!/usr/bin/env python3
"""Regressions for archive-aware heap accounting and pre-allocation compaction."""
import struct
import tempfile
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]
import membudget as m
import npcanims


class NpcStaging(unittest.TestCase):
    def tearDown(self):
        m.configure(env={})
        m.archive_models.cache_clear()
        m.TRIMMED = False

    def test_release_facts_reach_story_workers(self):
        from derive.steps import story
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot = {'format': 1, 'npc_stage_max': 102400, 'heap_total': 188912}
            ctx = SimpleNamespace(facts=snapshot, path=lambda *p: str(root.joinpath(*p)))
            settings = SimpleNamespace(langs=lambda ctx: [])
            with patch.object(story, 'Settings', return_value=settings):
                self.assertEqual(story.units(ctx), [])
            self.assertEqual(json.loads((root / 'derived/exe-facts.json').read_text()), snapshot)

    def test_record_original_uses_archive_bytes(self):
        blob = bytes(2048) + b'replacement'
        rows = {105: dict(modelSector=1, modelSize=11)}
        with patch.object(m._species, 'read_archive', return_value=(blob, 1, rows)), \
             patch.object(m._species, 'record_originals', return_value={105}):
            m.configure(env={'DW_MODEL_ARCHIVE': '/synthetic/DIGI.DAT'})
            self.assertEqual(m.model_data(105), b'replacement')
            self.assertEqual(m.mmd_size(105), 11)

    def test_recorded_target_compacts_without_local_linker_tree(self):
        m.TRIMMED = False
        m.TARGET_FACTS = {'npc_anim_keep': [[0]] * 180}
        m.NPC_STAGE_MAX = 4096
        with patch.object(m, 'mmd_size', return_value=2100), \
             patch.object(npcanims, 'trimmed_size', return_value=1900):
            self.assertEqual(m.model_block_resident(105), m.blk(1900))

    def test_explicit_archive_cannot_hide_missing_models(self):
        m.MODEL_ARCHIVE = '/missing/DIGI.DAT'
        with patch.object(m, 'model_data', side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError): m.mmd_size(105)

    def test_stage_capacity_includes_cd_padding(self):
        m.NPC_STAGE_MAX = 4095
        with patch.object(m, 'mmd_size', return_value=2049):
            self.assertFalse(m.staged(105))
        m.NPC_STAGE_MAX = 4096
        with patch.object(m, 'mmd_size', return_value=2049):
            self.assertTrue(m.staged(105))

    def test_untrimmed_legacy_model_keeps_sector_padding(self):
        m.TRIMMED = True
        with patch.object(m, 'mmd_size', return_value=2100), \
             patch.object(npcanims, 'trimmed_size', return_value=2100):
            self.assertEqual(m.model_block_resident(80), m.blk(4096))
            m.NPC_STAGE_MAX = 4096
            self.assertEqual(m.model_block_resident(80), m.blk(2100))

    def test_compaction_uses_target_masks_and_actual_model(self):
        # Two animations: keep idle (16 B), drop second (64 B), add 16 B stub.
        data = struct.pack('<IIII', 0, 8, 8, 24) + bytes(80)
        m.TARGET_FACTS = {'npc_anim_keep': [[0] for _ in range(180)]}
        with patch.object(m, 'model_data', return_value=data), \
             patch.dict(m.DIGI, {105: {'bone_count': 2}}):
            self.assertEqual(npcanims.trimmed_size(105), 48)

    def test_peak_covers_placements_before_later_model_load(self):
        # Earlier instances may already exist when the next full model loads.
        with patch.object(m, 'model_block_resident', return_value=100), \
             patch.object(m, 'model_block', return_value=1000), \
             patch.object(m, 'instance_blocks', return_value=30), \
             patch.object(m, 'staged', return_value=False), patch.object(m, 'TEMP_TIM', 0):
            self.assertEqual(m.path_cost([1, 2], [(1, 0)])['peak'], 1130)
        with patch.object(m, 'model_block_resident', return_value=100), \
             patch.object(m, 'instance_blocks', return_value=30), \
             patch.object(m, 'staged', return_value=True), patch.object(m, 'TEMP_TIM', 0):
            self.assertEqual(m.path_cost([1, 2], [(1, 0)])['peak'], 230)


if __name__ == '__main__':
    unittest.main()
