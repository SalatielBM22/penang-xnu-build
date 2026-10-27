#!/usr/bin/env bash
# Records the build host and toolchain identity (macOS runner). Output: key=value lines.
set -uo pipefail
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "os=$(sw_vers -productName 2>/dev/null) $(sw_vers -productVersion 2>/dev/null) ($(sw_vers -buildVersion 2>/dev/null))"
echo "hw_model=$(sysctl -n hw.model 2>/dev/null)"
echo "cpu=$(sysctl -n machdep.cpu.brand_string 2>/dev/null)"
echo "ncpu=$(sysctl -n hw.ncpu 2>/dev/null)"
echo "memsize_bytes=$(sysctl -n hw.memsize 2>/dev/null)"
echo "xcode_path=$(xcode-select -p 2>/dev/null)"
echo "xcode_version=$(xcodebuild -version 2>/dev/null | tr '\n' ' ')"
echo "clang=$(xcrun clang --version 2>/dev/null | head -1)"
echo "macos_sdk=$(xcrun --sdk macosx --show-sdk-version 2>/dev/null)"
