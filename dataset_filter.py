from __future__ import division
import math
import pprint
import scipy.misc
import numpy as np
import copy
import os
try:
    _imread = scipy.misc.imread
except AttributeError:
    from imageio import imread as _imread
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--data_path', type=lambda x: x.lower() in ('true', '1'), dest='training', default=True)
contirb, unparsed = parser.parse_known_args() 


def file_list(path, extensions, sort=True, path_label = False):
    if path_label == True:
        result = [(os.path.join(dp, f) + ' ' + os.path.join(dp, f).split('/')[-2])
        for dp, dn, filenames in os.walk(path) 
        for f in filenames if os.path.splitext(f)[1] in extensions]
    else:
        result = [os.path.join(dp, f) for dp, dn, filenames in os.walk(path) 
        for f in filenames if os.path.splitext(f)[1] in extensions]
    if sort:
        result.sort()

    return result

def imread_cycleGAN(path, is_grayscale = False):
    if (is_grayscale):
        return _imread(path, flatten=True).astype(np.float)
    else:
        return _imread(path, mode='RGB').astype(np.float)


def file_filter(path, extensions):
	file_lst = file_list(path, extensions)


	for file_name in file_lst:
		try:
			imread_cycleGAN(file_name)
		else OSError:
			os.remove(file_name)


file_filter(contrib.data_path, ('.jpg', '.png'))