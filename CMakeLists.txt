cmake_minimum_required(VERSION 2.8)

include(config/copy_utils.cmake)

add_subdirectory(llvm_passes)
add_subdirectory(runtime_lib)
add_subdirectory(bin)
add_subdirectory(tools)
add_subdirectory(config)

copy(llfi.py llfi)
genCopy()
