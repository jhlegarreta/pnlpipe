from plumbum import local, cli
import yaml
import inspect
from collections import OrderedDict
from ..readparams import params_file
try:
    # Python 3
    from itertools import zip_longest
except ImportError:
    # Python 2
    from itertools import izip_longest as zip_longest


PARAMS_HELP = \
"""# Use one of the following formats for 'caseid'
#    caseid: ['001', '002', '003']
#    caseid:
#       - '001'
#       - '002'
#       - '003'
#    caseid: [./caselist.txt]  # The '/' tells pnlpipe that this is a file
#
# Note that you need to wrap your caseid in quotes if it is an integer like
# above, otherwise the yaml reader will read them as 1, 2, 3, etc. instead of
# '001', '002', '003'.
#
# The values for keys like inputDwiKey come from the names in INPUT_KEYS in
# pnlpipe_config.py. For # example,
#
#    inputDwiKey: ['dwiharmonized', 'dwi']
#
# means that the pipeline will be run for the filepaths of 'dwiharmonized' and
# 'dwi' in pnlpipe.config.INPUT_KEYS. (caseid will automatically be substituted).

"""

class Init(cli.Application):
    """Makes parameter file that is used as input for this pipeline."""

    force = cli.Flag(
        ['--force'], help='Force overwrite existing parameter file.')

    def main(self):
        pipelineName = self.parent.__class__.__name__
        paramsFile = params_file(self.parent.pipeline_name)
        if paramsFile.exists() and not self.force:
            print(
                "'{}' already exists, won't overwrite (use '--force' to overwrite it).".format(
                    paramsFile))
            return
        paramsFile.delete()
        paramsFile.dirname.mkdir()
        args, _, _, defaults = inspect.getargspec(
            self.parent.make_pipeline_orig)
        if defaults:
            x = zip_longest(
                reversed(args), reversed(defaults), fillvalue='*mandatory*')
        else:
            x = zip_longest(reversed(args), [], fillvalue='*mandatory*')
        paramDict = OrderedDict(reversed(list(map(lambda y: (y[0], [y[1]]), x))))
        paramDict['caseid'] = ['./caselist.txt']
        represent_dict_order = lambda self, data: self.represent_mapping('tag:yaml.org,2002:map', data.items())
        yaml.add_representer(OrderedDict, represent_dict_order)
        with open(paramsFile, 'w') as f:
            f.write(PARAMS_HELP)
            yaml.dump(paramDict, f, default_flow_style=None)
        print("Made '{}'".format(paramsFile))
        print("Before running the pipeline, replace the '*mandatory*' fields:")
        print("# Edit {}, add your parameters".format(paramsFile))
        print("./pnlpipe {} setup".format(pipelineName))
        print("./pnlpipe {} run".format(pipelineName))
