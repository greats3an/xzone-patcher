from io import BytesIO
from zipfile import ZipFile
import gamedata,logging,hashlib,zlib,os,sys,shutil,pathlib,struct
logging.basicConfig(level=0)
from config import *
#===================
# Setup
#==================
RELPATH = {
    'bin/emulib2.dll':'{bin}/emulib2.dll',
    'bin/emulib3.dll':'{bin}/emulib3.dll',
    'bin/emulib4.dll':'{bin}/emulib4.dll',
    'resource/roms.md5':'{resource}/roms.md5',
    'resource/res/rom_md5.xml':'{resource}/res/rom_md5.xml',
}
def locate_xzone(xpath : str,_iter=0):    
    if _iter > 5:
        raise FileNotFoundError("Cannot find X-Zone.")
    dirs = os.listdir(xpath)
    if 'bin' in dirs and 'resource' in dirs:
        bin_ = os.path.join(xpath,'bin')
        resource_ = os.path.join(xpath,'resource')
        return {'bin':bin_,'resource':resource_}
    else:
        # try to find it upper level
        xpath = pathlib.Path(xpath).parent
        return locate_xzone(xpath,_iter + 1)
    

def match_by_filename(fname : str) -> gamedata.__archive:
    for archn in filter(lambda n:'__' not in n,dir(gamedata)):
        arch : gamedata.__archive = getattr(gamedata,archn)
        if arch.FILENAME == fname:
            return arch
    return False

def md5sum(fname : str):
    md5sum = hashlib.md5()
    with open(fname,'rb') as f:
        while chunk:=f.read():
            md5sum.update(chunk)
    return md5sum

def crc32(fname : str):
    crc=0x0
    with open(fname,'rb') as f:
        while chunk:=f.read():
            crc=zlib.crc32(chunk,crc)
    return crc & 0xFFFFFFFF

def extract(fname : str):
    logging.info('Extracting: %s' % fname)
    with ZipFile(fname,'r') as arch:
        arch.extractall('./extracted')
    return logging.debug('Extraction complete') or True

def cleandir(dirname : str):
    if os.path.isdir(dirname):
        shutil.rmtree(dirname)
    os.mkdir(dirname)        
    return True

def cuint32(i : int):    
    return struct.pack('<L',i & 0xFFFFFFFF)

def find_and_patch(src:bytearray,pattern:bytes,repl:bytes,offset=0):
    index = src.find(pattern,offset)
    if index < 0:
        return offset
    logging.debug('Located at %s,patched.' % index)
    src[index:index+len(repl)] = repl
    return find_and_patch(src,pattern,repl,index + len(repl))

# Locating X-Zone & filling the blanks
try:
    zone = locate_xzone(xzone)
    for k,v in RELPATH.items():
        RELPATH[k] = v.format(**zone)
except FileNotFoundError as e:
    logging.critical(e)
    sys.exit(2)
logging.info('X-Zone setup successfully located.')
archive = match_by_filename(game)
if not archive:
    logging.critical('Target file not supported (%s)' % game)

md5hash = md5sum(game).hexdigest()
logging.info('====================================')
logging.info('= GAME     : %s' % archive.GAMENAME)
logging.info('= ZIPNAME  : %s' % archive.FILENAME)
logging.info('= MD5 HASH : %s' % md5hash)
logging.info('====================================')

# Extracting files
logging.debug('Cleaning up')
cleandir('./extracted')
if not extract(game):
    logging.critical('Extraction failed,aborting.')
# Calculating & Comparing CRC
logging.debug('Calculating CRC')
crc = dict()
for simm in os.listdir('./extracted'):
    crc[simm] = crc32('./extracted/%s' % simm)
# Checking ROM integrity
dirty=False
crc_patches=[]
for fname,crc_ in archive.CRC32.items():
    if not fname in crc:
        logging.critical('Cannot find %s' % fname) ; dirty=True
        continue
    if not crc_ == crc[fname]:
        logging.warning('Mismatched CRC (%s vs %s) for %s, will be patched.' % (crc_,crc[fname],fname))
        crc_patches.append((crc_,crc[fname]))
    else:
        logging.debug('Matched CRC for %s' % fname)

if dirty:
    logging.critical('ROM is either incomplete or severly damaged. Not proceeding.')
    sys.exit(2)

# Gather files
logging.debug('Gathering X-Zone files')
cleandir('./xzone') and cleandir('./xzone/bin') and cleandir('./xzone/resource') and cleandir('./xzone/resource/res') and cleandir('./xzone/resource/roms')
for k,v in RELPATH.items():
    shutil.copyfile(v,'./xzone/%s'%k)
logging.info('Files copied')

# ! PATCH 1 : Emulib
# pre-process -> uint32 values
crc_patches = [ (cuint32(orig),cuint32(patch)) for orig,patch in crc_patches]
if crc_patches:
    for emulib in os.listdir('./xzone/bin'):
        emu = './xzone/bin/%s' % emulib
        logging.info('Patching %s' % emu)  
        raw = bytearray(open(emu,'rb').read())
        for orig,patch in crc_patches:
            logging.debug('... patching crc %s -> %s' % (orig.hex(),patch.hex()) )
            offset = find_and_patch(raw,orig,patch)
            if not offset:logging.warning('crc not found, passing')
        open(emu,'wb').write(raw)
        logging.info('Patched %s' % emu)  
# ! PATCH 2 : MD5 sum
# patch roms.md5
lines = []
with open('./xzone/resource/roms.md5') as f:
    lines = f.readlines()
    for i in range(0,len(lines)):
        if game in lines[i]:
            lines[i] = '%s = %s' % (md5hash,game)
            logging.info('Patched roms.md5 ,line %s' % i)
        lines[i] = lines[i].strip()
    lines = '\x0a'.join(lines)
open('./xzone/resource/roms.md5','w').write(lines)
# patch rom_md5.xml
lines = []
with open('./xzone/resource/res/rom_md5.xml') as f:
    lines = f.readlines()
    for i in range(0,len(lines)):
        if game in lines[i]:
            lines[i] = '    <item name="%s" value="%s" />' % (game,md5hash)
            logging.info('Patched rom_md5.xml ,line %s' % i)
        lines[i] = lines[i].strip()
    lines = '\x0a'.join(lines)
open('./xzone/resource/res/rom_md5.xml','w').write(lines)
shutil.copy('./jojoban.zip','./xzone/resource/roms/jojoban.zip')
logging.info('Patching complete. Be sure to overwrite the installation with files within `xzone`')