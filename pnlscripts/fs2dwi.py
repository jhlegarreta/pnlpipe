#!/usr/bin/env python

from __future__ import print_function
from util import logfmt, TemporaryDirectory, join, dirname
from plumbum import local, cli, FG
from plumbum.cmd import ConvertBetweenFileFormats
import sys, os, psutil, warnings
from util.antspath import ResampleImageBySpacing, antsApplyTransforms, ImageMath
from util.scripts import bse_py, antsRegistrationSyNMI_sh
from subprocess import check_call
SCRIPTDIR= os.path.dirname(os.path.abspath(__file__))
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=FutureWarning)
    import nibabel as nib

import logging
logger = logging.getLogger()
logging.basicConfig(level=logging.DEBUG, format=logfmt(__file__))

N_CPU= '4' # str(psutil.cpu_count())


def rigid_registration(dim, moving, fixed, outPrefix):

    antsRegistrationSyNMI_sh['-d', str(dim), '-t', 'r', '-m', moving, '-f', fixed, '-o', outPrefix,
                    '-n', N_CPU] & FG


def registerFs2Dwi(tmpdir, namePrefix, b0masked, brain, wmparc, wmparc_out):

    logging.info('Registering wmparc to B0')
    pre = tmpdir / namePrefix
    affine = pre + '0GenericAffine.mat'
    warp = pre + '1Warp.nii.gz'

    logging.info('Computing warp from brain.nii.gz to (resampled) baseline')
    antsRegistrationSyNMI_sh['-m', brain, '-f', b0masked, '-o', pre,
                           '-n', N_CPU] & FG

    logging.info('Applying warp to wmparc.nii.gz to create (resampled) wmparcindwi.nii.gz')
    antsApplyTransforms('-d', '3', '-i', wmparc, '-t', warp, affine,
                        '-r', b0masked, '-o', wmparc_out,
                        '--interpolation', 'NearestNeighbor')

    logging.info('Made ' + wmparc_out)


# The functions registerFs2Dwi and registerFs2Dwi_T2 differ by the use of t2masked, T2toBrainAffine, and a print statement


def registerFs2Dwi_T2(tmpdir, namePrefix, b0masked, t2masked, T2toBrainAffine, wmparc, wmparc_out):

    logging.info('Registering wmparc to B0')
    pre = tmpdir / namePrefix
    affine = pre + '0GenericAffine.mat'
    warp = pre + '1Warp.nii.gz'

    logging.info('Computing warp from t2 to (resampled) baseline')
    antsRegistrationSyNMI_sh['-d', '3', '-m', t2masked, '-f', b0masked, '-o', pre,
                           '-n', N_CPU] & FG

    logging.info('Applying warp to wmparc.nii.gz to create (resampled) wmparcindwi.nii.gz')
    antsApplyTransforms('-d', '3', '-i', wmparc, '-t', warp, affine, T2toBrainAffine,
                        '-r', b0masked, '-o', wmparc_out,
                        '--interpolation', 'NearestNeighbor')

    logging.info('Made ' + wmparc_out)




class FsToDwi(cli.Application):
    """Registers Freesurfer labelmap to DWI space."""

    fsdir = cli.SwitchAttr(
        ['-f', '--freesurfer'],
        cli.ExistingDirectory,
        help='freesurfer subject directory',
        mandatory=True)

    dwi = cli.SwitchAttr(
        ['-t', '--target'],
        cli.ExistingFile,
        help='target DWI',
        mandatory=True)

    dwimask = cli.SwitchAttr(
        ['-m', '--mask'],
        cli.ExistingFile,
        help='DWI mask',
        mandatory=True)

    out = cli.SwitchAttr(
        ['-o', '--out'],
        help='output directory',
        mandatory=True)

    force= cli.Flag(
        ['--force'],
        help='turn on this flag to overwrite existing output',
        default= False,
        mandatory= False)

    debug = cli.Flag(
        ['-d','--debug'],
        help='Debug mode, saves intermediate transforms to out/fs2dwi-debug-<pid>',
        default= False)


    def main(self):

        if not self.nested_command:
            logging.info("No command given")
            sys.exit(1)

        self.fshome = local.path(os.getenv('FREESURFER_HOME'))

        if not self.fshome:
            logging.info('Set FREESURFER_HOME first.')
            sys.exit(1)

        logging.info('Making output directory')
        self.out= local.path(self.out)
        if self.out.exists() and self.force:
            logging.info('Deleting existing directory')
            self.out.delete()
        self.out.mkdir()


