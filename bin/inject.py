#! /usr/bin/env python3

"""
llfi-inject takes a fault injection executable and executes it

Prerequisites:
  1. 'input.yaml' contains appropriate options for LLFI and must be in the
     current working directory.
  2. You need to be at the parent directory of the FI_EXE to invoke llfi-inject.
     This is to make it easier for LLFI to track the outputs generated by
     FI_EXE.
  3. llfi-inject only checks recursively at the current directory for possible
     outputs, if your output is not under current directory, you need to store
     that output by yourself.
  4. You need to put input files (if any) in the current working directory.
"""

# This script injects faults the program and produces output
# This script should be run after the profiling step

import sys, os, subprocess
import yaml
import time
import random
import shutil
import argparse
import resource
import glob
from collections import defaultdict

runOverride = False
timeout = 500

basedir = os.getcwd()
prog = os.path.basename(sys.argv[0])

yaml_options = {
  "verbose": False,
}

def usage(msg = None):
  retval = 0
  if msg is not None:
    retval = 1
    msg = "ERROR: " + msg
    print(msg, file=sys.stderr)
  print(__doc__ % globals(), file=sys.stderr)
  sys.exit(retval)

def help():
  parser = initParser()
  parser.print_help()

def initParser():
  parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    prog='llfi inject',
    epilog=__doc__,
  )
  parser.add_argument('FI_EXE', help='instrumented executable')
  parser.add_argument('EXE_ARGS', nargs='*',
                      help='arguments to FI_EXE used during profiling')
  return parser


def parseArgs(parser, args):
  options = parser.parse_args(args)
  options.FI_EXE = os.path.realpath(options.FI_EXE)
  if os.path.dirname(os.path.dirname(options.FI_EXE)) != basedir:
    usage("You need to invoke llfi-inject at the parent directory of FI_EXE")

  # remove the directory prefix for input files, this is to make it easier for the program
  # to take a snapshot
  for index, opt in enumerate(options.EXE_ARGS):
    if os.path.isfile(opt):
      if os.path.realpath(os.path.dirname(opt)) != basedir:
        usage("File %s passed through option is not under current directory" % opt)
      else:
        options.EXE_ARGS[index] = os.path.basename(opt)

  return options

def checkInputYaml():
  global timeout, doc
  #Check for input.yaml's presence
  try:
    f = open(os.path.join(basedir, 'input.yaml'),'r')
  except:
    usage("No input.yaml file in the parent directory of FI_EXE")
    exit(1)

  #Check for input.yaml's correct formmating
  try:
    doc = yaml.load(f)
    f.close()
    if "kernelOption" in doc:
      for opt in doc["kernelOption"]:
        if opt=="forceRun":
          runOverride = True
          print("Kernel: Forcing run")
    if "timeOut" in doc:
      timeout = int(doc["timeOut"])
      assert timeout > 0, "The timeOut option must be greater than 0"
    else:
      print("Run FI_EXE with default timeout " + str(timeout))
  except:
    usage("input.yaml is not formatted in proper YAML (reminder: use spaces, not tabs)")
    exit(1)


def print_progressbar(idx, nruns):
  pct = (float(idx) / float(nruns))
  WIDTH = 50
  bar = "=" *  int(pct * WIDTH)
  bar += ">"
  bar += "-" * (WIDTH - int(pct * WIDTH))
  print(("\r[%s] %.1f%% (%d / %d)" % (bar, pct * 100, idx, nruns)), end=' ')
  sys.stdout.flush()


