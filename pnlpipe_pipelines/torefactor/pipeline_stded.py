import sys
from pnlpipe_pipelines.pnlnodes import StrctXc, DwiXc, FsInDwiDirect, FreeSurferUsingMask, T1wMaskMabs, DwiMaskBet, DwiEd, UkfDefault, Wmql, TractMeasures, MaskRigid, DwiEpi, DoesNotExistException
from pnlpipe_lib import InputKey

DEFAULT_TARGET = 'tractmeasures'


def make_pipeline(caseid,
                 t1PathKey,
                 dwiPathKey,
                 dwimaskPathKey='',
                 version_FreeSurfer='5.3.0',
                 hash_UKFTractography='421a7ad',
                 hash_tract_querier='e045eab',
                 hash_BRAINSTools='41353e8',
                 hash_trainingDataT1AHCC='d6e5990'):
    """Makes the PNL's standard pipeline, given an eddy corrected DWI
    (For example, a DRBUDDI processed DWI.). Same as 'std' except eddy
    current correction is not performed."""

    pipeline = {'_name': "standard PNL pipeline with no eddy correction"}

    pipeline['t1'] = InputKey(caseid, t1PathKey)
    pipeline['dwi'] = InputKey(caseid, dwiPathKey)
    pipeline['t1xc'] = StrctXc(caseid, pipeline['t1'], hash_BRAINSTools)
    pipeline['dwimask'] = InputKey(
        caseid, dwimaskPathKey) if dwimaskPathKey else DwiMaskBet(
            caseid, pipeline['dwi'], 0.1, hash_BRAINSTools)
    pipeline['t1mask'] = T1wMaskMabs(caseid, pipeline['t1xc'],
                                     hash_trainingDataT1AHCC, hash_BRAINSTools)
    pipeline['fs'] = FreeSurferUsingMask(
        caseid, pipeline['t1xc'], pipeline['t1mask'], version_FreeSurfer)
    pipeline['fsindwi'] = FsInDwiDirect(caseid, pipeline['fs'],
                                        pipeline['dwi'], pipeline['dwimask'],
                                        hash_BRAINSTools)
    pipeline['ukf'] = UkfDefault(caseid, pipeline['dwi'], pipeline['dwimask'],
                                 hash_UKFTractography, hash_BRAINSTools)
    pipeline['wmql'] = Wmql(caseid, pipeline['fsindwi'], pipeline['ukf'],
                            hash_tract_querier)
    pipeline['tractmeasures'] = TractMeasures(caseid, pipeline['wmql'])
    return pipeline


def status(combos, extraFlags=[]):
    import pnlpipe_pipelines.pnlnodes
    pnlpipe_pipelines.pnlnodes.tractMeasureStatus(combos, extraFlags)