@FsToDwi.subcommand("direct")
class Direct(cli.Application):
    """Direct registration from Freesurfer to B0."""

    def main(self):

        with TemporaryDirectory() as tmpdir:

            tmpdir = local.path(tmpdir)

            b0masked = tmpdir / "b0masked.nii.gz" # Sylvain wants both
            b0maskedbrain = tmpdir / "b0maskedbrain.nii.gz"

            brain = tmpdir / "brain.nii.gz"
            wmparc = tmpdir / "wmparc.nii.gz"

            brainmgz = self.parent.fsdir / 'mri/brain.mgz'
            wmparcmgz = self.parent.fsdir / 'mri/wmparc.mgz'

            wmparcindwi = tmpdir / 'wmparcInDwi.nii.gz' # Sylvain wants both
            wmparcinbrain = tmpdir / 'wmparcInBrain.nii.gz'

            logging.info("Making brain.nii.gz and wmparc.nii.gz from their mgz versions")

            vol2vol = local[self.parent.fshome / 'bin/mri_vol2vol']
            label2vol = local[self.parent.fshome / 'bin/mri_label2vol']

            with local.env(SUBJECTS_DIR=''):
                vol2vol('--mov', brainmgz, '--targ', brainmgz, '--regheader',
                        '--o', brain)
                label2vol('--seg', wmparcmgz, '--temp', brainmgz,
                          '--regheader', wmparcmgz, '--o', wmparc)

            logging.info('Extracting B0 from DWI and masking it')
            bse_py['-i', self.parent.dwi, '-m', self.parent.dwimask, '-o', tmpdir / 'b0mask.nrrd'] & FG
            ConvertBetweenFileFormats(tmpdir / 'b0mask.nrrd', b0masked)
            logging.info('Made masked B0')


            dwi_res= nib.load(str(b0masked)).header['pixdim'][1:4].round()
            brain_res= nib.load(str(brain)).header['pixdim'][1:4].round()
            logging.info(f'DWI resolution: {dwi_res}')
            logging.info(f'FreeSurfer brain resolution: {brain_res}')

            if dwi_res.ptp() or brain_res.ptp():
                logging.info('Resolution is not uniform among all the axes')


            logging.info('Registering wmparc to B0')
            registerFs2Dwi(tmpdir, 'fsbrainToB0', b0masked, brain, wmparc, wmparcindwi)

            if (dwi_res!=brain_res).any():
                logging.info('DWI resolution is different from FreeSurfer brain resolution')
                logging.info('wmparc wil be registered to both DWI and brain resolution')
                logging.info('Check output files wmparcInDwi.nii.gz and wmparcInBrain.nii.gz')

                logging.info('Resampling B0 to brain resolution')

                ResampleImageBySpacing('3', b0masked, b0maskedbrain, brain_res.tolist())

                logging.info('Registering wmparc to resampled B0')
                registerFs2Dwi(tmpdir, 'fsbrainToResampledB0', b0maskedbrain, brain, wmparc, wmparcinbrain)


            # copying images to outDir
            b0masked.copy(self.parent.out)
            wmparcindwi.copy(self.parent.out)

            if b0maskedbrain.exists():
                b0maskedbrain.copy(self.parent.out)
                wmparcinbrain.copy(self.parent.out)


            if self.parent.debug:
                tmpdir.copy(self.parent.out, 'fs2dwi-debug-' + str(os.getpid()))

        logging.info('See output files in '+ self.parent.out._path)


