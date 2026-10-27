# Legal notes

Not legal advice. This file states what the repository does and does not contain and distribute.

## Contained in this repository
- Workflows and scripts written for this project (MIT, see `LICENSE`).
- Future patches to Apple's public XNU sources, published under the Apple Public Source License 2.0
  (APSL-2.0) as the license of the files they modify requires, with upstream notices kept.

## Never contained in this repository
- Any Apple binary, firmware, IPSW, disk image, cryptex, dyld shared cache, font or artwork.
- Any decryption key for Apple software.
- Any Qualcomm/Motorola firmware, device tree dump, partition image or device-specific secret.
- Credentials, tokens or personal data.

## Build inputs used at run time (not redistributed)
- Apple open-source projects fetched from `github.com/apple-oss-distributions` (APSL-2.0 and others as marked).
- The Xcode toolchain preinstalled on GitHub-hosted macOS runners (Apple hardware).
- A Kernel Debug Kit installed on the runner only after Apple signature verification; it is not uploaded.

## Build outputs
Workflow artifacts are kernels built from APSL-2.0 sources; the exact source is the pinned public tag plus the
patches in this repository. Artifacts expire after 14 days.

"Apple", "XNU", "iOS", "iPadOS" and "iPhone" are trademarks of Apple Inc., named only to describe what the code
works with. If you believe something here infringes your rights, open an issue and it will be removed.
