#!/usr/bin/env python3
"""Verify fork settings translations against production-generated language assets.

Usage:
  python3 tools/check_settings_localizations.py --assets-dir PATH
  python3 tools/check_settings_localizations.py --apk app.apk

Expected text comes from the checked-in Arabic and default XML files, not a
second translation implementation. Both generated assets and a signed APK
can be checked with the same assertions. Only Python's standard library is used.
"""
import argparse
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'TMessagesProj/src/main/res'
KEYS = '''BackAnimationStyle SpringAnimationCrossfade localPremium
UnlimitedPinnedDialogs UnlimitedFavoredStickers uploadBoost enhancedFileLoader
NoiseSuppressAndVoiceEnhance SendMp4DocumentAsVideo EnhancedVideoBitrate
unreadBadgeOnBackButton SendCommentAfterForward UseChatAttachEnterMenu FixLinkPreview
DisableLinkPreviewByDefault DeleteChatForBothSides ShowMessageID showSeconds
UseEditedIcon DateOfForwardedMsg TelegramUIAutoTranslate TranslatorKeepMarkdown
TranslatorMode LlmProviderPreset LlmApiKey FolderNameAsTitle CustomTitleUserName
DisableNumberRounding PreferCommonGroupsTab ShowIdAndDc NameOrder SaveToChatSubfolder IPv6'''.split()


def java_hash(value):
    encoded = value.encode('utf-16-le')
    result = 0
    for unit, in struct.iter_unpack('<H', encoded):
        result = (31 * result + unit) & 0xffffffff
    return result


def decode_asset(data):
    count, = struct.unpack_from('<I', data)
    offset = 4
    entries = {}
    for _ in range(count):
        key_hash, = struct.unpack_from('<I', data, offset)
        offset += 4
        start = offset
        length = data[offset]
        if length == 254:
            length = int.from_bytes(data[offset + 1:offset + 4], 'little')
            offset += 4
        else:
            offset += 1
        text = data[offset:offset + length].decode('utf-8')
        offset += length
        offset += (-(offset - start)) % 4
        assert key_hash not in entries, 'Duplicate string hash in asset'
        entries[key_hash] = text
    assert offset == len(data), 'Asset length mismatch'
    return entries


def xml_texts(folder):
    result = {}
    for file in sorted(folder.glob('strings*.xml')):
        for node in ET.parse(file).getroot().findall('string'):
            value = ''.join(node.itertext())
            result[node.attrib['name']] = value.replace('\\n', '\n').replace('\\', '').replace('&lt;', '<')
    return result


def check(load):
    for locale, directory in [('en', 'values'), ('ar', 'values-ar')]:
        expected = xml_texts(RES / directory)
        actual = decode_asset(load('localization_' + locale + '.bin'))
        for key in KEYS:
            assert key in expected, f'Missing source translation: {locale}/{key}'
            assert actual.get(java_hash(key)) == expected[key], f'Missing/wrong packaged translation: {locale}/{key}'
            assert expected[key] and expected[key] != key and not expected[key].startswith('LOC_ERR'), f'Invalid title: {locale}/{key}'
        print(f'PASS {locale}: {len(KEYS)} settings titles match source translations ({len(actual)} asset entries)')


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--assets-dir', type=Path)
    source.add_argument('--apk', type=Path)
    args = parser.parse_args()
    if args.apk:
        with zipfile.ZipFile(args.apk) as apk:
            check(lambda name: apk.read('assets/' + name))
            assert apk.getinfo('assets/emoji.pack').compress_type == zipfile.ZIP_STORED, 'Regression: emoji.pack compressed again'
            print('PASS emoji.pack remains STORED')
    else:
        check(lambda name: (args.assets_dir / name).read_bytes())


if __name__ == '__main__':
    main()