@FsToDwi.subcommand("witht2")
class WithT2(cli.Application):
    """Registration from Freesurfer to T2 to B0."""

    t2 = cli.SwitchAttr(
        ['--t2'],
        cli.ExistingFile,
        help='T2 image',
        mandatory=True)

    t2mask = cli.SwitchAttr(
        ['--t2mask'],
        cli.ExistingFile,
        help='T2 mask',
        mandatory=True)



    def main(self):

        with TemporaryDirectory() as tmpdir:

            tmpdir = local.path(tmpdir)

            b0masked = tmpdir / "b0masked.nii.gz" # Sylvain wants both
            b0maskedbrain = tmpdir / "b0maskedbrain.nii.gz"

            t2masked= tmpdir / 't2masked.nii.gz'
            logging.info('Masking the T2')
            ImageMath(3, t2masked, 'm', self.t2, self.t2mask)

            brain = tmpdir / "brain.nii.gz"
            wmparc = tmpdir / "wmparc.nii.gz"

            brainmgz = self.parent.fsdir / 'mri/brain.mgz'
            wmparcmgz = self.parent.fsdir / 'mri/wmparc.mgz'

            wmparcindwi = tmpdir / 'wmparcInDwi.nii.gz' # Sylvain wants both
            wmparcinbrain = tmpdir / 'wmparcInBrain.nii.gz'

            logging.info("Making brain.nii.gz and wmparc.nii.gz from their mgz versions")

            vol2vol = local[self.parent.fshome / 'bin/mri_vol2vol']
            label2vol = local[self.parent.fshome / 'bin/mri_label2vol']

            with local.env(SUBJECTS_DIR=''):
                vol2vol('--mov', brainmgz, '--targ', brainmgz, '--regheader',
                        '--o', brain)
                label2vol('--seg', wmparcmgz, '--temp', brainmgz,
                          '--regheader', wmparcmgz, '--o', wmparc)

            logging.info('Extracting B0 from DWI and masking it')
            bse_py['-i', self.parent.dwi, '-m', self.parent.dwimask, '-o', tmpdir / 'b0mask.nrrd'] & FG
            ConvertBetweenFileFormats(tmpdir / 'b0mask.nrrd', b0masked)
            logging.info('Made masked B0')


            # rigid registration from t2 to brain.nii.gz
            pre = tmpdir / 'BrainToT2'
            BrainToT2Affine = pre + '0GenericAffine.mat'

            logging.info('Computing rigid registration from brain.nii.gz to t2')
            # antsRegistrationSyNMI_sh['-d', '3', '-t', 'r', '-m', brain, '-f', t2masked, '-o', pre,
            #                 '-n', N_CPU] & FG
            rigid_registration(3, brain, t2masked, pre)
            # generates three files for rigid registration:
            # pre0GenericAffine.mat  preInverseWarped.nii.gz  preWarped.nii.gz

            # generates five files for default(rigid+affine+deformable syn) registration:
            # pre0GenericAffine.mat  pre1Warp.nii.gz  preWarped.nii.gz   pre1InverseWarp.nii.gz  preInverseWarped.nii.gz


            dwi_res= nib.load(str(b0masked)).header['pixdim'][1:4].round()
            brain_res= nib.load(str(brain)).header['pixdim'][1:4].round()
            logging.info(f'DWI resolution: {dwi_res}')
            logging.info(f'FreeSurfer brain resolution: {brain_res}')

            if dwi_res.ptp() or brain_res.ptp():
                logging.info('Resolution is not uniform among all the axes')


            logging.info('Registering wmparc to B0 through T2')
            registerFs2Dwi_T2(tmpdir, 'fsbrainToT2ToB0', b0masked, t2masked,
                              BrainToT2Affine, wmparc, wmparcindwi)

            if (dwi_res!=brain_res).any():
                logging.info('DWI resolution is different from FreeSurfer brain resolution')
                logging.info('wmparc wil be registered to both DWI and brain resolution')
                logging.info('Check output files wmparcInDwi.nii.gz and wmparcInBrain.nii.gz')

                logging.info('Resampling B0 to brain resolution')

                ResampleImageBySpacing('3', b0masked, b0maskedbrain, brain_res.tolist())

                logging.info('Registering wmparc to resampled B0')
                registerFs2Dwi_T2(tmpdir, 'fsbrainToT2ToResampledB0', b0maskedbrain, t2masked,
                                  BrainToT2Affine, wmparc, wmparcinbrain)

            # copying images to outDir
            b0masked.copy(self.parent.out)
            wmparcindwi.copy(self.parent.out)

            if b0maskedbrain.exists():
                b0maskedbrain.copy(self.parent.out)
                wmparcinbrain.copy(self.parent.out)


            if self.parent.debug:
                tmpdir.copy(self.parent.out, 'fs2dwi-debug-' + str(os.getpid()))


        logging.info('See output files in '+ self.parent.out._path)

if __name__ == '__main__':
    FsToDwi.run()

