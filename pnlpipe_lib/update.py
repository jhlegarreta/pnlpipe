from plumbum import local, colors
import yaml
import pickle
import logging
logger = logging.getLogger(__name__)
from python_log_indenter import IndentedLoggerAdapter
log = IndentedLoggerAdapter(logger, indent_char='.')
from . import basenode
from . import dag
from . import config


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


DBDIR = config.OUTDIR / 'db'


def staticdeps(static_build):
    """Decorator for node build() methods that don't have dynamic dependencies,
    saves some boilerplate"""

    def build(self, db):
        need_deps(self, db)
        self.static_build()

    return build


def _nodebuild(node, db):
    if hasattr(node, 'build'):
        node.build(db)
    else:
        staticdeps(node.static_build)(node, db)


def _exists(node):
    return local.path(node.output()).exists()


def _dbfile(node):
    nodepath = local.path(node.output())
    if nodepath.startswith(local.cwd):
        relative = nodepath - config.OUTDIR
    else:
        relative = nodepath
    return local.path(DBDIR + '/' + relative.__str__() + '.db')


def _readDB(node):
    if not _dbfile(node).exists():
        return None
    with open(_dbfile(node), 'r') as f:
        return yaml.load(f)


def _writeDB(node, db):
    if not _dbfile(node).dirname.exists():
        _dbfile(node).dirname.mkdir()
    with open(_dbfile(node), 'w') as f:
        yaml.dump(db, f)


def need(parentNode, childNode, db):
    # log.info('Need: {}{}{}'.format(bcolors.HEADER, childNode.show(),
    #                                bcolors.ENDC))
    if not childNode.output():
        raise TypeError("{}.output() returns NoneType, make sure it returns a valid output path.".format(childNode))
    stamp = update(childNode)
    db['deps'][pickle.dumps(childNode)] = (childNode.output().__str__(), stamp)


def need_deps(node, db):
    for dep in node.deps.values():
        need(node, dep, db)


def _build(node):
    log.push()
    nodepath = local.path(node.output())
    db = {'value': None, 'deps': {}}
    if not node.deps:  # is input file
        if not nodepath.exists():
            raise Exception("{}: input path doesn't exist".format(node.output(
            )))
    else:
        nodepath.dirname.mkdir()
        log.info('Run {}.build()'.format(node.tag))
        _nodebuild(node, db)
        nodepath = local.path(node.output())
        if nodepath.exists() and \
           nodepath.is_dir() and \
           not nodepath.list():
            nodepath.delete()
        if not _exists(node):
            raise Exception('{}: output wasn\'t created'.format(nodepath))
        node.write_provenance()
    log.debug('Record value')
    db['value'] = node.stamp()
    log.debug('Node value is: {}'.format(db['value']))
    _writeDB(node, db)
    log.pop()
    return db['value']


def upToDate(node):
    log.debug('upToDate: check: {}{}{}'.format(bcolors.WARNING, node.show(), bcolors.ENDC)).push().add()

    # Source path is up to date if it exists
    if not node.deps:
        if not _exists(node):
            raise Exception("{}: input path doesn't exist".format(node.output()))
        log.pop()
        return None

    db = _readDB(node)
    currentValue = None if not _exists(node) else node.stamp()
    outdatedNode = None

    if db == None:
        reason = "Has no entry in database"
        log.debug(reason)
        outdatedNode = (node, reason)
    elif currentValue == None:
        reason = "Path is missing ({})".format(node.output())
        log.debug(reason)
        outdatedNode = (node, reason)
    elif db['value'] != currentValue:
        reason = "Value has changed"
        log.debug('old value: {}, new value: {}'.format(db['value'],
                                                        currentValue))
        log.debug(reason)
        outdatedNode = (node, reason)
    else:
        log.debug('Path exists and has not been modified')
        log.debug('Check if dependencies are unchanged:')
        changedDeps = []
        log.debug("Check subtree for modified dependencies")
        for i, (depKey, (_, dbDepValue)) in enumerate(db['deps'].items()):
            depNode = pickle.loads(depKey)
            log.debug('{}. Check: {}{}{}'.format(i+1, bcolors.WARNING, depNode.show(), bcolors.ENDC))
            # log.info('Output path: {}'.format(basenode.relativeOutput(depNode)))
            depValue = depNode.stamp()
            log.debug(
                'upToDate(): current value: {depValue}, db value: {dbDepValue}'.format(
                    **locals()))
            # We check this instead of recursing because an input path could conceivably
            # change during a run, making previously built nodes out of date.
            if (depValue != dbDepValue):
                reason = 'Has been modified'
                log.debug(reason)
                outdatedNode = (depNode, reason)
                break
            outdatedNode = upToDate(depNode)
            if outdatedNode:
                break
    log.pop()
    return outdatedNode


def update(node):
    log.info('Update: {}{}{}'.format(bcolors.HEADER, node.show(),
                                   bcolors.ENDC))

    # upToDate already has this check of a source path, but putting it here so
    # we can print a better log message
    if not node.deps:  # is input path
        if not _exists(node):
            raise Exception("{}: input path doesn't exist".format(node.output()))
        stamp = node.stamp()
        log.info('Exists: {}{}{} ({})'.format(bcolors.OKGREEN, node.show(), bcolors.ENDC, stamp))
    else: # is generated path
        log.push().add()
        outdatedNode = upToDate(node)
        if outdatedNode:
            if node.show() == outdatedNode[0].show():
                log.info("Stale: {}".format(outdatedNode[1]))
            else:
                log.info("Stale: {}: {}".format(outdatedNode[1], outdatedNode[0].show()))
            stamp = _build(node)
        else:
            stamp = node.stamp()
        log.pop()
        log.info('Done: {}{}{}'.format(bcolors.OKGREEN, node.show(), bcolors.ENDC))

    return stamp
