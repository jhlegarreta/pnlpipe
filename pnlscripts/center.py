#!/usr/bin/env python

from __future__ import print_function
from util import ExistingNrrd
from plumbum import local, cli, FG
import nrrd
from numpy import array


def dot_product(v1, v2):
    return [a*b for (a,b) in zip(v1, v2)]


def get_attr(filename):
    img= nrrd.read(filename)

    mri= img[0]
    hdr= img[1]

    return (mri, hdr)


def centered_origin(hdr):

    spc_dirs= hdr['space directions']

    sizes= hdr['sizes']

    origin= hdr['space origin']

    print("space directions: " + str(spc_dirs))
    print("sizes: " + str(sizes))
    print("origin: " + str(origin))

    new_origin = []
    for dir in spc_dirs:
        sizes2 = [(x-1)/2  for x in sizes]
        tuple(sizes2)
        dp = dot_product(sizes2, dir)
        dp_abs = [abs(x) for x in dp]
        maxmin_elem = dp_abs.index(max(dp_abs))
        new_origin.append(-dp[maxmin_elem])

    print("new origin: " + str(new_origin[:3]))

    return new_origin[:3]

    
class App(cli.Application):
    """Centers an nrrd."""

    image_in = cli.SwitchAttr(['-i', '--infile'], ExistingNrrd, help='a 3d or 4d nrrd image', mandatory=True)
    outfile = cli.SwitchAttr(['-o', '--outfile'], help='a 3d or 4d nrrd image', mandatory=True)

    def main(self):

        mri, hdr= get_attr(self.image_in._path)
        hdr_out= hdr.copy()

        new_origin = centered_origin(hdr)

        hdr_out['space origin'] = array(new_origin)

        if 'data file' in hdr_out.keys():
            del hdr_out['data file']
        elif 'datafile' in hdr_out.keys():
            del hdr_out['datafile']

        if 'content' in hdr_out.keys():
            del hdr_out['content']

        nrrd.write(self.outfile, mri, header=hdr_out, compression_level=1)

if __name__ == '__main__':
    App.run()
