# Known Issues and Platform-Specific Install Notes

This document covers real installation issues encountered during the OSMP sovereign node build on constrained hardware (Android/Termux, Raspberry Pi, embedded Linux). Every issue below was hit during a live install. Root causes and fixes are documented.

---

## Termux (Android) Install

Termux is the primary path for Android sovereign nodes. Install Termux from **F-Droid, not the Play Store**. The Play Store version is outdated and will fail.

### Issue 1: pydantic-core requires Rust compiler

**Error:** `error: can't find Rust compiler`
**Root cause:** pydantic-core ships pre-built wheels for most platforms but not for Termux/aarch64-linux-android. pip tries to build from source, which requires Rust.
**Fix:**
```bash
pkg install rust
export CARGO_BUILD_TARGET=aarch64-linux-android
export ANDROID_API_LEVEL=34
pip install pydantic-core
```

### Issue 2: npm PATH not set in Termux

**Error:** `npm: command not found` after installing Node.js
**Root cause:** Termux installs npm but does not always add it to PATH.
**Fix:**
```bash
pkg install nodejs-lts
export PATH=$PATH:$PREFIX/bin
```

### Issue 3: Python version mismatch

**Error:** Various import failures with Python 3.14 pre-release
**Root cause:** Some packages do not yet have wheels for Python 3.14.
**Fix:** Use Python 3.12 or 3.13 on constrained platforms. OSMP requires Python >= 3.9.

### Issue 4: PowerInfer / llama.cpp build failures

**Error:** CMake errors during PowerInfer install
**Root cause:** Upstream of OSMP. PowerInfer's CMake configuration assumes desktop Linux toolchains.
**Fix:** This is not an OSMP issue. See PowerInfer documentation for mobile builds.

---

## Raspberry Pi (Pi Zero 2W)

### Issue 5: pip install --break-system-packages required

**Error:** `error: externally-managed-environment`
**Root cause:** Modern Debian/Ubuntu marks the system Python as externally managed.
**Fix:**
```bash
pip install osmp --break-system-packages
```
Or use a virtual environment:
```bash
python3 -m venv osmp-env
source osmp-env/bin/activate
pip install osmp
```

### Issue 6: zstandard build requires gcc

**Error:** Build failure when installing D:PACK optional dependency
**Root cause:** zstandard compiles a C extension.
**Fix:**
```bash
sudo apt install build-essential python3-dev
pip install osmp[dpack]
```
Note: D:PACK is optional. Basic encode/decode/validate works without it.

---

## General Python Issues

### Issue 7: Old import pattern (pre-2.0)

**Symptom:** Five attempts to import, none work:
```python
# These all fail or require too much setup:
import osmp                          # ModuleNotFoundError
from osmp import encode              # AttributeError
from osmp import SALEncoder          # works, but then what?
enc = SALEncoder()                   # TypeError: missing asd
enc = SALEncoder(AdaptiveSharedDictionary())  # finally works
```

**Fix:** OSMP 2.0 provides Tier 1 functions. Three lines:
```python
from osmp import encode, decode
sal = encode(["H:HR@NODE1>120", "H:CASREP", "M:EVA@*"])
text = decode(sal)
```

### Issue 8: Confusing MCP vs SDK install

**Symptom:** Developer installs `osmp-mcp` thinking it's the SDK, gets an MCP server.
**Fix:** Use `pip install osmp` for the SDK. Use `pip install osmp-mcp` only if you need the MCP server for Claude Desktop, Cursor, or other MCP clients. See the root README for the four install paths.

---

## What is NOT an OSMP issue

The following errors from the sovereign node build are upstream dependencies, not OSMP bugs:

- Termux pkg failures (mirror issues, outdated package lists)
- Rust compiler installation on Android
- PowerInfer/llama.cpp CMake configuration
- npm global package path on Termux
- LoRa radio firmware flashing (Meshtastic, Heltec T114)

OSMP itself has zero dependencies beyond Python standard library. The optional `zstandard` dependency is only needed for D:PACK corpus compression.