################################################################################
def config():
  global inputdir, outputdir, errordir, stddir, llfi_stat_dir, logdir
  # config
  llfi_dir = os.path.dirname(fi_exe)
  inputdir = os.path.join(llfi_dir, "prog_input")
  outputdir = os.path.join(llfi_dir, "prog_output")
  errordir = os.path.join(llfi_dir, "error_output")
  stddir = os.path.join(llfi_dir, "std_output")
  logdir = os.path.join(llfi_dir, "log_output")
  llfi_stat_dir = os.path.join(llfi_dir, "llfi_stat_output")

  if not os.path.isdir(outputdir):
    os.mkdir(outputdir)
  if not os.path.isdir(errordir):
    os.mkdir(errordir)
  if not os.path.isdir(inputdir):
    os.mkdir(inputdir)
  if not os.path.isdir(stddir):
    os.mkdir(stddir)
  if not os.path.isdir(logdir):
    os.mkdir(logdir)
  if not os.path.isdir(llfi_stat_dir):
    os.mkdir(llfi_stat_dir)

################################################################################
def set_timeout():
  resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))

def execute( execlist):
  global outputfile
  global return_codes
  #get state of directory
  dirSnapshot()

  outputFile = open(outputfile, "w")
  # Run process!
  p_time = -time.time()
  p = subprocess.Popen(execlist, stdout = outputFile,
                       preexec_fn = set_timeout)
  p.wait()
  p_time += time.time()

  outputFile.close()
  moveOutput()
  replenishInput() #for cases where program deletes input or alters them each run

  p_retcode = p.returncode

  # return code -9 is from a timeout
  if p_retcode != -9:
    return_codes[p_retcode] += 1
  else:
    p_retcode = 'timed-out'
    return_codes['TO'] += 1

  return (str(p.returncode), p_time)

################################################################################
def storeInputFiles(exe_args):
  global inputList
  inputList=[]
  for opt in exe_args:
    if os.path.isfile(opt):#stores all files in inputList and copy over to inputdir
      shutil.copy2(opt, os.path.join(inputdir, opt))
      inputList.append(opt)

################################################################################
def replenishInput():#TODO make condition to skip this if input is present
  for each in inputList:
    if not os.path.isfile(each):#copy deleted inputfiles back to basedir
      shutil.copy2(os.path.join(inputdir, each), each)

################################################################################
def moveOutput():
  #move all newly created files
  newfiles = [_file for _file in os.listdir(".")]
  for each in newfiles:
    if each not in dirBefore:
      fileSize = os.stat(each).st_size
      if fileSize == 0 and each.startswith("llfi"):
        #empty library output, can delete
        #print each+ " is going to be deleted for having size of " + str(fileSize)
        os.remove(each)
      else:
        flds = each.split(".")
        newName = '.'.join(flds[0:-1])
        newName+='.'+run_id+'.'+flds[-1]
        if newName.startswith("llfi"):
          os.rename(each, os.path.join(llfi_stat_dir, newName))
        else:
          os.rename(each, os.path.join(outputdir, newName))

################################################################################
def dirSnapshot():
  #snapshot of directory before each execute() is performed
  global dirBefore
  dirBefore = [_file for _file in os.listdir(".")]

################################################################################
def readCycles():
  global totalcycles
  profinput= open("llfi.stat.prof.txt","r")
  while 1:
    line = profinput.readline()
    if line.strip():
      if line[0] == 't':
        label, totalcycles = line.split("=")
        break
  profinput.close()

