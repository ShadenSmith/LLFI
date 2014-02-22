#!/usr/bin/env python2
'''
llfi-stats is a set of analysis tools <TODO>
'''

import os
import re
import argparse
from collections import defaultdict

##############################################################################
def help():
  parser = initParser()
  parser.print_help()
##############################################################################

##############################################################################
def run(args):
  parser = initParser()
  options = parser.parse_args(args)
  nruns = getRunSizes(options.DIR)

  # First generate return code summary
  codes = genCodeSummary(options.DIR, nruns)

  printCodeSummary(codes, nruns)

##############################################################################

def initParser():
  parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    prog='llfi stats',
    epilog=__doc__,
  )
  parser.add_argument('DIR', default='llfi',
                      help='directory containing LLFI output')
  #parser.add_argument('--summary', action='store_true', dest='SUMMARY',
                      #help='generate a summary of injection output')

  return parser

def genCodeSummary(directory, nruns):
  # A list of default dicts, one for each group of runs
  codes = []
  # Initialize all groups to 0 (EXIT_SUCCESS), then decrement when errors
  # are found
  for group, runs in enumerate(nruns):
    codes.append(defaultdict(int))
    codes[group]['0'] = runs

  error_dir = os.path.join(directory, "error_output")
  files = [os.path.join(error_dir, f) for f in os.listdir(error_dir)]

  run_re = re.compile('.*errorfile-run-(\d+)-(\d+)')
  code_re = re.compile('.*return code (-?\d+)')
  for curr_file in files:
    m = run_re.match(curr_file)
    if m:
      group = int(m.group(1))
      run = int(m.group(2))

      code = '-1'
      with open(curr_file) as f:
        dat = f.read()
        m = code_re.match(dat)
        if m:
          code = m.group(1)
        else:
          code = 'TO'

      codes[group][code] += 1
      codes[group]['0'] -= 1

  return codes

def getRunSizes(directory):
  '''
    Return a list of run sizes for each group of runs
  '''
  run_dict = defaultdict(int)
  stat_dir = os.path.join(directory, 'llfi_stat_output');
  files = os.listdir(stat_dir)

  run_re = re.compile('llfi.stat.fi.injectedfaults.(\d+)-(\d+).txt')
  for f in files:
    m = run_re.match(f)
    if m:
      group = int(m.group(1))
      run = int(m.group(2)) + 1 # adjust for zero-indexing
      run_dict[group] = max(run_dict[group], run)

  # Convert dict to list
  runs = [0] * len(run_dict)
  for k,v in run_dict.items():
    runs[k] = v

  return runs

def printCodeSummary(codes, nruns):
  print("Return codes:")
  for g,c in enumerate(codes):
    print("Group: {} [{} runs]".format(g, nruns[int(g)]))
    for k in sorted(c.keys()):
      print("   {:>3s}: {:>5,}".format(k, c[k]))
    print("")

