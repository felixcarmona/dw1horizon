# Horizon Play, the host program (docs/player.md). SDL2 is fetched at a pinned release and linked statically, so
# the bundle is the program, the core library and the BIOS. The core is built by build.py from its own source.
cmake_minimum_required(VERSION 3.16)
project(horizon_play C)

option(HORIZON_GLES "Use OpenGL ES 3 (Android)" OFF)

include(FetchContent)
if(ANDROID)
  # Android: SDL's Java side loads libSDL2.so and libmain.so (this program as a library)
  set(SDL_SHARED ON CACHE BOOL "" FORCE)
  set(SDL_STATIC OFF CACHE BOOL "" FORCE)
  set(HORIZON_GLES ON CACHE BOOL "" FORCE)
else()
  set(SDL_SHARED OFF CACHE BOOL "" FORCE)
  set(SDL_STATIC ON CACHE BOOL "" FORCE)
endif()
set(SDL_TEST OFF CACHE BOOL "" FORCE)
set(SDL2_DISABLE_INSTALL ON CACHE BOOL "" FORCE)
FetchContent_Declare(SDL2
  URL https://github.com/libsdl-org/SDL/releases/download/release-2.32.10/SDL2-2.32.10.tar.gz
  URL_HASH SHA256=5f5993c530f084535c65a6879e9b26ad441169b3e25d789d83287040a9ca5165)
FetchContent_MakeAvailable(SDL2)

if(ANDROID)
  add_library(horizon-play SHARED horizon_play.c overlay.c controls.c menu.c)
  set_target_properties(horizon-play PROPERTIES OUTPUT_NAME main)
  target_link_libraries(horizon-play PRIVATE SDL2::SDL2main SDL2::SDL2 GLESv3 log)
  # 16 KB pages (Android 15+ devices)
  target_link_options(horizon-play PRIVATE "-Wl,-z,max-page-size=16384")
else()
  add_executable(horizon-play WIN32 MACOSX_BUNDLE horizon_play.c overlay.c controls.c menu.c)
  target_link_libraries(horizon-play PRIVATE SDL2::SDL2main SDL2::SDL2-static)
endif()
if(HORIZON_GLES)
  target_compile_definitions(horizon-play PRIVATE HORIZON_GLES)
endif()
set(HORIZON_VERSION "" CACHE STRING "The version shown in the menu (tools/version.py)")
if(HORIZON_VERSION)
  target_compile_definitions(horizon-play PRIVATE "HORIZON_VERSION=\"${HORIZON_VERSION}\"")
endif()
if(MSVC)
  target_compile_definitions(horizon-play PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()
set_target_properties(horizon-play PROPERTIES
  MACOSX_BUNDLE_BUNDLE_NAME "Horizon Play"
  MACOSX_BUNDLE_GUI_IDENTIFIER "com.dw1horizon.play")