################################################################################
def checkValues(key, val, var1 = None,var2 = None,var3 = None,var4 = None):
  #preliminary input checking for fi options
  #also checks for fi_bit usage by non-kernel users
  #optional var# are used for fi_bit's case only
  if key =='run_number':
    assert isinstance(val, int)==True, key+" must be an integer in input.yaml"
    assert int(val)>0, key+" must be greater than 0 in input.yaml"

  elif key == 'fi_type':
    pass

  elif key == 'fi_cycle':
    assert isinstance(val, int)==True, key+" must be an integer in input.yaml"
    assert int(val) >= 0, key+" must be greater than or equal to 0 in input.yaml"
    assert int(val) <= int(totalcycles), key +" must be less than or equal to "+totalcycles.strip()+" in input.yaml"

  elif key == 'fi_rate':
    assert isinstance(val, int)==True, key+" must be an integer in input.yaml"
    assert int(val) >= 0, key+" must be greater than or equal to 0 in input.yaml"

  elif key == 'fi_index':
    assert isinstance(val, int)==True, key+" must be an integer in input.yaml"
    assert int(val) >= 0, key+" must be greater than or equal to 0 in input.yaml"

  elif key == 'fi_reg_index':
    assert isinstance(val, int)==True, key+" must be an integer in input.yaml"
    assert int(val) >= 0, key+" must be greater than or equal to 0 in input.yaml"

  elif key == 'fi_bit':
    assert isinstance(val, int)==True, key+" must be an integer in input.yaml"
    assert int(val) >= 0, key+" must be greater than or equal to 0 in input.yaml"

    if runOverride:
      pass
    elif var1 > 1 and (var2 or var3) and var4:
      user_input = input("\nWARNING: Injecting into the same cycle(index), bit multiple times "+
                  "is redundant as it would yield the same result."+
                  "\nTo turn off this warning, please see Readme "+
                  "for kernel mode.\nDo you wish to continue anyway? (Y/N)\n ")
      if user_input.upper() =="Y":
        pass
      else:
        exit(1)

