#!/usr/bin/env python3

"""
llfi-instrument takes a single IR file as input and generates IR files (and
executables, depending on the -IRonly option) with instrumented profiling and
fault injection function calls


Prerequisites:
  1. 'input.yaml' contains appropriate options for LLFI and must be under the
     same directory as IR_FILE
"""

# Everytime the contents of compileOption is changed in input.yaml
# this script should be run to create new fi.exe and prof.exe

import sys, os, shutil
import yaml
import subprocess
import argparse

script_path = os.path.realpath(os.path.dirname(__file__))
sys.path.append(os.path.join(script_path, '../config'))
import llvm_paths

optbin = os.path.join(llvm_paths.LLVM_DST_ROOT, "bin/opt")
llcbin = os.path.join(llvm_paths.LLVM_DST_ROOT, "bin/llc")
llvmgcc = os.path.join(llvm_paths.LLVM_GXX_BIN_DIR, "clang")
llvmgxx = os.path.join(llvm_paths.LLVM_GXX_BIN_DIR, "clang++")
llfilinklib = os.path.join(script_path, "../runtime_lib")
prog = os.path.basename(sys.argv[0])
basedir = os.getcwd()

if sys.platform == "linux" or sys.platform == "linux2":
  llfilib = os.path.join(script_path, "../llvm_passes/llfi-passes.so")
elif sys.platform == "darwin":
  llfilib = os.path.join(script_path, "../llvm_passes/llfi-passes.dylib")
else:
  print("ERROR: LLFI does not support platform " + sys.platform + ".")
  exit(1)

def help():
  parser = initParser()
  parser.print_help()

################################################################################
def run(args):
  parser = initParser()
  options = parseArgs(parser, args)
  yamlOpts = checkInputYaml(options)
  compileOptions = readCompileOption(yamlOpts, options)
  compileProg(options, compileOptions)
################################################################################

def initParser():
  parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    prog='llfi instrument',
    epilog=__doc__,
  )
  parser.add_argument('IR_FILE', help='source IR file to instrument')
  parser.add_argument('--dir', default='llfi', dest='DIR',
                      help='directory to store instrumented executables')
  parser.add_argument('-l',  action='append', metavar='LIB',
                      help='link against LIB')
  parser.add_argument('-L', action='append', metavar='DIR',
                      help='add DIR to search path for linking')
  parser.add_argument('--readable', action='store_true', dest='READABLE',
                      help='generate human-readable IR files')
  parser.add_argument('--IRonly', action='store_true',
                      help='only generate instrumented IR files; linking and \
                      executable generation will be done manually')
  parser.add_argument('-v', '--verbose', action='store_true', dest='VERBOSE',
                      help='show verbose information')
  # secret option set by YAML
  parser.add_argument('--gendotgraph',dest='GEN_DOT_GRAPH',action='store_true',
                      help=argparse.SUPPRESS)
  return parser

def parseArgs(parser, args):
  options = parser.parse_args(args)

  # some post processing is necessary
  options.DIR = options.DIR.rstrip('/')
  options.IR_FILE = os.path.join(basedir, options.IR_FILE)
  for _, d in enumerate(options.L):
    d = os.path.join(basedir, d)

  if '/' in options.DIR:
    usage("Cannot specify embedded directories for --dir")
  else:
    srcpath = os.path.dirname(options.IR_FILE)
    fullpath = os.path.join(srcpath, options.DIR)
    if os.path.exists(fullpath):
      usage(options.DIR + " already exists under " + srcpath + \
            ", you can either specify a different directory for --dir or " +\
            "remove " + options.DIR + " from " + srcpath)
    else:
      try:
        os.mkdir(fullpath)
        options.DIR = fullpath
      except:
        usage("Unable to create a directory named " + options.DIR +\
              " under " + srcpath)
  return options

def usage(msg = None):
  retval = 0
  if msg is not None:
    retval = 1
    msg = "ERROR: " + msg
    print(msg, file=sys.stderr)
  print(__doc__ % globals(), file=sys.stderr)
  sys.exit(retval)


def verbosePrint(msg, verbose):
  if verbose:
    print(msg)

def checkInputYaml(options):
  #Check for input.yaml's presence
  srcpath = os.path.dirname(options.IR_FILE)
  try:
    f = open(os.path.join(srcpath, 'input.yaml'), 'r')
  except:
    print("ERROR: No input.yaml file in the %s directory." % srcpath)
    os.rmdir(options.DIR)
    exit(1)

  #Check for input.yaml's correct formmating
  try:
    doc = yaml.load(f)
    f.close()
    verbosePrint(yaml.dump(doc), options.VERBOSE)
  except:
    print("Error: input.yaml is not formatted in proper YAML (reminder: use spaces, not tabs)")
    os.rmdir(options.DIR)
    exit(1)

  #Check for compileOption in input.yaml
  cOpt = None
  try:
    cOpt = doc["compileOption"]
  except:
    print("ERROR: Please include compileOptions in input.yaml.")
    os.rmdir(options.DIR)
    exit(1)
  return cOpt

