"""Private volume identifiers stay local while the native layout preserves their bytes."""
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from tools import discmeta


class MetadataTests(unittest.TestCase):
    def test_roundtrip_and_xml_escaping(self):
        source = '<track><identifiers publisher="Studio &amp; Co" data_preparer="Disc Author" copyright="C &quot;D&quot;"/></track>'
        private = discmeta.redact(source)
        self.assertNotIn('Disc Author', private)
        self.assertNotIn('Studio', private)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'disc.xml'
            project.write_text(source)
            self.assertEqual(discmeta.resolve(private, project), source)
            self.assertEqual(ET.fromstring(discmeta.resolve(private, project)).find('identifiers').get('publisher'), 'Studio & Co')

    def test_absent_project_and_malformed_recipe_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'missing.xml'
            with self.assertRaisesRegex(ValueError, 'tools/extract.sh'):
                discmeta.resolve('', path)
            path.write_text('<track/>')
            with self.assertRaisesRegex(ValueError, 'no disc identifiers'):
                discmeta.resolve('', path)
            with self.assertRaisesRegex(ValueError, 'expected one publisher'):
                discmeta.redact('<track/>')


if __name__ == '__main__':
    unittest.main()