################################################################################
def run(args):
  global outputfile, totalcycles,run_id, return_codes

  parseArgs(args)
  # Maintain a dict of all return codes received and print summary at end
  return_codes = defaultdict(int)

  parser = initParser()
  options = parseArgs(parser, args)
  checkInputYaml()
  config(options.FI_EXE)

  # get total num of cycles
  readCycles()
  storeInputFiles(options.EXE_ARGS)

  #Set up each config file and its corresponding run_number
  try:
    rOpt = doc["runOption"]
  except:
    print("ERROR: Please include runOption in input.yaml.")
    exit(1)

  if not os.path.isfile(options.FI_EXE):
    print("ERROR: The executable "+ options.FI_EXE + " does not exist.")
    print("Please build the executables with create-executables.\n")
    exit(1)
  else:
    print("======Fault Injection======")
    for ii, run in enumerate(rOpt):
      # Maintain a dict of all return codes received and print summary at end
      return_codes = defaultdict(int)
      tot_time = 0.0

      # Put an empty line between configs
      if ii > 0:
        print("")
      print("---FI Config #"+str(ii)+"---")

      if "numOfRuns" not in run["run"]:
        print ("ERROR: Must include a run number per fi config in input.yaml.")
        exit(1)

      run_number=run["run"]["numOfRuns"]
      checkValues("run_number", run_number)

      # check for verbosity option, set at the FI run level
      if "verbose" in run["run"]:
        yaml_options["verbose"] = run["run"]["verbose"]

      # reset all configurations
      if 'fi_type' in locals():
        del fi_type
      if 'fi_cycle' in locals():
        del fi_cycle
      if 'fi_rate' in locals():
        del fi_rate
      if 'fi_index' in locals():
        del fi_index
      if 'fi_reg_index' in locals():
        del fi_reg_index
      if 'fi_bit' in locals():
        del fi_bit

      #write new fi config file according to input.yaml
      if "fi_type" in run["run"]:
        fi_type=run["run"]["fi_type"]
        checkValues("fi_type",fi_type)
      if "fi_cycle" in run["run"]:
        fi_cycle=run["run"]["fi_cycle"]
        checkValues("fi_cycle",fi_cycle)
      if "fi_rate" in run["run"]:
        fi_rate=run["run"]["fi_rate"]
        checkValues("fi_rate",fi_rate)
      if "fi_index" in run["run"]:
        fi_index=run["run"]["fi_index"]
        checkValues("fi_index",fi_index)
      if "fi_reg_index" in run["run"]:
        fi_reg_index=run["run"]["fi_reg_index"]
        checkValues("fi_reg_index",fi_reg_index)
      if "fi_bit" in run["run"]:
        fi_bit=run["run"]["fi_bit"]
        checkValues("fi_bit",fi_bit)

      if ('fi_cycle' not in locals()) and 'fi_index' in locals():
        print(("\nINFO: You choose to inject faults based on LLFI index, "
               "this will inject into every runtime instruction whose LLFI "
               "index is %d\n" % fi_index))

      need_to_calc_fi_cycle = True
      if ('fi_cycle' in locals()) or ('fi_index' in locals()) or ('fi_rate' in locals()):
        need_to_calc_fi_cycle = False

      # fault injection
      for index in range(0, run_number):
        run_id = str(ii)+"-"+str(index)
        outputfile = stddir + "/std_outputfile-" + "run-"+run_id
        errorfile = errordir + "/errorfile-" + "run-"+run_id
        execlist = [options.FI_EXE]

        if need_to_calc_fi_cycle:
          fi_cycle = random.randint(0, int(totalcycles) - 1)

        ficonfig_File = open("llfi.config.fi.txt", 'w')
        if 'fi_cycle' in locals():
          ficonfig_File.write("fi_cycle="+str(fi_cycle)+'\n')
        elif 'fi_index' in locals():
          ficonfig_File.write("fi_index="+str(fi_index)+'\n')
        elif 'fi_rate' in locals():
          ficonfig_File.write("fi_rate="+str(fi_rate)+'\n')

        if 'fi_type' in locals():
          ficonfig_File.write("fi_type="+fi_type+'\n')
        if 'fi_reg_index' in locals():
          ficonfig_File.write("fi_reg_index="+str(fi_reg_index)+'\n')
        if 'fi_bit' in locals():
          ficonfig_File.write("fi_bit="+str(fi_bit)+'\n')
        ficonfig_File.close()

        # print run index before executing. Comma removes newline for prettier
        # formatting
        execlist.extend(options.EXE_ARGS)
        ret, curr_time = execute(execlist)
        tot_time += curr_time

        if ret == "timed-out":
          error_File = open(errorfile, 'w')
          error_File.write("Program hang\n")
          error_File.close()
        elif int(ret) < 0:
          error_File = open(errorfile, 'w')
          error_File.write("Program crashed, terminated by the system, return code " + ret + '\n')
          error_File.close()
        elif int(ret) > 0:
          error_File = open(errorfile, 'w')
          error_File.write("Program crashed, terminated by itself, return code " + ret + '\n')
          error_File.close()

        # Log time and return code information
        logname = os.path.join(logdir, 'logfile-run-{}.txt'.format(run_id))
        with open(logname, 'a') as logfile:
          logfile.write('code={}, time={:0.3f}\n'.format(ret,curr_time))

        # Print updates
        print_progressbar(index, run_number)

      print_progressbar(run_number, run_number)
      print("") # progress bar needs a newline after 100% reached
      # Print summary
      if options["verbose"]:
        print("========== SUMMARY ==========")
        print("Return codes:")
        for r in list(return_codes.keys()):
          print(("  %3s: %5d" % (str(r), return_codes[r])))

      # write summary file
      summary_file = os.path.join(logdir, 'summaryfile-run-{}'.format(ii))
      with open(summary_file, 'w') as f:
        f.write('runs: {}\n'.format(run_number))
        avg_time = tot_time / run_number
        f.write('avg time: {:0.3f}\n'.format(avg_time))

        if 'fi_rate' in locals():
          f.write('fi_rate: {}\n'.format(fi_rate))
          f.write('faults expected: {:0.3f}\n'.format(float(totalcycles) / float(fi_rate)))
          # count average number of injected faults
          nfaults = 0
          base = os.path.join(llfi_stat_dir,'llfi.stat.fi.injectedfaults.{}-*'.format(ii))
          logs = glob.glob(base)
          for log in logs:
            with open(log,'r') as log_f:
              nfaults += sum(1 for line in log_f)
          avg_faults = float(nfaults) / run_number

          f.write('faults avg: {:0.3f}\n'.format(avg_faults))

################################################################################

if __name__=="__main__":
  if len(sys.argv) == 1:
    help()
    exit(1)
  run(sys.argv[1:])
