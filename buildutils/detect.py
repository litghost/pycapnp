"""Detect zmq version"""
#
#  Copyright (C) PyZMQ Developers
#
#  This file is part of pyzmq, copied and adapted from h5py.
#  h5py source used under the New BSD license
#
#  h5py: <http://code.google.com/p/h5py/>
#
#  Distributed under the terms of the New BSD License.  The full license is in
#  the file COPYING.BSD, distributed as part of this software.
#
#
# Adapted for use in pycapnp from pyzmq. See https://github.com/zeromq/pyzmq
# for original project.

import shutil
import sys
import os
import logging
import platform
from distutils import ccompiler
from distutils.ccompiler import get_default_compiler
import tempfile

from .misc import get_compiler, get_output_error
from .patch import patch_lib_paths

pjoin = os.path.join

#
# Utility functions (adapted from h5py: http://h5py.googlecode.com)
#


def test_compilation(cfile, compiler=None, **compiler_attrs):
    """Test simple compilation with given settings"""
    cc = get_compiler(compiler, **compiler_attrs)

    efile, _ = os.path.splitext(cfile)

    cpreargs = lpreargs = []
    if sys.platform == 'darwin':
        # use appropriate arch for compiler
        if platform.architecture()[0] == '32bit':
            if platform.processor() == 'powerpc':
                cpu = 'ppc'
            else:
                cpu = 'i386'
            cpreargs = ['-arch', cpu]
            lpreargs = ['-arch', cpu, '-undefined', 'dynamic_lookup']
        else:
            # allow for missing UB arch, since it will still work:
            lpreargs = ['-undefined', 'dynamic_lookup']
    if sys.platform == 'sunos5':
        if platform.architecture()[0] == '32bit':
            lpreargs = ['-m32']
        else:
            lpreargs = ['-m64']
    extra_compile_args = compiler_attrs.get('extra_compile_args', [])
    if os.name != 'nt':
        extra_compile_args += ['--std=c++14']
    extra_link_args = compiler_attrs.get('extra_link_args', [])
    if cc.compiler_type == 'msvc':
        extra_link_args += ['/MANIFEST']

    objs = cc.compile([cfile], extra_preargs=cpreargs, extra_postargs=extra_compile_args)
    cc.link_executable(objs, efile, extra_preargs=lpreargs, extra_postargs=extra_link_args)
    return efile


def detect_version(basedir, compiler=None, **compiler_attrs):
    """Compile, link & execute a test program, in empty directory `basedir`.

    The C compiler will be updated with any keywords given via setattr.

    Parameters
    ----------

    basedir : path
        The location where the test program will be compiled and run
    compiler : str
        The distutils compiler key (e.g. 'unix', 'msvc', or 'mingw32')
    **compiler_attrs : dict
        Any extra compiler attributes, which will be set via ``setattr(cc)``.

    Returns
    -------

    A dict of properties for zmq compilation, with the following two keys:

    vers : tuple
        The ZMQ version as a tuple of ints, e.g. (2,2,0)
    settings : dict
        The compiler options used to compile the test function, e.g. `include_dirs`,
        `library_dirs`, `libs`, etc.
    """
    if compiler is None:
        compiler = get_default_compiler()
    cfile = pjoin(basedir, 'vers.cpp')
    shutil.copy(pjoin(os.path.dirname(__file__), 'vers.cpp'), cfile)

    # check if we need to link against Realtime Extensions library
    if sys.platform.startswith('linux'):
        cc = ccompiler.new_compiler(compiler=compiler)
        cc.output_dir = basedir
        if not cc.has_function('timer_create'):
            if 'libraries' not in compiler_attrs:
                compiler_attrs['libraries'] = []
            compiler_attrs['libraries'].append('rt')

    cc = get_compiler(compiler=compiler, **compiler_attrs)
    efile = test_compilation(cfile, compiler=cc)
    patch_lib_paths(efile, cc.library_dirs)

    rc, so, se = get_output_error([efile])
    if rc:
        msg = "Error running version detection script:\n%s\n%s" % (so, se)
        logging.error(msg)
        raise IOError(msg)

    handlers = {'vers': lambda val: tuple(int(v) for v in val.split('.'))}

    props = {}
    for line in (x for x in so.split('\n') if x):
        key, val = line.split(':')
        props[key] = handlers[key](val)

    return props


def test_build(**compiler_attrs):
    """do a test build of libcapnp"""
    tmp_dir = tempfile.mkdtemp()

    # line()
    # info("Configure: Autodetecting Cap'n Proto settings...")
    # info("    Custom Cap'n Proto dir:       %s" % prefix)
    try:
        detected = detect_version(tmp_dir, None, **compiler_attrs)
    finally:
        erase_dir(tmp_dir)

    # info("    Cap'n Proto version detected: %s" % v_str(detected['vers']))

    return detected


def erase_dir(path):
    """Erase directory"""
    try:
        shutil.rmtree(path)
    except Exception:
        pass
