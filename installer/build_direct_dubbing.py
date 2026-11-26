"""Reconstruct ready-to-copy SFX RPFs from the original data ZIP and dubbing payloads."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '_patch_analysis'))
from rpf_index import read_index
from apply_patch import digest, transfer


def build(source_zip, payload_dir, output, report):
    manifest = json.loads((ROOT / 'manifests/dubbing.json').read_text('utf-8'))
    output = output.resolve()
    results = []
    with zipfile.ZipFile(source_zip) as original:
        for item in manifest['files']:
            name = Path(item['path']).name
            target = output / 'sfx' / name
            temporary = target.with_suffix('.rpf.partial')
            if target.exists():
                if digest(target) != item['target_sha256']:
                    raise ValueError('Existing output differs: ' + str(target))
            else:
                if temporary.exists():
                    raise ValueError('Partial output exists: ' + str(temporary))
                member = 'com.thegwchr.fuzzy/files/game/' + item['path']
                if original.getinfo(member).file_size != item['source_bytes']:
                    raise ValueError('Wrong original size: ' + name)
                if item['copies'] != [{'source_offset': 0, 'offset': 0, 'bytes': item['source_bytes']}]:
                    raise ValueError('Unsupported copy layout')
                target.parent.mkdir(parents=True, exist_ok=True)
                with original.open(member) as src, temporary.open('xb') as dst:
                    if transfer(src, dst, item['source_bytes']) != item['source_sha256']:
                        raise ValueError('Wrong original hash: ' + name)
                    dst.truncate(item['target_bytes'])
                    for part in item['parts']:
                        archive = (payload_dir / part['archive']).resolve()
                        if archive.parent != payload_dir.resolve():
                            raise ValueError('Unsafe payload path')
                        with zipfile.ZipFile(archive) as z:
                            if z.getinfo(part['entry']).file_size != part['bytes']:
                                raise ValueError('Wrong payload size')
                            dst.seek(part['offset'])
                            with z.open(part['entry']) as src:
                                if transfer(src, dst, part['bytes']) != part['sha256']:
                                    raise ValueError('Wrong payload hash')
                if temporary.stat().st_size != item['target_bytes'] or digest(temporary) != item['target_sha256']:
                    raise ValueError('Wrong reconstructed hash: ' + name)
                temporary.rename(target)
            index = read_index(target)
            replaced = 0
            for entry in index['entries']:
                if entry['kind'] != 'binary':
                    continue
                offset = entry['file_offset_sector'] * 512
                length = entry['stored_size'] or entry['uncompressed_size']
                if offset + length > item['target_bytes']:
                    raise ValueError('Entry outside archive: ' + name)
                if offset >= item['source_bytes']:
                    if entry['encrypted'] or entry['stored_size']:
                        raise ValueError('Unexpected encoded AWC')
                    with target.open('rb') as f:
                        f.seek(offset)
                        if f.read(4) not in (b'ADAT', b'TADA'):
                            raise ValueError('Invalid replacement AWC: ' + name)
                    replaced += 1
            results.append({'file': 'sfx/' + name, 'bytes': item['target_bytes'],
                            'sha256': item['target_sha256'], 'replacement_awcs': replaced})
            print('VERIFIED', name, 'replacement AWC:', replaced, flush=True)
    if len(results) != 29 or sum(x['replacement_awcs'] for x in results) != 2216:
        raise ValueError('Incomplete dubbing set')
    # A complete replacement folder must also retain every unchanged SFX archive.
    patched_names = {Path(x['path']).name for x in manifest['files']}
    prefix = 'com.thegwchr.fuzzy/files/game/android/audio/sfx/'
    with zipfile.ZipFile(source_zip) as original:
        members = [i for i in original.infolist() if i.filename.startswith(prefix) and not i.is_dir()]
        if len(members) != 54 or len({i.filename for i in members}) != 54:
            raise ValueError('Expected exactly 54 original SFX archives')
        for member in members:
            name = member.filename[len(prefix):]
            if '/' in name or not name.endswith('.rpf'):
                raise ValueError('Unexpected source SFX member: ' + name)
            if name in patched_names:
                continue
            target = output / 'sfx' / name
            expected = hashlib.sha256()
            with original.open(member) as src:
                for block in iter(lambda: src.read(4 * 1024 * 1024), b''):
                    expected.update(block)
            expected = expected.hexdigest()
            if not target.exists():
                temporary = target.with_suffix('.rpf.partial')
                with original.open(member) as src, temporary.open('xb') as dst:
                    if transfer(src, dst, member.file_size) != expected:
                        raise ValueError('Original SFX copy failed')
                temporary.rename(target)
            if target.stat().st_size != member.file_size or digest(target) != expected:
                raise ValueError('Unchanged SFX differs: ' + name)
            results.append({'file': 'sfx/' + name, 'bytes': member.file_size,
                            'sha256': expected, 'replacement_awcs': 0})
            print('VERIFIED original', name, flush=True)
        if {x['file'] for x in results} != {'sfx/' + i.filename[len(prefix):] for i in members}:
            raise ValueError('Incomplete original SFX inventory')
    actual = sorted(p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file())
    if actual != sorted(x['file'] for x in results):
        raise ValueError('Distribution contains unexpected files')
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({'format': 'ready-to-copy-sfx', 'files': results,
                                 'total_bytes': sum(x['bytes'] for x in results),
                                 'replacement_awcs': 2216, 'complete_sfx_folder': True,
                                 'file_count': len(results), 'verification': 'PASS'}, indent=2), 'utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-zip', required=True, type=Path)
    parser.add_argument('--payload-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    build(args.source_zip, args.payload_dir, args.output, args.report)
