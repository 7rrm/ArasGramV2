#!/usr/bin/env python3
"""Protect strings that Android resolves without Telegram's localization tables.

Run source checks with no arguments. After production string generation, run:
  python tools/test_android_visible_strings.py --generated-dir PATH
PATH is build/generated/telegramStrings/<variant> (contains res/ and stable-ids.txt).
"""
import argparse
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'buildSrc/src/main/kotlin/org/telegram/tasks/TelegramStringsTask.kt'
MANIFEST = ROOT / 'TMessagesProj/src/main/AndroidManifest.xml'
ANDROID = '{http://schemas.android.com/apk/res/android}'
TOOLS = '{http://schemas.android.com/tools}'
GENERATED = None


def exclusions(name):
    match = re.search(r'\b' + name + r'\s*=\s*setOf\((.*?)\)', TASK.read_text(), re.S)
    assert match, 'Missing exclusion set: ' + name
    return set(re.findall(r'"([A-Za-z0-9_]+)"', match.group(1)))


def manifest_strings():
    return {value[len('@string/'):] for node in ET.parse(MANIFEST).iter()
            for value in node.attrib.values() if value.startswith('@string/')}


class AndroidVisibleStringsTest(unittest.TestCase):
    def test_launcher_label_is_arasgram(self):
        application = ET.parse(MANIFEST).getroot().find('application')
        self.assertEqual(application.get(ANDROID + 'label'), '@string/NagramX')
        strings = ET.parse(ROOT / 'TMessagesProj/src/main/res/values/strings_nax.xml')
        self.assertEqual(strings.find("string[@name='NagramX']").text, 'ArasGram')

    def test_manifest_strings_are_not_forced_discarded(self):
        self.assertTrue(manifest_strings())
        self.assertFalse(manifest_strings() - exclusions('GENERATED_EXCLUSIONS'))

    def test_manifest_strings_use_normal_android_resource_ids(self):
        self.assertFalse(manifest_strings() - exclusions('STABLE_IDS_EXCLUSIONS'))

    def test_upstream_app_names_remain_protected(self):
        for name in ('GENERATED_EXCLUSIONS', 'STABLE_IDS_EXCLUSIONS'):
            self.assertTrue({'AppName', 'AppNameBeta'} <= exclusions(name))

    def test_actual_generated_outputs(self):
        if GENERATED is None:
            self.skipTest('Pass --generated-dir to check production task outputs')
        resource = ET.parse(GENERATED / 'res/raw/strings_discard.xml').getroot()
        discard = {v.strip() for v in resource.get(TOOLS + 'discard').split(',')}
        for key in manifest_strings():
            self.assertNotIn('@string/' + key, discard)
        stable = (GENERATED / 'stable-ids.txt').read_text()
        for key in manifest_strings():
            self.assertNotIn(':string/' + key + ' =', stable)
        # Localization migration must remain enabled for regular fork strings.
        self.assertIn('@string/BackAnimationStyle', discard)
        self.assertIn(':string/BackAnimationStyle =', stable)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--generated-dir', type=Path)
    args, rest = parser.parse_known_args()
    GENERATED = args.generated_dir
    unittest.main(argv=[__file__, *rest], verbosity=2)
