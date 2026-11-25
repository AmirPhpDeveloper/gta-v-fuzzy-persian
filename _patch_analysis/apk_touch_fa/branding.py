import struct,io
from PIL import Image

def replace_strings(data,replacements):
    root_header=struct.unpack_from('<H',data,2)[0]
    result=bytearray(data[:root_header]);pos=root_header;replaced=0
    while pos<len(data):
        kind,header,size=struct.unpack_from('<HHI',data,pos);chunk=data[pos:pos+size]
        if kind==1:
            count,styles,flags,start,style_start=struct.unpack_from('<5I',chunk,8)
            offsets=struct.unpack_from('<%dI'%count,chunk,header)
            def length(p,wide):
                if wide:
                    value=struct.unpack_from('<H',chunk,p)[0];p+=2
                    if value&0x8000:value=((value&0x7fff)<<16)|struct.unpack_from('<H',chunk,p)[0];p+=2
                else:
                    value=chunk[p];p+=1
                    if value&128:value=((value&127)<<8)|chunk[p];p+=1
                return value,p
            def encoded_length(n,wide):
                if wide:return struct.pack('<H',n) if n<0x8000 else struct.pack('<HH',0x8000|(n>>16),n&0xffff)
                return bytes([n]) if n<128 else bytes([128|(n>>8),n&255])
            blob=bytearray();new_offsets=[]
            for offset in offsets:
                p=start+offset
                if flags&256:
                    units,p=length(p,False);n,p=length(p,False);s=chunk[p:p+n].decode('utf-8')
                else:
                    units,p=length(p,True);s=chunk[p:p+2*units].decode('utf-16le')
                if s in replacements:s=replacements[s];replaced+=1
                new_offsets.append(len(blob));units=len(s.encode('utf-16le'))//2
                if flags&256:
                    raw=s.encode('utf-8');blob.extend(encoded_length(units,False)+encoded_length(len(raw),False)+raw+b'\0')
                else:blob.extend(encoded_length(units,True)+s.encode('utf-16le')+b'\0\0')
            blob.extend(b'\0'*((-len(blob))%4))
            prefix=bytearray(chunk[:start]);struct.pack_into('<%dI'%count,prefix,header,*new_offsets)
            if style_start:struct.pack_into('<I',prefix,24,start+len(blob))
            chunk=prefix+blob+(chunk[style_start:] if style_start else b'')
            struct.pack_into('<I',chunk,4,len(chunk))
        result.extend(chunk);pos+=size
    assert replaced==len(replacements),(replaced,len(replacements))
    struct.pack_into('<I',result,4,len(result));return bytes(result)

def manifest_label(data,label):
    return replace_strings(data,{'Grand Theft Auto V':label})

def icon_png(image_path,original_png):
    size=Image.open(io.BytesIO(original_png)).size
    im=Image.open(image_path).convert('RGBA').resize(size,Image.Resampling.LANCZOS)
    stream=io.BytesIO();im.save(stream,format='PNG',optimize=True);return stream.getvalue()
