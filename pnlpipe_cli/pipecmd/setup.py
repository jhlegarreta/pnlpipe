from plumbum import local, cli
import pnlpipe_cli
from pnlpipe_cli import printVertical
from pnlpipe_cli.readparams import read_combos, read_grouped_combos, params_file, make_pipeline, OBSID_KEY, get_software
import importlib
import logging
import pnlpipe_software


def _concat(l):
    return l if l == [] else [item for sublist in l for item in sublist]


class Setup(cli.Application):
    """Builds necessary pnlpipe_software for the pipeline. """

    fullPaths = cli.Flag(
        ['-p'],
        help="Use full path filenames (containing escaped characters) in the shell environment files instead of shortened symlinks")

    def main(self):
        logging.info("Build prerequisite pnlpipe_software")
        combos = read_combos(self.parent.pipeline_name)
        software = set(_concat([get_software(combo).items() for combo in combos]))
        for name, version in software:
                module = pnlpipe_software.import_module(name)
                logging.info("Make {}".format(module.get_path(version)))
                module.make(version)

        # logging.info("Make shell environment files")
        # make_env_files(self.parent.pipeline_name, self.fullPaths)


def escape_path(filepath):
    return filepath.__str__().replace('(', '\(').replace(')', '\)')


def make_env_files(pipeline_name, use_full_paths=False):
    # first delete existing files in case they are stale
    outdir = local.path(params_file(pipeline_name)).dirname
    for f in  outdir // ('_' + pipeline_name + '*.sh'):
        f.delete()

    for paramid, combo, caseids in read_grouped_combos(pipeline_name):
        pipeline = make_pipeline(pipeline_name, combo, caseids[0])

        envfile = outdir / ('{}_env{}.sh'.format(pipeline_name, paramid))

        logging.info("Make '{}'".format(envfile))

        with open(envfile, 'w') as f:
            f.write('# Parameter combination {}\n'.format(paramid))
            printVertical(combo, prepend='#  ', fd=f)
            f.write('\n')

            # Generated output paths
            for tag, node in pipeline.items():
                # if self.use_full_paths:
                nodepath = escape_path(node.output())
                # else:
                #     from pnlpipe_cli.pipecmd.symlink import toSymlink
                #     path = toSymlink(caseid, pipeline_name, tag,
                                     # node.output(), paramid)
                f.write('export {}={}\n\n'.format(tag, nodepath))

            f.write('export {}={}\n\n'.format(OBSID_KEY, caseids[0]))

            # Software environment
            env_dicts = []
            for softname, version in software_params(combo).items():
                software_module = pnlpipe_software.import_module(softname)
                if hasattr(software_module, 'env_dict'):
                    env_dicts.append(software_module.env_dict(version))
            softVars = pnlpipe_software.composeEnvDicts(env_dicts)
            for var, val in softVars.items():
                f.write('export {}={}\n\n'.format(var, val))

            # TODO remove ad hoc addition of pnlscripts?
            f.write("export PATH={}:$PATH\n".format(
                local.path('pnlscripts')))
