from config import *
from zipfile import ZipFile
import gamedata
import logging
import hashlib
import zlib
import os
import shutil
import pathlib
import struct
from stat import S_IWRITE
logging.basicConfig(level=0)
# ===================
# Setup
# ==================
RELPATH = {
    'bin/emulib2.dll': '{bin}/emulib2.dll',
    'bin/emulib3.dll': '{bin}/emulib3.dll',
    'bin/emulib4.dll': '{bin}/emulib4.dll',
    'resource/res/rom_md5.xml': '{resource}/res/rom_md5.xml',
    'resource/cfg.xml':'{resource}/cfg.xml',
    'resource/configure.xml':'{resource}/configure.xml'
}


def locate_xzone(xpath: str, _iter=0):
    if _iter > 5:
        raise FileNotFoundError("Cannot find X-Zone.")
    dirs = os.listdir(xpath)
    if 'bin' in dirs and 'resource' in dirs:
        bin_ = os.path.join(xpath, 'bin')
        resource_ = os.path.join(xpath, 'resource')
        return {'bin': bin_, 'resource': resource_}
    else:
        # try to find it upper level
        xpath = pathlib.Path(xpath).parent
        return locate_xzone(xpath, _iter + 1)


def match_by_filename(fname: str) -> gamedata.__archive:
    for archn in filter(lambda n: '__' not in n, dir(gamedata)):
        arch: gamedata.__archive = getattr(gamedata, archn)
        if arch.FILENAME == fname:
            return arch
    return False


def md5sum(fname: str):
    md5sum = hashlib.md5()
    with open(fname, 'rb') as f:
        while chunk := f.read():
            md5sum.update(chunk)
    return md5sum


def crc32(fname: str):
    crc = 0x0
    with open(fname, 'rb') as f:
        while chunk := f.read():
            crc = zlib.crc32(chunk, crc)
    return crc & 0xFFFFFFFF


def extract(fname: str):
    logging.info('Extracting: %s' % fname)
    with ZipFile(fname, 'r') as arch:
        arch.extractall('./extracted')
    return logging.debug('Extraction complete') or True


def cleandir(dirname: str):
    def on_error(func, path, exc_info):
        os.chmod(path, S_IWRITE)
        os.unlink(path)
    if os.path.isdir(dirname):
        shutil.rmtree(dirname, onerror=on_error)
    os.mkdir(dirname)
    return True


def cuint32(i: int):
    return struct.pack('<L', i & 0xFFFFFFFF)


def find_and_patch(src: bytearray, pattern: bytes, repl: bytes, offset=0):
    index = src.find(pattern, offset)
    if index < 0:
        return offset
    logging.debug('Located at %s,patched.' % index)
    src[index:index+len(repl)] = repl
    return find_and_patch(src, pattern, repl, index + len(repl))

def find_line_contains(lines,pattern : str):    
    for index in range(0,len(lines)):
        if pattern in lines[index]:
            yield index

def __main__():
    # Locating X-Zone & filling the blanks
    try:
        zone = locate_xzone(xzone)
        for k, v in RELPATH.items():
            RELPATH[k] = v.format(**zone)
    except FileNotFoundError as e:
        logging.critical(e)
        return False
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
    for simm,orig in archive.CRC32.items():        
        crc[simm] = crc32('./extracted/%s' % simm)
    # Checking ROM integrity
    dirty = False
    crc_patches = []
    for fname, crc_ in archive.CRC32.items():
        if not fname in crc:
            logging.critical('Cannot find %s' % fname)
            dirty = True
            continue
        if not crc_ == crc[fname]:
            logging.warning('Mismatched CRC (%s vs %s) for %s, will be patched.' % (
                crc_, crc[fname], fname))
            crc_patches.append((crc_, crc[fname]))
        else:
            logging.debug('Matched CRC for %s' % fname)

    if dirty:
        logging.critical(
            'ROM is either incomplete or severly damaged. Not proceeding.')
        return False

    # Gather files
    logging.debug('Gathering X-Zone files')
    cleandir('./xzone') and cleandir('./xzone/bin') and cleandir('./xzone/resource') and cleandir(
        './xzone/resource/res') and cleandir('./xzone/resource/roms')
    for k, v in RELPATH.items():
        shutil.copyfile(v, './xzone/%s' % k)
    logging.info('Files copied')

    # ! PATCH 1 : Emulib
    # pre-process -> uint32 values
    crc_patches = [(cuint32(orig), cuint32(patch))
                   for orig, patch in crc_patches]
    if crc_patches:
        for emulib in os.listdir('./xzone/bin'):
            emu = './xzone/bin/%s' % emulib
            logging.info('Patching %s' % emu)
            raw = bytearray(open(emu, 'rb').read())
            for orig, patch in crc_patches:
                logging.debug('... patching crc %s -> %s' %
                              (orig.hex(), patch.hex()))
                offset = find_and_patch(raw, orig, patch)
                if not offset:
                    logging.warning('crc not found, passing')
            open(emu, 'wb').write(raw)
            logging.info('Patched %s' % emu)
    # ! PATCH 2 : MD5 sum
    # patch rom_md5.xml
    with open('./xzone/resource/res/rom_md5.xml','r+',encoding='utf-8') as f:
        lines = f.readlines()
        for i in find_line_contains(lines,game):
            lines[i] = '    <item name="%s" value="%s" />\n' % (game, md5hash)
            logging.debug('Patched rom_md5.xml ,line %s' % i)            
            break        
        lines = ''.join(lines)
        f.seek(0)
        f.write(lines)
    # ! PATCH 3 : XZone updates    
    with open('./xzone/resource/cfg.xml','r+',encoding='utf-8') as f:
        lines = f.readlines()
        # patching out CRC check
        for i in find_line_contains(lines,'rom_md5.xml'):
            lines[i] = '        <!--%s-->' % lines[i]
            logging.debug('Patched cfg.xml, line %s' % i)            
        lines = ''.join(lines)            
        f.seek(0)
        f.write(lines)
    with open('./xzone/resource/configure.xml','r+',encoding='utf-8') as f:
        lines = f.readlines()
        # patching out cfg.xml updates
        for i in find_line_contains(lines,'remotecfg/pc/cfg.xml'):
            lines[i] = '        <!--%s-->\n' % lines[i].strip()
            logging.debug('Patched configure.xml, line %s' % i)            
        lines = ''.join(lines)            
        f.seek(0)
        f.write(lines)        
    logging.debug('Copying ROM file %s' % game)
    shutil.copy('./%s' % game, './xzone/resource/roms/%s' % game)    
    return True


if __name__ == '__main__':
    try:
        __main__() and print(
            '='*30, '补丁成功。现可将本目录下 xzone 内容覆盖至原安装目录；若欲恢复补丁请重新执行游聚安装包', '='*30, sep='\n')
    except:
        logging.critical('Critical error')
        import traceback
        traceback.print_exc()
        print('出现错误：请及时将该 traceback 提交 issues')
    input('Press ENTER to continue...')
