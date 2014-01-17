cmake_minimum_required(VERSION 2.8)

include(../config/copy_utils.cmake)

project(bin)

copy(instrument.py instrument.py)
copy(injectfault.py injectfault.py)
copy(profile.py profile)
copy(__init__.py __init__.py)

genCopy()

