import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from package_openai_plugin import SOURCES, build, collect, validate


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.files = collect()

    def change(self, path, change):
        data = json.loads(self.files[path])
        change(data)
        self.files[path] = json.dumps(data).encode()

    def test_archive_is_curated_and_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = build(Path(directory), self.files)
            original = archive.read_bytes()
            self.assertEqual(build(Path(directory), self.files).read_bytes(), original)
            with zipfile.ZipFile(archive) as zipped:
                self.assertEqual(set(zipped.namelist()), set(SOURCES))
                self.assertEqual(zipped.read('skills/slash-markets-kite-data/SKILL.md'),
                                 self.files['skills/slash-markets-kite-data/SKILL.md'])

    def test_rejects_extra_secret_file(self):
        self.files['.env'] = b'SYNTHETIC=not-a-real-secret'
        with self.assertRaises(ValueError):
            validate(self.files)

    def test_rejects_auth_headers(self):
        self.change('.mcp.json', lambda d: d['mcpServers']['slash-markets'].update(
            headers={'Authorization': 'Bearer synthetic'}))
        with self.assertRaises(ValueError):
            validate(self.files)

    def test_rejects_reviewer_credentials(self):
        self.change('.codex-plugin/plugin.json', lambda d:
                    d['extensions']['com.openai']['review'].update(test_credentials='synthetic'))
        with self.assertRaises(ValueError):
            validate(self.files)

    def test_rejects_escaping_asset(self):
        self.change('.codex-plugin/plugin.json', lambda d:
                    d['interface'].update(logo='../outside.png'))
        with self.assertRaises(ValueError):
            validate(self.files)

    def test_rejects_missing_skill(self):
        del self.files['skills/slash-markets-kite-data/SKILL.md']
        with self.assertRaises(ValueError):
            validate(self.files)

    def test_rejects_overlong_listing(self):
        self.change('.codex-plugin/plugin.json', lambda d:
                    d['interface'].update(shortDescription='a' * 31))
        with self.assertRaises(ValueError):
            validate(self.files)

    def test_rejects_staging_endpoint(self):
        self.change('.mcp.json', lambda d: d['mcpServers']['slash-markets'].update(
            url='https://staging-kite-mcp.slash.markets/'))
        with self.assertRaises(ValueError):
            validate(self.files)


if __name__ == '__main__':
    unittest.main()
