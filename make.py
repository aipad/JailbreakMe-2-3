#!/usr/bin/env python
# encoding: utf-8
from fabricate import *
import fabricate
def hybrid_hasher(filename):
    try:
        return (mtime_hasher if os.path.getsize(filename) > 1048576 else md5_hasher)(filename)
    except (IOError, OSError):
        return None
fabricate.default_builder.hasher = hybrid_hasher
fabricate.default_builder.deps # do this before we chdir
import sys, os, re, glob, traceback, shutil, tempfile, zlib

ROOT = os.path.realpath(os.path.dirname(sys.argv[0]))

installer_version = '3'
package_version = '3'

use_null = True

# configgy
def set_firmware(firmware=None, lndir=False):
    global iversion, device, version, build_num, is_armv7, BUILD_ROOT, BS
    if firmware is None:
        BS = os.readlink(ROOT + '/config/cur')
        firmware = BS.strip('/').split('/')[-1]
    else:
        BS = ROOT + '/bs/' + firmware
    device, version, build_num = re.match('(i[A-Z][a-z]+[0-9],[0-9x])_([0-9\.]+)_([A-Z0-9]+)', firmware).groups()
    is_armv7 = device not in ['iPhone1,1', 'iPhone1,2', 'iPod1,1', 'iPod2,1']
    bits = version.split('.') + [0, 0]
    iversion = int(bits[0]) * 0x10000 + int(bits[1]) * 0x100 + int(bits[2])
    if lndir:
        BUILD_ROOT = os.path.realpath(ROOT + '/config/build-' + firmware)
        if not os.path.exists(BUILD_ROOT): os.mkdir(BUILD_ROOT)
    else:
        BUILD_ROOT = ROOT


    global GCC_FLAGS, SDK, BIN, GCC_BIN, GCC_BASE, GCC, GCC_UNIVERSAL, GCC_ARMV6, GCC_NATIVE, HEADERS
    GCC_FLAGS = ['-std=gnu99', '-g3', '-Werror', '-Wimplicit', '-Wuninitialized', '-Wall', '-Wextra', '-Wreturn-type', '-Wno-unused', '-Os']
    SDK = '/var/sdk'
    BIN = '/Developer/Platforms/iPhoneOS.platform/Developer/usr/bin'
    GCC_BIN = BIN + '/gcc-4.2'
    GCC_BASE = [GCC_BIN, GCC_FLAGS, '-isysroot', SDK, '-F'+SDK+'/System/Library/Frameworks', '-F'+SDK+'/System/Library/PrivateFrameworks', '-I', ROOT, '-fblocks', '-mapcs-frame', '-fomit-frame-pointer']
    GCC = [GCC_BASE, '-arch', ('armv7' if is_armv7 else 'armv6'), '-mthumb', '-DVERSION=0x%x' % iversion]
    if 'iPad2' in device: GCC.append('-DIPAD2=1')
    GCC_UNIVERSAL = [GCC_BASE, '-arch', 'armv6', '-arch', 'armv7', '-mthumb']
    #GCC_ARMV6 = [GCC_BASE, '-arch', 'armv6', '-mthumb']
    GCC_ARMV6 = [GCC_BASE, '-arch', 'armv7', '-mthumb']
    GCC_NATIVE = ['gcc', '-arch', 'i386', '-arch', 'x86_64', GCC_FLAGS]
    HEADERS = ROOT + '/headers'

    if os.path.exists(BS+'/kern0') and not os.path.exists(BS+'/kern'):
        make('datautils0', 'native')
        goto('.')
        run('datautils0/native/grapher', BS+'/kern0', '--matchB', glob.glob(re.sub('_[^_]*$', '_*/kern', re.sub('2,[0-9]', '1,1', BS)))[0], '--vt', '--manual', '_lck_mtx_unlock', 'pattern', '- 5a f0 7f f5 00 20 a0 e3 90 cf 1d ee', BS+'/kern')
        assert os.path.exists(BS+'/kern')
def tmp(x):
    x = os.path.join(os.getcwd(), x)
    if ROOT is not BUILD_ROOT: x = x.replace(ROOT, BUILD_ROOT) 
    return x


def goto(dir):
    if ROOT is not BUILD_ROOT: shell('mkdir', '-p', os.path.join(BUILD_ROOT, dir))
    os.chdir(os.path.join(ROOT, dir))

def chext(f, ext):
    return f[:f.find('.')] + ext

def install():
    goto('install')
    compile_stuff(['install.m'], 'install-%s.dylib' % installer_version, gcc=GCC_ARMV6, cflags=['-I../headers', '-fblocks', '-DUSE_NULL=%d' % use_null], ldflags=['-framework', 'Foundation', '-framework', 'GraphicsServices', '-framework', 'MobileCoreServices', '-L.', '-ltar', '-llzma', '-dynamiclib'])