################################################################################
def execCompilation(execlist, options):
  verbosePrint(' '.join(execlist), options.VERBOSE)
  p = subprocess.Popen(execlist)
  p.wait()
  return p.returncode

################################################################################
def readCompileOption(cOpt, options):
  compileOptions = []

  ###Instruction selection method
  if "instSelMethod" not in cOpt:
    print ("\n\nERROR: Please include an 'instSelMethod' key value pair under compileOption in input.yaml.\n")
    exit(1)
  else:
    validMethods = ["insttype", "funcname", "custominstselector"]
    # Generate list of instruction selection methods
    # TODO: Generalize and document
    instSelMethod = cOpt["instSelMethod"]
    for method in instSelMethod:
      methodName = list(method.keys())[0]
      if methodName not in validMethods:
        print ("\n\nERROR: Unknown instruction selection method in input.yaml.\n")
        exit(1)
      if methodName != "custominstselector":
        compileOptions.append("-%s" % (str(methodName)))
      else:
        compileOptions.append('-custominstselector')
        compileOptions.append('-fiinstselectorname='+method[methodName])
        continue # custom selectors don't have attributes

      # Ensure that 'include' is specified at least
      # TODO: This isn't a very extendible way of doing this.
      if methodName != "custominstselector" and "include" not in method[methodName]:
        print(("\n\nERROR: An 'include' list must be present for the %s method in input.yaml.\n" % (methodName)))
        exit(1)

      # Parse all options for current method
      for attr in list(method[methodName].keys()):
        prefix = "-%s" % (str(attr))
        if methodName == "insttype":
          prefix += "inst="
        elif methodName == "funcname":
          prefix += "func="
        else: # add the ability to give custom options here?
          pass
        # Generate list of options for attribute
        opts = [prefix + opt for opt in method[methodName][attr]]
        compileOptions.extend(opts)

  ###Register selection method
  if "regSelMethod" not in cOpt:
    print ("\n\nERROR: Please include an 'regSelMethod' key value pair under compileOption in input.yaml.\n")
    exit(1)
  else:
    #Select by register location
    if cOpt["regSelMethod"] == 'regloc':
      compileOptions.append('-regloc')
      if "regloc" not in cOpt:
        print ("\n\nERROR: An 'regloc' key value pair must be present for the regloc method in input.yaml.\n")
        exit(1)
      else:
        compileOptions.append('-'+cOpt["regloc"])

    #Select by custom register
    elif cOpt["regSelMethod"]  == 'customregselector':
      compileOptions.append('-customregselector')
      if "customRegSelector" not in cOpt:
        print ("\n\nERROR: An 'customRegSelector' key value pair must be present for the customregselector method in input.yaml.\n")
        exit(1)
      else:
          compileOptions.append('-firegselectorname='+cOpt["customRegSelector"])
          if "customRegSelectorOption" in cOpt:
            for opt in cOpt["customRegSelectorOption"]:
              compileOptions.append(opt)

    else:
      print ("\n\nERROR: Unknown Register selection method in input.yaml.\n")
      exit(1)

  ###Injection Trace selection
  if "includeInjectionTrace" in cOpt:
    for trace in cOpt["includeInjectionTrace"]:
      if trace == 'forward':
        compileOptions.append('-includeforwardtrace')
      elif trace == 'backward':
        compileOptions.append('-includebackwardtrace')
      else:
        print ("\n\nERROR: Invalid value for trace (forward/backward allowed) in input.yaml.\n")
        exit(1)

  ###Tracing Proppass
  if "tracingPropagation" in cOpt:
    print(("\nWARNING: You enabled 'tracingPropagation' option in input.yaml. "
           "The generate executables will be able to output dynamic values for instructions. "
           "However, the executables take longer time to execute. If you don't want the trace, "
           "please disable the option and re-run %s." %prog))
    compileOptions.append('-insttracepass')
    if 'tracingPropagationOption' in cOpt:
      if "debugTrace" in cOpt["tracingPropagationOption"]:
        if(str(cOpt["tracingPropagationOption"]["debugTrace"]).lower() == "true"):
          compileOptions.append('-debugtrace')
      if "maxTrace" in cOpt["tracingPropagationOption"]:
        assert isinstance(cOpt["tracingPropagationOption"]["maxTrace"], int)==True, "maxTrace must be an integer in input.yaml"
        assert int(cOpt["tracingPropagationOption"]["maxTrace"])>0, "maxTrace must be greater than 0 in input.yaml"
        compileOptions.append('-maxtrace')
        compileOptions.append(str(cOpt["tracingPropagationOption"]["maxTrace"]))

      ###Dot Graph Generation selection
      if "generateCDFG" in cOpt["tracingPropagationOption"]:
        options.GEN_DOT_GRAPH = True

  return compileOptions

