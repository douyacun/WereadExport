'''
os_util.py
Copyright 2020 by Algebra-FUN
ALL RIGHTS RESERVED.
'''

import os
import shutil
import re
import subprocess
import sys


def dir_check(dir):
    try:
        os.makedirs(f'{os.getcwd()}/{dir}')
    except FileExistsError:
        pass

def os_start_file(file_name):
    if sys.platform == 'win32':
        os.startfile(file_name)
    else:
        subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', file_name], check=True)

def clear_temp(file_name):
    if os.path.exists(file_name):
        shutil.rmtree(file_name)

def escape(file_name):
    return re.sub(r"[\/\\\:\*\?\"\<\>\|]",'_',file_name)
