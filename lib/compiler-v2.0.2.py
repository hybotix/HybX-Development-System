"""
compiler-v2.0.2.py
Hybrid RobotiX — HybX Development System v2.0
Dale Weber <hybotix@hybridrobotix.io>

HybX compiler module. Orchestrates the full 8-step build pipeline for
Arduino UNO Q / Zephyr sketches, replacing arduino-cli compile entirely.

Build pipeline:
  1. Preprocess source files (library discovery)
  2. Compile sketch .cpp files
  3. Compile library .cpp files
  4. Compile core files (or use precompiled core.a)
  5. Link pass 1 — static check (memory-check.ld + syms-dynamic.ld)
  6. Link pass 2 — dynamic temp (build-dynamic.ld) → sketch.ino_temp.elf
  7. gen-rodata-ld — generate rodata_split.ld from temp ELF
  8. Link pass 3 — final (rodata_split.ld + build-dynamic.ld) → sketch.ino.elf
  9. strip — produces sketch.ino.elf (debug stripped)
  10. objcopy — produces sketch.ino.bin + sketch.ino.hex
  11. zephyr-sketch-tool — produces sketch.ino.elf-zsk.bin (flashable)

Usage:
    from compiler import HybXCompiler
    compiler = HybXCompiler(board, app_path)
    result = compiler.build()
    if result.success:
    else:
        print(f"ERROR: {result.error}")

License: MIT
"""

import os
import json
import subprocess
import shutil
import glob
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ── Build result ───────────────────────────────────────────────────────────────

@dataclass
class BuildResult:
    success:  bool             = False
    binary:   Optional[str]    = None   # path to sketch.ino.elf-zsk.bin
    elapsed:  float            = 0.0
    error:    Optional[str]    = None
    warnings: list[str]        = field(default_factory=list)
    objects:  list[str]        = field(default_factory=list)


# ── Compiler ───────────────────────────────────────────────────────────────────

