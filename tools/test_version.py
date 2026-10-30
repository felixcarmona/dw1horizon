"""Release metadata must agree across git checkouts and source archives."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import version


class Version(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = self.tmp.name
        self.env = dict(os.environ, GIT_AUTHOR_DATE='2026-10-25T12:00:00+00:00',
                        GIT_COMMITTER_DATE='2026-10-25T12:00:00+00:00')
        self.git('init', '-q')
        self.git('config', 'user.name', 'Version test')
        self.git('config', 'user.email', '')
        self.git('commit', '-q', '--allow-empty', '-m', 'Initial')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', self.repo, *args], env=self.env, text=True).strip()

    def test_annotated_release_and_development(self):
        self.env['GIT_COMMITTER_DATE'] = '2026-10-26T12:00:00+00:00'
        self.git('tag', '-a', 'v0.1.0', '-m', 'Release')
        info = version.describe(self.repo)
        self.assertEqual((info['version'], info['date']), ('0.1.0', '2026-10-26'))
        self.assertEqual(version.game_text(info), 'v0.1.0')
        self.env['GIT_COMMITTER_DATE'] = '2026-10-27T12:00:00+00:00'
        self.git('commit', '-q', '--allow-empty', '-m', 'Next')
        info = version.describe(self.repo)
        self.assertEqual(info['version'], '0.1.0-dev.1+' + self.git('rev-parse', '--short=8', 'HEAD'))
        self.assertEqual(info['date'], '2026-10-27')

    def test_lightweight_and_prerelease_tags_are_ignored(self):
        self.git('tag', 'v9.9.9')
        self.git('tag', '-a', 'v8.8.8-rc', '-m', 'Prerelease')
        info = version.describe(self.repo)
        self.assertEqual(info['version'], '0.0.0-dev.1+' + self.git('rev-parse', '--short=8', 'HEAD'))
        self.assertIsNone(info['tag'])

    def test_archive_without_git_metadata(self):
        with tempfile.TemporaryDirectory() as archive:
            info = version.describe(archive)
            self.assertEqual(info['version'], '0.0.0-dev+unknown')

    def test_git_executable_missing(self):
        with mock.patch.object(version.subprocess, 'run', side_effect=FileNotFoundError('git')):
            self.assertEqual(version.describe(self.repo)['version'], '0.0.0-dev+unknown')

    def test_build_version_override_needs_no_git(self):
        # Run build-full's actual version assignment in a source archive.
        script = Path(version.REPO, 'tools/build-full.sh').read_text()
        assignment = next(line for line in script.splitlines() if line.startswith('MOD_VERSION='))
        with tempfile.TemporaryDirectory() as archive:
            root = Path(archive)
            (root / 'tools').mkdir()
            shutil.copyfile(Path(version.__file__), root / 'tools/version.py')
            build = root / 'tools/build-full.sh'
            build.write_text('set -euo pipefail\ncd "$(dirname "$0")/.."\nPY=python3\n' + assignment + '\nprintf "%s\\n" "$MOD_VERSION"\n')
            for override, expected in ((None, 'v0.0.0-dev+unknown'), ('v0.1.0', 'v0.1.0'), ('', '')):
                with self.subTest(override=override):
                    env = dict(os.environ)
                    env.pop('MOD_VERSION', None)
                    if override is not None: env['MOD_VERSION'] = override
                    result = subprocess.check_output(['bash', str(build)], env=env, text=True)
                    self.assertEqual(result.strip(), expected)


if __name__ == '__main__':
    unittest.main()