def locutus():
    install()
    adler = zlib.adler32(open('install-%s.dylib' % installer_version).read()) & 0xffffffff
    goto('locutus')
    cflags = ['-DFNO_ASSERT_MESSAGES', '-DPACKAGE_VERSION="%s"' % package_version, '-DINSTALLER_VERSION="%s"' % installer_version, '-fblocks', '-Oz', '-Wno-parentheses', '-miphoneos-version-min=4.0', '-Wno-deprecated-declarations']
    compile_stuff(['locutus_server.m'], tmp('locutus_server.dylib'), gcc=GCC, cflags=cflags, ldflags=['-dynamiclib', '-framework', 'Foundation', '-framework', 'UIKit', '-install_name', 'X'*32]+cflags, ldid=False)
    run('sh', '-c', 'xxd -i "%s" | sed "s/[l_].*dylib/dylib/g" > "%s"' % (tmp('locutus_server.dylib'), tmp('locutus_server_.c')))
    compile_stuff(['locutus.c', 'inject.c', 'baton.S',  tmp('locutus_server_.c')], tmp('locutus'), gcc=GCC_ARMV6, cflags=cflags+['-DINSTALL_ADLER=%u' % adler], ldflags=['-lz', '-framework', 'CoreFoundation', '-framework', 'CFNetwork', '-framework', 'Foundation']+cflags, ldid=True, ent='ent.plist')
build = locutus


def catalog():
    make('data', 'universal')
    make('datautils0', 'universal')
    goto('catalog')
    run('../datautils0/universal/make_kernel_patchfile', BS+'/kern', tmp('patchfile'))

def catalog_dejavu():
    goto('catalog')
    catalog()
    run(GCC, '-c', '-o', tmp('kcode_dejavu.o'), 'kcode.S', '-Oz', '-DDEJAVU')
    run('python', 'catalog.py', 'dejavu', device, version, BS+'/cache', BS+'/kern', tmp('patchfile'), tmp('kcode_dejavu.o'), tmp('catalog.txt'))

def catalog_untether():
    catalog()
    run(GCC, '-c', '-o', tmp('kcode_two.o'), 'kcode.S', '-Oz')
    run('python', 'catalog.py', 'untether', device, version, BS+'/cache', BS+'/kern', tmp('patchfile'), tmp('kcode_two.o'), tmp('two.txt'))

def untether():
    catalog_untether()
    goto('catalog')
    run('python', '../goo/two.py', BS+'/cache', tmp('two.txt'), tmp('untether'))

def pdf(files=None):
    dejavu(files)
    goto('pdf')
    run('python', 'mkpdf.py', tmp('../dejavu/dejavu.pfb'), tmp('out.pdf'))

def compile_stuff(files, output, ent='', cflags=[], ldflags=[], strip=True, gcc=None, ldid=True, combine=False):
    if gcc is None: gcc = GCC
    objs = []
    output_ = (output + '_' if strip or ldid else output)
    if combine:
        run(gcc, '-o', output_, files, cflags, ldflags, '-dead_strip', '-combine', '-fwhole-program')
    else:
        for inp in files:
            obj = chext(os.path.basename(inp), '.o')
            if BUILD_ROOT in output: obj = tmp(obj)
            objs.append(obj)
            if obj == inp: continue
            run(gcc, '-c', '-o', obj, inp, cflags)
        run(gcc, '-o', output_, objs, ldflags, '-dead_strip')
    if strip or ldid:
        commands = [['cp', output + '_', output]]
        if strip: commands.append(['strip', '-x' if 'dylib' in output else '-ur', output])
        if ldid: commands.append(['ldid', '-S' + ent, output])
        run_multiple(*commands)

def chain():
    goto('chain')
    cf = ['-marm', '-DUSE_ASM_FUNCS=0', '-fblocks']
    ldf=['-dynamiclib', '-nostdlib', '-nodefaultlibs', '-lgcc', '-undefined', 'dynamic_lookup', '-read_only_relocs', 'suppress']
    compile_stuff(['chain.c', 'dt.c', 'stuff.c', 'fffuuu.S', 'putc.S', 'annoyance.S', 'bcopy.s', 'bzero.s', 'what.s'], 'chain-kern.dylib', cflags=cf, ldflags=ldf, strip=False)
    compile_stuff(['chain-user.c'], 'chain-user', ldflags=['-framework', 'IOKit', '-framework', 'CoreFoundation'])

def make(path, build, *targets):
    goto(path)
    run('make', 'BUILD='+build, *targets)

def sandbox2():
    goto('sandbox2')
    run(GCC_ARMV6, '-c', '-o', tmp('sandbox.o'), 'sandbox.S')

def fs():
    goto('fs')
    crap = [GCC, '-dynamiclib', '-g3',  '-fwhole-program', '-combine', '-nostdinc', '-nodefaultlibs', '-lgcc', '-Wno-error', '-Wno-parentheses', '-Wno-format', '-I.', '-Ixnu', '-Ixnu/bsd', '-Ixnu/libkern', '-Ixnu/osfmk', '-Ixnu/bsd/i386', '-Ixnu/bsd/sys', '-Ixnu/EXTERNAL_HEADERS', '-Ixnu/osfmk/libsa', '-D__i386__', '-DKERNEL', '-DKERNEL_PRIVATE', '-DBSD_KERNEL_PRIVATE', '-D__APPLE_API_PRIVATE', '-DXNU_KERNEL_PRIVATE', '-flat_namespace', '-undefined', 'dynamic_lookup', '-fno-builtin-printf', '-fno-builtin-log', '-DNULLFS_DIAGNOSTIC', '-dead_strip']
    #run(*(crap + ['-o', tmp('nullfs.dylib'), 'kpi_vfs.c', 'null/null_subr.c', 'null/null_vfsops.c', 'null/null_vnops.c']))
    run(*(crap + ['-o', tmp('union.dylib'), 'kpi_vfs.c', 'union/union_subr.c', 'union/union_vfsops.c', 'union/union_vnops.c', 'union/splice.c']))