class HybXCompiler:
    """
    Full build pipeline for Arduino UNO Q / Zephyr sketches.

    board     : board definition dict loaded from boards/uno-q.json
    app_path  : path to the app directory (e.g. ~/Arduino/UNO-Q/lsm6dsox)
    build_dir : output directory for compiled objects and binaries.
                Defaults to <app_path>/.cache/sketch/
    verbose   : if True, print each compiler command as it runs
    """

    def __init__(self,
                 board:     dict,
                 app_path:  str,
                 build_dir: Optional[str] = None,
                 verbose:   bool = False):
        self.board     = board
        self.app_path  = os.path.expanduser(app_path)
        self.build_dir = build_dir or os.path.join(self.app_path, ".cache", "sketch")
        # Final binaries go to <board_apps_root>/build/ — one place for all
        apps_root      = os.path.dirname(self.app_path)
        self.out_dir   = os.path.join(apps_root, "build")
        self.verbose   = verbose

        # Expand all ~ paths in board definition
        self._platform  = self._expand(board["platform"]["path"])
        self._toolchain = self._expand(board["toolchain"]["path"])
        self._variant   = board["platform"]["variant"]
        self._variant_path = os.path.join(self._platform, "variants", self._variant)
        self._core_path    = os.path.join(self._platform, "cores", "arduino")
        self._internal     = self._expand(board["libraries"]["internal"])
        self._user_libs    = self._expand(board["libraries"]["user"])
        self._platform_libs = os.path.join(self._platform, "libraries")
        self._tools         = self._expand(board.get("link", {}).get(
                                "rodata_tool", "")).rsplit("/", 1)[0]

    # ── Public interface ───────────────────────────────────────────────────────

    def build(self) -> BuildResult:
        """Run the full build pipeline. Returns a BuildResult."""
        start = time.monotonic()
        result = BuildResult()
        try:
            os.makedirs(self.build_dir, exist_ok=True)
            sketch_path = self._find_sketch()
            if not sketch_path:
                result.error = f"No sketch (.ino) found in {self.app_path}"
                return result


            # Step 1: Preprocess + library discovery
            cpp_path  = self._preprocess_sketch(sketch_path)
            libraries = self._discover_libraries(cpp_path)
            includes  = self._build_include_list(libraries)


            # Step 2: Compile sketch
            print("  Compiling...")
            sketch_obj = self._compile_file(cpp_path, includes, "sketch")
            objects = [sketch_obj]

            # Step 3: Compile libraries
            system_libs = set(self.board.get("system_libraries", []))
            for lib_name, lib_path in libraries.items():
                for src in self._find_sources(lib_path):
                    obj = self._compile_file(src, includes, f"libraries/{lib_name}")
                    objects.append(obj)

            # Step 4: Core (use precompiled core.a if available)
            core_archive = self._expand(self.board["link"].get("core_archive", ""))
            if os.path.exists(core_archive):
                core_obj = self._compile_core_stubs(includes)
                objects.extend(core_obj)
            else:
                for src in self._find_sources(self._core_path):
                    obj = self._compile_file(src, includes, "core")
                    objects.append(obj)
                core_archive = None

            # Steps 5-8: Link passes
            print("  Linking...")
            elf_path = self._link(objects, core_archive)

            # Step 9: Strip
            stripped = self._strip(elf_path)

            # Step 10: objcopy
            self._objcopy(stripped)

            # Step 11: zephyr-sketch-tool → .elf-zsk.bin
            binary = self._zephyr_sketch_tool(stripped)

            print("  Done.")
            # Copy final binary to <app>/bin/<project>.elf-zsk.bin
            import shutil
            project_name = os.path.basename(self.app_path)
            os.makedirs(self.out_dir, exist_ok=True)
            named_binary = os.path.join(self.out_dir,
                                        f"{project_name}.elf-zsk.bin")
            shutil.copy2(binary, named_binary)

            # Clean up intermediate build artifacts — keep storage lean
            import shutil
            shutil.rmtree(self.build_dir, ignore_errors=True)

            result.success = True
            result.binary  = named_binary
            result.objects = objects
            result.elapsed = time.monotonic() - start

        except Exception as e:
            result.error   = str(e)
            result.elapsed = time.monotonic() - start
            print(f"[build] ERROR: {e}")

        return result

    # ── Private: sketch handling ───────────────────────────────────────────────

    def _find_sketch(self) -> Optional[str]:
        """Find the .ino sketch file."""
        sketch_dir = os.path.join(self.app_path, "sketch")
        matches    = glob.glob(os.path.join(sketch_dir, "*.ino"))
        return matches[0] if matches else None

    def _preprocess_sketch(self, sketch_path: str) -> str:
        """
        Preprocess the .ino into a .cpp file by prepending the standard
        Arduino sketch preamble and running ctags for function prototypes.
        Returns the path to the .cpp file.
        """
        cpp_dir  = os.path.join(self.build_dir, "sketch")
        os.makedirs(cpp_dir, exist_ok=True)
        cpp_path = os.path.join(cpp_dir, os.path.basename(sketch_path) + ".cpp")

        with open(sketch_path, "r") as f:
            sketch_src = f.read()

        # Arduino preamble — same as arduino-cli generates
        preamble = (
            "#include <Arduino.h>\n"
            "#line 1 \"" + sketch_path + "\"\n"
        )

        with open(cpp_path, "w") as f:
            f.write(preamble + sketch_src)

        return cpp_path

    # ── Private: library discovery ─────────────────────────────────────────────

    def _discover_libraries(self, cpp_path: str,
                             _visited: set | None = None) -> dict:
        """
        Parse the .cpp for #include directives and resolve them to library
        paths. Searches: user libs (~/.Arduino/libraries), platform libs,
        internal libs (~/.arduino15/internal).

        _visited tracks already-scanned files to prevent infinite recursion
        from circular includes.

        Returns {library_name: library_path}
        """
        if _visited is None:
            _visited = set()

        if cpp_path in _visited:
            return {}
        _visited.add(cpp_path)

        libraries = {}

        try:
            with open(cpp_path, "r", errors="ignore") as f:
                source = f.read()
        except OSError:
            return {}

        import re
        headers = re.findall(r'#include\s*[<"]([^>"]+\.h)[>"]', source)

        for header in headers:
            lib_path = self._resolve_header(header)
            if lib_path and lib_path not in libraries.values():
                lib_name = os.path.basename(lib_path)
                libraries[lib_name] = lib_path
                # Recursively discover transitive dependencies via headers only
                for hdr in self._find_headers(lib_path):
                    sub_libs = self._discover_libraries(hdr, _visited)
                    for k, v in sub_libs.items():
                        if v not in libraries.values():
                            libraries[k] = v

        return libraries

    def _resolve_header(self, header: str) -> Optional[str]:
        """Resolve a header filename to a library directory."""
        search_paths = [
            self._user_libs,
            self._platform_libs,
        ]

        # User libs: direct subdirectory match
        for base in search_paths:
            if not os.path.isdir(base):
                continue
            for entry in os.scandir(base):
                if not entry.is_dir():
                    continue
                # Check if header exists in lib root or src/
                for sub in ["", "src", "utility"]:
                    candidate = os.path.join(entry.path, sub, header)
                    if os.path.exists(candidate):
                        return entry.path

        # Internal libs: ~/.arduino15/internal/<Name>_<version>_<hash>/<Name>/
        if os.path.isdir(self._internal):
            for entry in os.scandir(self._internal):
                if not entry.is_dir():
                    continue
                # The actual library is a subdirectory inside the hash dir
                for sub_entry in os.scandir(entry.path):
                    if not sub_entry.is_dir():
                        continue
                    for sub in ["", "src", "utility"]:
                        candidate = os.path.join(sub_entry.path, sub, header)
                        if os.path.exists(candidate):
                            return sub_entry.path

        return None

    # ── Private: include path construction ────────────────────────────────────

    def _build_include_list(self, libraries: dict) -> list[str]:
        """Build the full -I include path list."""
        includes = []

        # Core includes
        for inc in self.board["compile"]["core_includes"]:
            includes.append(os.path.join(self._platform, inc))

        # Library includes
        for lib_path in libraries.values():
            includes.append(lib_path)
            src_path = os.path.join(lib_path, "src")
            if os.path.isdir(src_path):
                includes.append(src_path)

        # Platform library includes (Wire, SPI etc.)
        for entry in os.scandir(self._platform_libs):
            if entry.is_dir() and entry.path not in includes:
                includes.append(entry.path)

        return includes

    # ── Private: compilation ───────────────────────────────────────────────────

    def _compile_file(self,
                      src_path:  str,
                      includes:  list[str],
                      obj_subdir: str) -> str:
        """
        Compile a single .cpp file to a .o object.
        Returns the path to the .o file.
        """
        obj_dir = os.path.join(self.build_dir, obj_subdir)
        os.makedirs(obj_dir, exist_ok=True)

        rel_name = os.path.basename(src_path)
        obj_path = os.path.join(obj_dir, rel_name + ".o")

        compiler = os.path.join(
            self._toolchain,
            self.board["compile"]["compiler"]
        )

        cmd = [compiler]

        # Debug + optimize
        cmd += [self.board["compile"]["debug"],
                self.board["compile"]["optimize"]]

        # C++ standard
        cmd += ["-std=" + self.board["compile"]["std"]]

        # Compile only
        cmd += ["-c"]

        # Picolibc define
        cmd += ["-D_PICOLIBC_CTYPE_SMALL=1"]

        # Suppress warnings during compilation
        cmd += ["-w"]

        # imacros
        for macro_file in self.board["compile"]["imacros"]:
            cmd += ["-imacros" + os.path.join(self._platform, macro_file)]

        # @cxxflags.txt
        cxxflags_path = os.path.join(
            self._platform,
            self.board["compile"]["cxxflags_file"]
        )
        if os.path.exists(cxxflags_path):
            cmd += ["@" + cxxflags_path]

        # Compile flags from board def
        cmd += self.board["compile"]["flags"]

        # CPU/FPU flags
        cmd += [
            f"-mcpu={self.board['compile']['cpu']}",
            f"-mfloat-abi={self.board['compile']['float_abi']}",
            f"-mfpu={self.board['compile']['fpu']}"
        ]

        # Defines
        for define in self.board["compile"]["defines"]:
            cmd += [f"-D{define}"]

        # Include paths
        for inc in includes:
            # Paths with spaces need quoting — subprocess handles this
            cmd += [f"-I{inc}"]

        # iprefix + @includes.txt
        includes_path = os.path.join(
            self._platform,
            self.board["compile"]["includes_file"]
        )
        cmd += [f"-iprefix{self._variant_path}"]
        if os.path.exists(includes_path):
            cmd += ["@" + includes_path]

        # Source and output
        cmd += [src_path, "-o", obj_path]

        self._run(cmd, f"compile {rel_name}")
        return obj_path

    def _compile_core_stubs(self, includes: list[str]) -> list[str]:
        """
        Compile only the variant-specific files (analogReference.cpp etc.)
        that are NOT in core.a. Returns list of .o paths.
        """
        objects = []
        variant_srcs = glob.glob(os.path.join(self._variant_path, "*.cpp"))
        for src in variant_srcs:
            obj = self._compile_file(src, includes, "core")
            objects.append(obj)
        return objects

    # ── Private: linking ───────────────────────────────────────────────────────

    def _link(self, objects: list[str], core_archive: Optional[str]) -> str:
        """
        Run the 3-pass link sequence:
          Pass 1: static check link
          Pass 2: dynamic temp link → temp.elf
          gen-rodata-ld → rodata_split.ld
          Pass 3: final link → sketch.ino.elf

        Returns path to the final debug ELF.
        """
        link    = self.board["link"]
        linker  = os.path.join(self._toolchain,
                               self.board["compile"]["compiler"])
        ld_base = [
            linker,
            f"-L{self.build_dir}",
            f"-L{self._variant_path}",
            "-Wl,--gc-sections",
            f"-mcpu={self.board['compile']['cpu']}",
            f"-mfloat-abi={self.board['compile']['float_abi']}",
            f"-mfpu={self.board['compile']['fpu']}",
            f"-std={self.board['compile']['std']}",
            "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics",
            "-fno-unwind-tables", "-fno-use-cxa-atexit",
            "-lstdc++", "-lsupc++", "-lnosys", "-nostdlib",
            "--specs=nano.specs", "--specs=nosys.specs",
        ]

        obj_args    = objects[:]
        core_group  = []
        if core_archive:
            core_group = [
                "-Wl,--start-group",
                core_archive,
                "-lstdc++", "-lsupc++", "-lm",
                "-Wl,--end-group"
            ]
        entry_flag  = ["-e", "main"]
        ld_path     = os.path.join(self._platform, "variants")

        check_elf   = os.path.join(self.build_dir, "sketch.ino_check.tmp")
        temp_elf    = os.path.join(self.build_dir, "sketch.ino_temp.elf")
        temp_map    = os.path.join(self.build_dir, "sketch.ino_temp.map")
        rodata_ld   = os.path.join(self.build_dir, "rodata_split.ld")
        debug_elf   = os.path.join(self.build_dir, "sketch.ino_debug.elf")

        # Pass 1: static check
        self._run(
            ld_base + obj_args + core_group + entry_flag + [
                f"-T{self._variant_path}/syms-dynamic.ld",
                f"-T{os.path.join(self._platform, 'variants', '_ldscripts', 'memory-check.ld')}",
                f"-T{os.path.join(self._platform, 'variants', '_ldscripts', 'build-static.ld')}",
                "-o", check_elf
            ],
            "link pass 1"
        )

        # Pass 2: dynamic temp
        self._run(
            ld_base + obj_args + core_group + entry_flag + [
                f"-T{os.path.join(self._platform, 'variants', '_ldscripts', 'build-dynamic.ld')}",
                "-r",
                f"-Wl,-Map,{temp_map}",
                "-o", temp_elf
            ],
            "link pass 2"
        )

        # gen-rodata-ld
        rodata_tool = self._expand(link["rodata_tool"])
        self._run(
            [rodata_tool, temp_elf, rodata_ld, "dynamic"],
            "gen-rodata-ld"
        )

        # Pass 3: final
        final_map = os.path.join(self.build_dir, "sketch.ino.map")
        self._run(
            ld_base + obj_args + core_group + entry_flag + [
                f"-T{rodata_ld}",
                f"-T{os.path.join(self._platform, 'variants', '_ldscripts', 'build-dynamic.ld')}",
                "-r",
                f"-Wl,-Map,{final_map}",
                "-o", debug_elf
            ],
            "link pass 3"
        )

        return debug_elf

    # ── Private: post-link ─────────────────────────────────────────────────────

    def _strip(self, debug_elf: str) -> str:
        """Strip debug symbols. Returns path to stripped ELF."""
        stripped = os.path.join(self.build_dir, "sketch.ino.elf")
        strip    = os.path.join(self._toolchain, "arm-zephyr-eabi-strip")
        self._run(
            [strip, "--strip-debug", debug_elf, "-o", stripped],
            "strip"
        )
        return stripped

    def _objcopy(self, elf_path: str) -> None:
        """Generate .bin and .hex from ELF."""
        objcopy = os.path.join(self._toolchain, "arm-zephyr-eabi-objcopy")
        bin_out = elf_path.replace(".elf", ".bin")
        hex_out = elf_path.replace(".elf", ".hex")
        self._run(
            [objcopy, "-O", "binary", elf_path, bin_out],
            "objcopy bin"
        )
        self._run(
            [objcopy, "-O", "ihex", "-R", ".eeprom", elf_path, hex_out],
            "objcopy hex"
        )

    def _zephyr_sketch_tool(self, elf_path: str) -> str:
        """
        Run zephyr-sketch-tool to produce the flashable .elf-zsk.bin.
        Returns path to the binary.
        """
        tool   = self._expand(self.board["link"]["sketch_tool"])
        binary = elf_path + "-zsk.bin"
        self._run([tool, elf_path], "zephyr-sketch-tool (elf)")
        bin_path = elf_path.replace(".elf", ".bin")
        self._run([tool, bin_path], "zephyr-sketch-tool (bin)")
        return binary

    # ── Private: helpers ───────────────────────────────────────────────────────

    def _find_sources(self, lib_path: str) -> list[str]:
        """Find all compilable .cpp and .c source files in a library."""
        sources = []
        for pattern in ["*.cpp", "*.c"]:
            sources.extend(glob.glob(os.path.join(lib_path, pattern)))
            sources.extend(glob.glob(os.path.join(lib_path, "src", pattern)))
        return sorted(sources)

    def _find_headers(self, lib_path: str) -> list[str]:
        """Find all .h header files in a library — for dependency scanning only."""
        headers = []
        for pattern in ["*.h", "*.hpp"]:
            headers.extend(glob.glob(os.path.join(lib_path, pattern)))
            headers.extend(glob.glob(os.path.join(lib_path, "src", pattern)))
        return sorted(headers)

    def _expand(self, path: str) -> str:
        """Expand ~ in a path string."""
        return os.path.expanduser(path) if path else path

    def _run(self, cmd: list[str], step: str) -> None:
        """
        Run a subprocess command. Raises RuntimeError on failure.
        No silent failures — every step is checked.
        """
        if self.verbose:
            print("  $ " + " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"[build] FAILED at step '{step}' (exit {result.returncode})\n"
                f"CMD: {' '.join(cmd[:3])} ...\n"
                f"STDERR: {result.stderr.strip()[:500]}"
            )

        if result.stderr.strip():
            # Warnings — don't fail but record them
            if self.verbose:
                print(f"  [warn] {result.stderr.strip()[:200]}")
