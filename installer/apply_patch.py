#!/usr/bin/env python3
"""Build verified patched RPFs without changing the input game or save files."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path

BLOCK=4*1024*1024
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(BLOCK),b''):h.update(block)
    return h.hexdigest()
def inside(root,relative):
    path=(root/relative).resolve()
    if not path.is_relative_to(root):raise ValueError('Unsafe path in manifest')
    return path
def transfer(source,target,count):
    h=hashlib.sha256();remaining=count
    while remaining:
        block=source.read(min(BLOCK,remaining))
        if not block:raise ValueError('Unexpected end of input')
        target.write(block);h.update(block);remaining-=len(block)
    return h.hexdigest()
def apply(manifest,game,output,payload_dir):
    game=game.resolve();output=output.resolve();payload_dir=payload_dir.resolve()
    data=json.loads(manifest.read_text('utf-8-sig'))
    if data.get('format')!='fuzzy-range-patch-v1':raise ValueError('Unsupported patch format')
    files=data['files'];assert files
    # Validate every source and archive before producing any output.
    for item in files:
        source=inside(game,item['path']);target=inside(output,item['path'])
        if source==target:raise ValueError('Input and output must be different')
        if target.exists() or target.with_suffix(target.suffix+'.partial').exists():raise ValueError('Output exists: '+str(target))
        if not source.is_file() or source.stat().st_size!=item['source_bytes'] or digest(source)!=item['source_sha256']:
            raise ValueError('Wrong source version: '+str(source)+'. Use unmodified data for the supported build.')
        for part in item['parts']:
            archive=inside(payload_dir,part['archive'])
            with zipfile.ZipFile(archive) as z:
                if z.getinfo(part['entry']).file_size!=part['bytes']:raise ValueError('Incorrect payload size')
        print('Source verified:',item['path'],flush=True)
    for item in files:
        source=inside(game,item['path']);target=inside(output,item['path']);target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_suffix(target.suffix+'.partial')
        with source.open('rb') as original,temporary.open('xb') as out:
            out.truncate(item['target_bytes'])
            for region in item['copies']:
                original.seek(region['source_offset']);out.seek(region['offset']);transfer(original,out,region['bytes'])
            for part in item['parts']:
                out.seek(part['offset'])
                with zipfile.ZipFile(inside(payload_dir,part['archive'])) as z,z.open(part['entry']) as incoming:
                    actual=transfer(incoming,out,part['bytes'])
                    if actual!=part['sha256']:raise ValueError('Damaged payload: '+part['entry'])
        if digest(temporary)!=item['target_sha256']:raise ValueError('Output verification failed: '+str(temporary))
        temporary.rename(target)
        print('Output verified:',item['path'],flush=True)
    print('Done. Close the game and launcher, then merge these files into the active game folder:',output)
    return data
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--game',required=True,type=Path,help='Original game folder containing android/ and update/')
    parser.add_argument('--output',required=True,type=Path,help='A separate empty output game folder')
    parser.add_argument('--payload-dir',type=Path,help='Folder containing the downloaded ZIP payloads')
    args=parser.parse_args()
    apply(args.manifest,args.game,args.output,args.payload_dir or args.manifest.parent)
if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,zipfile.BadZipFile) as error:print('ERROR:',error,file=sys.stderr);sys.exit(1)
