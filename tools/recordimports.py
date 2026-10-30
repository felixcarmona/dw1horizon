"""The four cross-game record originals, using derive's existing import machinery.

Only the additional frozen entries and size operations live here; existing imported models
import recipes and deltas are unchanged. No private model is a cache/input.
"""
import json

from tools.derive.importers import Provider


class Sources(Provider):
    def __init__(self, games, work, repo=None):
        super().__init__(games, work, repo)
        recipes = json.loads((self.repo / 'content/record-originals/imports.json').read_text())
        for recipe in recipes['recipes']:
            for ext in ('MMD', 'TIM'):
                self.batches[f'{recipe["out"]}/{recipe["entry"]["name"]}.{ext}'] = recipe
        self.sizes.update({r['target']: r for r in recipes['sizes']})
