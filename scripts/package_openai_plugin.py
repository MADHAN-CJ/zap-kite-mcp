"""Build a curated OpenAI ZIP; validate our documented Codex-format contract offline.

This is a repository validator, not OpenAI's portal validator or an official schema.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
# Explicit mapping: never recursively zip the repository or a working directory.
SOURCES = {
    '.codex-plugin/plugin.json': 'plugin-openai/.codex-plugin/plugin.json',
    '.mcp.json': 'plugin-openai/.mcp.json',
    'README.md': 'plugin-openai/README.md',
    'LICENSE': 'LICENSE',
    'assets/icon.png': 'plugin/icon.png',
    'skills/slash-markets-kite-data/SKILL.md': 'mcp/SKILL.md',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, limit, label):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= limit,
            f'Invalid {label}')


def https(value):
    text(value, 2048, 'HTTPS URL')
    u = urlsplit(value)
    require(u.scheme == 'https' and bool(u.hostname) and not u.username
            and not u.password and not u.fragment, 'Expected credential-free HTTPS URL')


def only_keys(value, allowed, label):
    require(isinstance(value, dict) and not (set(value) - set(allowed)),
            f'Unexpected fields in {label}')


def validate(files):
    require(set(files) == set(SOURCES), 'Unexpected or missing archive entries')
    manifest = json.loads(files['.codex-plugin/plugin.json'])
    only_keys(manifest, ('name', 'version', 'description', 'author', 'homepage', 'repository',
                        'license', 'keywords', 'skills', 'mcpServers', 'interface', 'extensions'),
              'manifest')
    require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', manifest['name'])
            and len(manifest['name']) <= 64, 'Invalid plugin name')
    require(re.fullmatch(r'\d+\.\d+\.\d+', manifest['version']), 'Invalid release version')
    text(manifest['description'], 4000, 'description')
    only_keys(manifest['author'], ('name', 'email', 'url'), 'author')
    text(manifest['author']['name'], 120, 'publisher')
    text(manifest['author']['email'], 320, 'support email')
    for url in (manifest['homepage'], manifest['repository'], manifest['author']['url']):
        https(url)
    require(manifest['skills'] == './skills/' and manifest['mcpServers'] == './.mcp.json',
            'Missing component mappings')
    ui = manifest['interface']
    limits = {'displayName': 30, 'shortDescription': 30, 'longDescription': 4000,
              'developerName': 80, 'category': 120}
    urls = ('websiteURL', 'supportURL', 'privacyPolicyURL', 'termsOfServiceURL')
    only_keys(ui, (*limits, *urls, 'capabilities', 'defaultPrompt', 'composerIcon', 'logo'),
              'interface')
    for key, limit in limits.items():
        text(ui[key], limit, key)
    for key in urls:
        text(ui[key], 1024, key)
        https(ui[key])
    for key, count, limit in [('capabilities', 20, 120), ('defaultPrompt', 3, 128)]:
        require(isinstance(ui[key], list) and len(ui[key]) <= count, f'Invalid {key}')
        for item in ui[key]:
            text(item, limit, key)
    require(len(set(ui['defaultPrompt'])) == len(ui['defaultPrompt']), 'Duplicate prompts')
    for key in ('composerIcon', 'logo'):
        require(ui[key] == './assets/icon.png', f'Invalid {key} path')
    png = files['assets/icon.png']
    require(png[:8] == b'\x89PNG\r\n\x1a\n' and png[12:16] == b'IHDR', 'Invalid PNG')
    width, height = struct.unpack('>II', png[16:24])
    require(width == height and 48 <= width <= 4096 and len(png) <= 5 * 1024 * 1024,
            'Icon dimensions or size outside documented limits')
    skill = files['skills/slash-markets-kite-data/SKILL.md'].decode()
    require(skill.startswith('---\nname: slash-markets-kite-data\ndescription: ')
            and '\n---\n' in skill[4:] and 'run_python' in skill, 'Invalid canonical skill')
    require('Claude' not in files['README.md'].decode(), 'OpenAI README is client-specific')
    only_keys(manifest['extensions'], ('com.openai',), 'extensions')
    extension = manifest['extensions']['com.openai']
    only_keys(extension, ('review', 'publication'), 'OpenAI extension')
    review = extension['review']
    only_keys(review, ('test_cases', 'commerce', 'commerce_description', 'demo_recording_url'),
              'review (credentials belong in the portal)')
    if 'demo_recording_url' in review:
        https(review['demo_recording_url'])
    require(review['commerce'] is False, 'Unexpected commerce declaration')
    text(review['commerce_description'], 4000, 'commerce description')
    only_keys(extension['publication'], ('release_notes',), 'publication')
    text(extension['publication']['release_notes'], 4000, 'release notes')
    cases = review['test_cases']
    only_keys(cases, ('positive', 'negative'), 'test cases')
    for group, count in [('positive', 5), ('negative', 3)]:
        require(len(cases[group]) == count, f'Expected {count} {group} cases')
        for case in cases[group]:
            only_keys(case, ('description', 'prompt', 'tools_triggered', 'expected_behavior'), 'case')
            for key in ('description', 'prompt', 'expected_behavior'):
                text(case[key], 4000, key)
            if group == 'positive':
                text(case['tools_triggered'], 4000, 'tools_triggered')
    mcp = json.loads(files['.mcp.json'])
    only_keys(mcp, ('mcpServers',), 'MCP config')
    require(set(mcp['mcpServers']) == {'slash-markets'}, 'Expected exactly one MCP server')
    server = mcp['mcpServers']['slash-markets']
    only_keys(server, ('url', 'extensions'), 'MCP server (headers/secrets are forbidden)')
    require(server['url'] == 'https://mcp.slash.markets/', 'Wrong production endpoint')
    only_keys(server['extensions'], ('com.openai',), 'MCP extensions')
    only_keys(server['extensions']['com.openai'], ('auth',), 'MCP OpenAI extension')
    auth = server['extensions']['com.openai']['auth']
    require(auth == {'type': 'oauth', 'client': {'mode': 'cimd'},
                     'baseScopes': ['kite:read', 'openid', 'email']},
            'Expected OAuth CIMD preference and declared scopes; no credentials')
    return manifest


def collect(root=ROOT):
    files = {}
    for destination, source in SOURCES.items():
        path = root / source
        require(path.is_file() and not path.is_symlink(), f'Missing/unsafe source: {source}')
        require(path.resolve().is_relative_to(root.resolve()), 'Source escapes repository')
        files[destination] = path.read_bytes()
    return files


def build(output_dir, files):
    manifest = validate(files)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"{manifest['name']}-openai-{manifest['version']}.zip"
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zipped.writestr(info, data)
    with zipfile.ZipFile(archive) as zipped:
        require(zipped.testzip() is None, 'ZIP integrity check failed')
        archived = {name: zipped.read(name) for name in zipped.namelist()}
        require(archived == files, 'Archive differs from validated source payload')
        validate(archived)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{checksum}  {archive.name}\n')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    payload = collect()
    validate(payload)
    if args.check:
        print('Local package contract checks passed (not portal validation).')
    else:
        print(build(args.output_dir, payload))
        print('Archive verified. Portal upload, MCP scan, and review are still pending.')