################################################################################
def _suffixOfIR(options):
  if options.READABLE:
    return ".ll"
  else:
    return ".bc"

def compileProg(options, compileOptions):
  srcbase = os.path.basename(options.IR_FILE)
  progbin = os.path.join(options.DIR, srcbase[0 : srcbase.rfind(".")])

  llfi_indexed_file = progbin + "-llfi_index"
  proffile = progbin + "-profiling"
  fifile = progbin + "-faultinjection"
  tmpfiles = []

  execlist = [optbin, '-load', llfilib, '-genllfiindexpass','-o',
              llfi_indexed_file + _suffixOfIR(options), options.IR_FILE]
  if options.READABLE:
    execlist.append('-S')
  if options.GEN_DOT_GRAPH:
    execlist.append('-dotgraphpass')
  retcode = execCompilation(execlist, options)

  if retcode == 0:
    execlist = [optbin, '-load', llfilib, '-profilingpass']
    execlist2 = ['-o', proffile + _suffixOfIR(options), llfi_indexed_file + _suffixOfIR(options)]
    execlist.extend(compileOptions)
    execlist.extend(execlist2)
    if options.READABLE:
      execlist.append("-S")
    retcode = execCompilation(execlist, options)

  if retcode == 0:
    execlist = [optbin, '-load', llfilib, "-faultinjectionpass"]
    execlist2 = ['-o', fifile + _suffixOfIR(options), llfi_indexed_file + _suffixOfIR(options)]
    execlist.extend(compileOptions)
    execlist.extend(execlist2)
    if options.READABLE:
      execlist.append("-S")
    retcode = execCompilation(execlist, options)

  if retcode != 0:
    print("\nERROR: there was an error during running the "\
                         "instrumentation pass, please follow"\
                         " the provided instructions for %s." % prog, file=sys.stderr)
    shutil.rmtree(options.DIR, ignore_errors = True)
    sys.exit(retcode)

  if not options.IRonly:
    if retcode == 0:
      execlist = [llcbin, '-filetype=obj', '-o', proffile + '.o', proffile + _suffixOfIR(options)]
      tmpfiles.append(proffile + '.o')
      retcode = execCompilation(execlist, options)
    if retcode == 0:
      execlist = [llcbin, '-filetype=obj', '-o', fifile + '.o', fifile + _suffixOfIR(options)]
      tmpfiles.append(fifile + '.o')
      retcode = execCompilation(execlist, options)

    liblist = []
    for lib_dir in options.L:
      liblist.extend(["-L", lib_dir])
    for lib in options.l:
      liblist.append("-l" + lib)
    liblist.append("-Wl,-rpath")
    liblist.append(llfilinklib)

    if retcode == 0:
      execlist = [llvmgcc, '-o', proffile + '.exe', proffile + '.o', '-L'+llfilinklib , '-lllfi-rt']
      execlist.extend(liblist)
      retcode = execCompilation(execlist, options)
      if retcode != 0:
        print("...Error compiling with " + os.path.basename(llvmgcc) + ", trying with " + os.path.basename(llvmgxx) + ".") 
        execlist[0] = llvmgxx
        retcode = execCompilation(execlist, options)
    if retcode == 0:
      execlist = [llvmgcc, '-o', fifile + '.exe', fifile + '.o', '-L'+llfilinklib , '-lllfi-rt']
      execlist.extend(liblist)
      retcode = execCompilation(execlist, options)
      if retcode != 0:
        print("...Error compiling with " + os.path.basename(llvmgcc) + ", trying " + os.path.basename(llvmgxx) + ".") 
        execlist[0] = llvmgxx
        retcode = execCompilation(execlist, options)


    for tmpfile in tmpfiles:
      try:
        os.remove(tmpfile)
      except:
        pass
    if retcode != 0:
      print("\nERROR: there was an error during linking and generating executables,"\
                           "Please take %s and %s and generate the executables manually (linking llfi-rt "\
                           "in directory %s)." %(proffile + _suffixOfIR(), fifile + _suffixOfIR(), llfilinklib), file=sys.stderr)
      sys.exit(retcode)
    else:
      print("\nSuccess", file=sys.stderr)

if __name__=="__main__":
  run(sys.argv[1:])
