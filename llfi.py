#!/usr/bin/env python3
'''
LLFI - LLVM based Fault Injector

usage: llfi CMD [args]

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

def print_help():
  s = \
'''{}
Supported commands are:
    {}

You can use `llfi help CMD` for information about a specific tool.
'''
  print(s.format(__doc__, '\n    '.join(sorted(cmds.keys()))))

if __name__ == '__main__':
  # Empty invocation, just print help
  if len(sys.argv) == 1:
    print_help()
    sys.exit(0)

  cmd = sys.argv[1]
  args = sys.argv[2:] # possibly []

  if cmd == 'help' or cmd == '-h':
    if len(args) == 0:
      print_help()
    elif args[0] in cmds:
      cmds[args[0]].help() # specific sub-command help
    else:
      print("llfi: {!r} is not a recognized command.".format(args[0]))
      print_help()
    sys.exit(0)

  # Check for invalid command
  if cmd not in cmds:
    print("llfi: {!r} is not a recognized command.".format(cmd))
    print_help()
    sys.exit(1)

  # Execute command!
  cmds[cmd].run(args)

