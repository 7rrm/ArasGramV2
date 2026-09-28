#!/usr/bin/env python3
"""Host-side regression tests for mmap-required emoji assets in MeeroX APKs.

Run: python3 tools/test_meero_apk_packaging.py
Requires a JDK. Tests only ZIP/encryption packaging, not Android UI or native execution.
"""
import pathlib
import subprocess
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


class MeeroPackagingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory()
        cls.directory = pathlib.Path(cls.workspace.name)
        subprocess.run([
            'javac', '-d', str(cls.directory), str(ROOT / 'tools/MeeroVaultPacker.java')
        ], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def pack(self, compression):
        source = self.directory / (self._testMethodName + '.apk')
        result = source.with_suffix('.packed.apk')
        with zipfile.ZipFile(source, 'w') as apk:
            # Dummy ELF-shaped input is never executed; tests exercise packaging only.
            apk.writestr('lib/arm64-v8a/libtmessages.49.so', b'\x7fELF' + b'\0' * 1000001)
            apk.writestr('lib/arm64-v8a/libmeerovault.so', b'test loader')
            if compression is not None:
                apk.writestr('assets/emoji.pack', b'EPK3-test-fixture', compress_type=compression)
        command = subprocess.run([
            'java', '-cp', str(self.directory), 'MeeroVaultPacker', str(source), str(result)
        ], capture_output=True, text=True)
        return command, result

    def test_compressed_emoji_rejected_before_signing(self):
        command, result = self.pack(zipfile.ZIP_DEFLATED)
        self.assertNotEqual(command.returncode, 0)
        self.assertIn('must exist and be STORED', command.stderr)
        self.assertFalse(result.exists())

    def test_missing_emoji_rejected_before_signing(self):
        command, result = self.pack(None)
        self.assertNotEqual(command.returncode, 0)
        self.assertIn('must exist and be STORED', command.stderr)
        self.assertFalse(result.exists())

    def test_stored_emoji_preserved_after_vault_pack(self):
        command, result = self.pack(zipfile.ZIP_STORED)
        self.assertEqual(command.returncode, 0, command.stderr)
        with zipfile.ZipFile(result) as apk:
            self.assertEqual(apk.getinfo('assets/emoji.pack').compress_type, zipfile.ZIP_STORED)
            self.assertEqual(apk.read('assets/emoji.pack'), b'EPK3-test-fixture')
            self.assertEqual(apk.getinfo('assets/meero_vault/core.enc').compress_type, zipfile.ZIP_STORED)

    def test_active_application_module_disables_pack_compression(self):
        build = (ROOT / 'TMessagesProj/build.gradle').read_text()
        self.assertIn("noCompress += 'pack'", build)


if __name__ == '__main__':
    unittest.main(verbosity=2)
