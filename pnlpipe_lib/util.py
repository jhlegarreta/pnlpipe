from __future__ import print_function
import sys
import os as _os
import warnings as _warnings
import hashlib
from tempfile import mkdtemp
from plumbum import local
from plumbum.commands.modifiers import ExecutionModifier
import logging
from python_log_indenter import IndentedLoggerAdapter
logger = logging.getLogger(__name__)
log = IndentedLoggerAdapter(logger, indent_char='.')

def concat(l):
    return l if l == [] else [item for sublist in l for item in sublist]


class LOG(ExecutionModifier):
    __slots__ = ("retcode", "timeout")

    def __init__(self, retcode=0, timeout=None, extra=None):
        self.retcode = retcode
        self.timeout = timeout

    def __rand__(self, cmd):
        from .update import log as updatelog
        # if log.indent_level != updatelog.indent_level - 1:
        if log.indent_level != updatelog.indent_level - 1:
            log.pop(99)
            log.add(updatelog.indent_level)
        log.info('  {}'.format(cmd))
        cmd(retcode=self.retcode,
            stdin=None,
            stdout=None,
            stderr=None,
            timeout=self.timeout)


LOG = LOG()



class MissingInputPathsKeyException(Exception):
    pass

class TemporaryDirectory(object):
    """Create and return a temporary directory.  This has the same
    behavior as mkdtemp but can be used as a context manager.  For
    example:

        with TemporaryDirectory() as tmpdir:
            ...

    Upon exiting the context, the directory and everything contained
    in it are removed.
    """

    def __init__(self, suffix="", prefix="tmp", dir=None):
        self._closed = False
        self.name = None # Handle mkdtemp raising an exception
        self.name = mkdtemp(suffix, prefix, dir)

    def __repr__(self):
        return "<{} {!r}>".format(self.__class__.__name__, self.name)

    def __enter__(self):
        return local.path(self.name)

    def cleanup(self, _warn=False):
        if self.name and not self._closed:
            try:
                self._rmtree(self.name)
            except (TypeError, AttributeError) as ex:
                # Issue #10188: Emit a warning on stderr
                # if the directory could not be cleaned
                # up due to missing globals
                if "None" not in str(ex):
                    raise
                print("ERROR: {!r} while cleaning up {!r}".format(ex, self,),
                      file=_sys.stderr)
                return
            self._closed = True
            if _warn:
                self._warn("Implicitly cleaning up {!r}".format(self),
                           ResourceWarning)

    def __exit__(self, exc, value, tb):
        self.cleanup()

    def __del__(self):
        # Issue a ResourceWarning if implicit cleanup needed
        self.cleanup(_warn=True)

    # XXX (ncoghlan): The following code attempts to make
    # this class tolerant of the module nulling out process
    # that happens during CPython interpreter shutdown
    # Alas, it doesn't actually manage it. See issue #10188
    _listdir = staticmethod(_os.listdir)
    _path_join = staticmethod(_os.path.join)
    _isdir = staticmethod(_os.path.isdir)
    _islink = staticmethod(_os.path.islink)
    _remove = staticmethod(_os.remove)
    _rmdir = staticmethod(_os.rmdir)
    _warn = _warnings.warn

    def _rmtree(self, path):
        # Essentially a stripped down version of shutil.rmtree.  We can't
        # use globals because they may be None'ed out at shutdown.
        for name in self._listdir(path):
            fullname = self._path_join(path, name)
            try:
                isdir = self._isdir(fullname) and not self._islink(fullname)
            except OSError:
                isdir = False
            if isdir:
                self._rmtree(fullname)
            else:
                try:
                    self._remove(fullname)
                except OSError:
                    pass
        try:
            self._rmdir(path)
        except OSError:
            pass
