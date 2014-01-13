#!/usr/bin/env python2

import os
import sys
import errno
import re
import argparse

# Commonly used parameters - see processArgs()
params = {}

def processArgs():
  parser = argparse.ArgumentParser()
  parser.add_argument('DIR', help='base LLFI output directory')
  parser.add_argument('-n' , '--nconfigs', help='number of configs to print',
                      default=1)
  parser.add_argument('-c' , '--code', help='return code to filter by',
                      default=-11)
  parser.add_argument('-g' , '--group', help='run group ID to scan',
                      default=0)
  parser.add_argument('-v' , '--verbose', default=False)
  args = parser.parse_args()

  for param in args.__dict__:
    params[param] = args.__dict__[param]

def getBasePath():
  """
    Returns path to the base LLFI output directory by parsing ARGV.
  """
  if len(sys.argv) < 2:
    print "usage: {} <directory>".format(sys.argv[0])
    sys.exit(errno.EINVAL)

  pwd = os.getcwd()
  return os.path.join(pwd, sys.argv[1])

def getErrorFiles(group=0):
  """
    Returns a list of files in error_output directory that come from
    a given group of runs.
  """
  regex = re.compile(".*run-{}-(\d+)$".format(group))
  path = os.path.join(params["DIR"], "error_output")
  files = os.listdir(path)
  files = [os.path.join(path, f) for f in files if regex.match(f)]
  return files

def getErrorRunIDs(group=0, code=-11):
  """
    Returns a sorted list of all runs within run group that exited with given
    error code.
  """
  # Compile regex to match files and return code strings
  fname_regex = re.compile(".*run-{}-(\d+)$".format(group))
  code_regex = re.compile(".*return code {}$".format(code))

  # Grab files from error_output directory and filter by run group
  errfiles = getErrorFiles(group)

  # Scan files and filter by those with the requested exit code
  ids = []
  for efile in errfiles:
    with open(efile, "r") as f:
      if code_regex.match(f.read()):
        # extract run ID
        ids.append(fname_regex.match(efile).group(1))

  return sorted(ids)

def getConfig(group=0, runID=0):
  """
    Returns a dict of config information for a given run.
  """
  conf = {}

  keyval = re.compile("^(\w+)=(\w+),?$")

  path = os.path.join(params["DIR"], "llfi_stat_output")
  name = "llfi.stat.fi.injectedfaults.{}-{}.txt".format(group,runID)
  fname = os.path.join(path, name)
  with open(fname) as f:
    # Extract all key=val pairs
    dat = f.read()
    tokens = dat.strip().split(" ")
    # foreach token, add it to pairs if it is matched by keyval
    pairs = [m for tok in tokens for m in [keyval.match(tok)] if m]

    # Now fill in conf
    for p in pairs:
      conf[p.group(1)] = p.group(2)

  return conf

def printConfigs(configs):
  """
    Pretty prints a list of configs to be used for future use by LLFI.
  """
  i = 0
  for conf in configs:
    if i == params["nconfigs"]:
      break
    for (key,val) in conf.items():
      print "{}={}".format(key,val)
    print ""
    i += 1

if __name__ == '__main__':
  processArgs()

  # TODO: Get input from ARGV
  if(params["verbose"]):
    print "Processing runs with return code: {}".format(params["code"])

  err_runs = getErrorRunIDs(group=params["group"], code=params["code"])
  if(params["verbose"]):
    print "Run IDs: {}".format(" ".join(err_runs))

  configs = [getConfig(runID=r) for r in err_runs]
  printConfigs(configs)

