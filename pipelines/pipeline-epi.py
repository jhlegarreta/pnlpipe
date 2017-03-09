from pipelines.pnlnodes import StrctXc, DwiXc, FsInDwiDirect, FreeSurferUsingMask, T1wMaskMabs, DwiMaskHcpBet, DwiEd, UkfDefault, Wmql, TractMeasures, T2wMaskRigid, DwiEpi, DoesNotExistException, assertInputKeys
from pipelib import Src
import pipelib

def makePipeline(caseid,
                 BRAINSTools,
                 tract_querier,
                 UKFTractography,
                 trainingDataT1AHCC,
                 dwiKey,
                 t1Key,
                 t2Key,
                 dwimaskKey):
    """Makes the PNL's standard pipeline with EPI distortion correction. """

    pipeline = { 'name' :  "EPI correction pipeline" }
    assertInputKeys(pipeline['name'], [dwiKey, t1Key, t2Key])

    pipeline['t1'] = Src(caseid, t1Key)
    pipeline['dwi'] = Src(caseid, dwiKey)
    pipeline['t2'] = Src(caseid, 't2')

    pipeline['t1xc'] = StrctXc(caseid, pipeline['t1'], BRAINSTools)
    pipeline['t2xc'] = StrctXc(caseid, pipeline['t2'], BRAINSTools)
    # run DwiXc first as it's able to convert a DWI nifti to nrrd
    pipeline['dwixc'] = DwiXc(caseid, pipeline['dwi'], BRAINSTools)
    pipeline['dwied'] = DwiEd(caseid, pipeline['dwixc'], BRAINSTools)

    pipeline['dwimask'] = Src(
        caseid, dwimaskKey) if pipelib.INPUT_PATHS.get(
            dwimaskKey) else DwiMaskHcpBet(caseid, pipeline['dwied'], BRAINSTools)

    pipeline['t1mask'] = Src(
        caseid,
        't1mask') if pipelib.INPUT_PATHS.get('t1mask') else T1wMaskMabs(
            caseid, pipeline['t1xc'], trainingDataT1AHCC, BRAINSTools)

    pipeline['t2mask'] = Src(
        caseid,
        't2mask') if pipelib.INPUT_PATHS.get('t2mask') else T2wMaskRigid(
            caseid, pipeline['t2xc'], pipeline['t1xc'], pipeline['t1mask'],BRAINSTools)

    pipeline['dwiepi'] = DwiEpi(caseid, pipeline['dwied'], pipeline['dwimask'],
                                pipeline['t2xc'], pipeline['t2mask'],BRAINSTools)

    pipeline['fs'] = FreeSurferUsingMask(caseid, pipeline['t1xc'],
                                         pipeline['t1mask'])
    pipeline['fsindwi'] = FsInDwiDirect(caseid, pipeline['fs'],
                                        pipeline['dwiepi'], pipeline['dwimask'], BRAINSTools)

    pipeline['ukf'] = UkfDefault(caseid, pipeline['dwiepi'],
                                 pipeline['dwimask'], UKFTractography, BRAINSTools)

    pipeline['wmql'] = Wmql(caseid, pipeline['fsindwi'], pipeline['ukf'],
                            tract_querier)
    pipeline['tractmeasures'] = TractMeasures(caseid, pipeline['wmql'])

    pipeline['all'] = pipeline['tractmeasures']  # default target to build

    return pipeline