def mroib():
    goto('mroib')
    run(GCC, '-c', '-o', 'clean.o', 'clean.c', '-marm')
    run(GCC, '-dynamiclib', '-o', 'mroib.dylib', 'power.c', 'timer.c', 'usb.c', 'mroib.c', 'clean.o', '-combine', '-fwhole-program', '-nostdinc', '-nodefaultlibs', '-lgcc', '-undefined', 'dynamic_lookup', '-I.', '-Iincludes', '-DCONFIG_IPHONE_4G')

def dejavu(files=None):
    locutus()
    goto('catalog')
    if files is None:
        catalog_dejavu()
        files = [tmp('catalog.txt')]
    goto('dejavu')
    run('python', 'gen_dejavu.raw.py', tmp('dejavu.raw'), tmp('../locutus/locutus'), *files)
    run('t1asm', tmp('dejavu.raw'), tmp('dejavu.pfb'))

def white():
    make('data', 'universal')
    make('white', 'universal', 'universal', 'universal/white_loader')
    #make('data', 'armv6')
    make('data', 'armv7')
    goto('white')
    run_multiple([GCC_ARMV6, '-o', 'white_loader', 'white_loader.c', '../data/armv7/libdata.a', '-DMINIMAL', '-Wno-parentheses'],
                 ['strip', '-ur', 'white_loader'],
                 ['ldid', '-Sent.plist', 'white_loader'])

#def humanify_device(device):
#    return {
#        'iPhone1,1': 'iPhone',
#        'iPhone1,2': 'iPhone 3G',
#        'iPhone2,1': 'iPhone 3GS',
#        'iPhone3,1': 'iPhone 4 GSM',
#        'iPhone3,3': 'iPhone 4 CDMA',
#        'iPod1,1
#    }[device]

def starstuff():
    fs()
    white()
    untether()
    goto('starstuff')
    compile_stuff(['mount_nulls.c'], 'mount_nulls', ldid=True, gcc=GCC_ARMV6, cflags='-DUSE_NULL=%d' % use_null)
    if use_null:
        run('../white/universal/white_loader', '-k', BS+'/kern', '-p', tmp('../fs/union.dylib'), tmp('union_prelink.dylib'))
    package = 'saffron-jailbreak-%s-%s' % (device, build_num)
    package_name = '%s %s JailbreakMe 3.0' % (build_num, device)
    run('bash', 'build-archive.sh', tmp('.'), package, package.replace(',', '.').lower(), '%d' % use_null, package_version, package_name)
    

def stage(string=None):
    all_devices = ['iPhone3,1', 'iPhone3,3', 'iPod4,1', 'iPad2,1', 'iPad2,2', 'iPad2,3', 'iPhone2,1', 'iPod3,1', 'iPad1,1', 'iPhone1,2', 'iPod2,1']
    armv6_devices = ['iPhone1,2', 'iPod1,1', 'iPod2,1']
    install() 
    goto('.')
    goto('bs')
    available = set(re.sub('[0-9],[0-9]', '', i) for i in glob.glob('*_*')) if string is None else [string]
    succeeded = []
    failed = []
    for string in available:
        basetype, version = string.split('_', 1)
        goto('bs')
        firmwares = glob.glob(basetype + '*_' + version)

        eligible = []
        outpdf = '%s/pdf/%s-%s.pdf' % (ROOT, string, installer_version)
        for firmware in firmwares:
            device = firmware[:firmware.find('_')]
            if device in all_devices:
                print '** Building %s for %s' % (firmware, outpdf)
                set_firmware(firmware, True)
                try:
                    starstuff()
                    catalog_dejavu()
                    goto('catalog')
                    eligible.append(tmp('catalog.txt'))
                    succeeded.append(firmware)
                except Exception, e:
                    print '** Failed: %s' % str(e)
                    failed.append(firmware)
        if eligible == []: continue
        try:
            pdf(eligible)
        except Exception, e:
            print '** pdf(...) failed: %s' % string
            failed.append(string)
        else:
            shutil.copy(tmp('out.pdf'), outpdf)
    print '** Done...'
    print 'succeeded:', succeeded
    print 'failed:', failed

def foo():
    run('touch', 'foo')

def lndir():
    set_firmware(lndir=True)

def clean():
    goto('.')
    shell('rm', '-f', 'pdf/*.pdf')
    for d in ['data', 'datautils0', 'white']:
        make(d, '', 'clean')
    autoclean()

try:
    set_firmware()
except OSError:
    pass

main()
