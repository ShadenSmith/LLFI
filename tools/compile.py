#! /usr/bin/env python3

"""
llfi-compile takes source files(s) as input and generates a single LLVM IR file
"""

import sys, os, subprocess, tempfile
script_path = os.path.realpath(os.path.dirname(__file__))
sys.path.append(os.path.join(script_path, '../config'))
import llvm_paths

import argparse

llvmlink = os.path.join(llvm_paths.LLVM_DST_ROOT, "bin/llvm-link")
llvmgcc = os.path.join(llvm_paths.LLVM_GXX_BIN_DIR, "clang")
llvmgxx = os.path.join(llvm_paths.LLVM_GXX_BIN_DIR, "clang++")
prog = os.path.basename(sys.argv[0])

basedir = os.getcwd()

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

def help():
  parser = initParser()
  parser.print_help()

def initParser():
  parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    prog='llfi compile',
    epilog=__doc__,
  )
  parser.add_argument('SOURCES', nargs='+',
                      help='source files to compile')
  parser.add_argument('-o', '--output', default='a.out', dest='OUT',
                      help='LLVM intermediate representation (IR) output file')
  parser.add_argument('-I', action='append', default=[], dest='INCLUDE_DIRS',
                      help='include directory for header files')
  parser.add_argument('--readable', action='store_true', dest='READABLE',
                      help='generate human-readable IR file')
  parser.add_argument('-v', '--verbose', dest='VERBOSE', action='store_true',
                      help='show verbose information')
  return parser

def parseArgs(parser, args):
  options = parser.parse_args(args)

  # some post processing is necessary
  options.OUT = os.path.join(basedir, options.OUT)
  for index, opt in enumerate(options.INCLUDE_DIRS):
    options.INCLUDE_DIRS[index] = os.path.join(basedir, opt)
  for index, opt in enumerate(options.SOURCES):
    options.SOURCES[index] = os.path.join(basedir, opt)

  return options

################################################################################
def execute(execlist, options):
  verbosePrint(' '.join(execlist), options.VERBOSE)
  p = subprocess.Popen(execlist)
  p.wait()
  return p.returncode


def compileToIR(outputfile, inputfile, options):
  if inputfile.endswith(".c"):
    execlist = [llvmgcc]
  else:
    execlist = [llvmgxx]

  execlist.extend(['-w', '-emit-llvm', '-o', outputfile, inputfile])

  for header_dir in options.INCLUDE_DIRS:
    execlist.extend(['-I', header_dir])

  if options.READABLE:
    execlist.append('-S')
  else:
    execlist.append('-c')
  return execute(execlist, options)


def linkFiles(outputfile, inputlist, options):
  execlist = [llvmlink, '-o', outputfile]

  if options.READABLE:
    execlist.append('-S')

  execlist.extend(inputlist)
  return execute(execlist, options)

################################################################################
def compileProg(options):
  outputfile = options.OUT
  srcfiles = options.SOURCES
  verbosePrint("Source files to be compiled: ", options.VERBOSE)
  verbosePrint(", ".join(srcfiles), options.VERBOSE)
  verbosePrint("\n======Compile======", options.VERBOSE)

  if len(srcfiles) == 1:
    retcode = compileToIR(outputfile, srcfiles[0], options)
  else:
    tmpfiles = []
    for src in srcfiles:
      file_handler, tmpfile = tempfile.mkstemp()
      tmpfiles.append(tmpfile)
      retcode = compileToIR(tmpfile, src, options)
      if retcode != 0:
        break

    if retcode == 0:
      retcode = linkFiles(outputfile, tmpfiles, options)

  # cleaning up the temporary files
    for tmpfile in tmpfiles:
      try:
        os.remove(tmpfile)
      except:
        pass

  if retcode != 0:
    print("\nERROR: there was a compilation error, please follow"\
                          " the provided instructions for %s or compile the "\
                          "source file(s) to one single IR file manually." % prog, file=sys.stderr)
    sys.exit(retcode)


################################################################################

def run(args):
  parser = initParser()
  options = parseArgs(parser, args)
  compileProg(options)

if __name__ == "__main__":
  run(sys.argv[1:])
