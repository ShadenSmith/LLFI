cmake_minimum_required(VERSION 2.8)

include(../config/copy_utils.cmake)

project(tools)

copy(__init__.py __init__.py)
copy(tracediff.py tracediff)
copy(traceontograph.py traceontograph)
copy(tracetools.py tracetools.py)
copy(traceunion.py traceunion)
copy(stats.py stats.py)
copy(compile.py compile.py)

genCopy()

