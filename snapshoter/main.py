#!/usr/bin/env python3

# Copyright (c) Huan He (hehuan2112@gmail.com)
# All rights reserved.
#
# This source code is licensed under the Apache 2.0 license found in the
# LICENSE file in the root directory of this source tree.
#
import sys
sys.path.append('..')

import os
import json
import pathlib
import shutil
import argparse
import datetime

from scene import p_IO_default as snpt4IOdefault
from scene import general_project as snpt4general


def make_archive(source, destination):
    '''
    Make a zip file to backup source folder
    '''
    base_name = '.'.join(destination.split('.')[:-1])
    format = destination.split('.')[-1]
    root_dir = os.path.dirname(source)
    base_dir = os.path.basename(source.strip(os.sep))
    shutil.make_archive(base_name, format, root_dir, base_dir)
    shutil.move('%s.%s'%(base_name, format), destination)


def kacha(keystr, cq_abbr, output_path, prefix=''):
    '''
    Take a snapshot

    This function will create a sub folder in the output_path.
    '''
    # first of all, remove the old kacha?
    prj_path = os.path.join(
        output_path, keystr, cq_abbr
    )

    if os.path.exists(prj_path):
        print('* found existing output path: %s' % prj_path)

        # move to other place
        src_path = prj_path
        dst_path = '/data/lnma/pub_backups/' + datetime.datetime.now().strftime('%Y-%m-%d')
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        dst_file = os.path.join(
            dst_path,
            '%s.%s.%s.zip' % (keystr, cq_abbr, datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S'))
        )
        # shutil.move(src_path, dst_path)
        make_archive(src_path, dst_file)
        print('* backuped the %s %s pub site to %s' % (
            keystr, cq_abbr, dst_file
        ))

        # remove
        shutil.rmtree(prj_path)
        print('* removed existed %s %s pub site data' % (
            keystr, cq_abbr
        ))
    
    if keystr == 'IO' and cq_abbr == 'default':
        # a special rule for IO default
        snpt4IOdefault.kacha(
            output_path, 
            prefix
        )
    
    else:
        snpt4general.kacha(
            keystr,
            cq_abbr,
            output_path,
            prefix
        )
        
    return 1



if __name__ == "__main__":
    parser = argparse.ArgumentParser('LNMA Snapshoter')
    parser.add_argument("--keystr", type=str,
        help="The keystr for the project. Use `all` for all projects"
    )
    parser.add_argument("--cq", type=str, default="default",
        help="The cq abbr. default is default"
    )
    parser.add_argument("--prefix", type=str, default="",
        help="The prefix for generated static site, default is empty. Then the static website will be served as root folder."
    )
    parser.add_argument("--output", type=str,
        help="The output path for the static website"
    )

    args = parser.parse_args()

    if args.keystr == 'all':
        pass

    else:
        kacha(args.keystr, args.cq, args.output, args.prefix)

    print('* done snapshot!')