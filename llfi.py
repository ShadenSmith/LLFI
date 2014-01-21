#!/usr/bin/env python2
'''
LLFI - LLVM based Fault Injector

LLFI is a toolchain used to inject faults into application code.
'''

# System imports
import sys

# LLFI imports
import bin.inject as inject
import bin.instrument as instrument
import bin.profile as profile
import tools.stats as stats

# Accepted commands mapped to their corresponding module, executed in the
# form `llfi <cmd>`
cmds = {
  'help' : int,
  'inject' : inject,
  'instrument' : instrument,
  'profile' : profile,
  'stats' : stats,
}

def print_usage():
  print "usage: llfi CMD [args]"

def print_help():
  s = \
'''{}
Supported commands are:
    {}

You can use `llfi help CMD` for information about a specific tool.
'''
  print s.format(__doc__, '\n    '.join(sorted(cmds.keys())))

if __name__ == '__main__':
  if len(sys.argv) == 1:
    # Empty invocation, just print help
    print_usage()
    print_help()
    sys.exit(0)

  cmd = sys.argv[1]
  args = sys.argv[2:]

  if cmd == 'help':
    if args:
      try:
        cmds[args[0]].help()
      except:
        print "llfi: {!r} is not a recognized command.".format(args[0])
        print_usage()
    else:
      print_usage()
      print_help()
  else:
    if cmd not in cmds:
      print "llfi: {!r} is not a recognized command.".format(cmd)
      print_usage()
      sys.exit(1)

    # Execute command!
    cmds[cmd].run(args)

