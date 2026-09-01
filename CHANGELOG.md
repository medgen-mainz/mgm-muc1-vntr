# Changelog

## [0.3.0](https://github.com/medgen-mainz/mgm-muc1-vntr/compare/v0.2.0...v0.3.0) (2026-09-01)


### Features

* add --json-output for the machine-readable SRS result ([#49](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/49)) ([24635fa](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/24635faa6fd66ab67b5d61505a50b4a72a80f5e5))

## [0.2.0](https://github.com/medgen-mainz/mgm-muc1-vntr/compare/v0.1.0...v0.2.0) (2026-08-31)


### Features

* add LRS analysis module ([#4](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/4)) ([dfd7246](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/dfd724692debbef84069c427fb819171411510a4))
* port over SRS analysis ([#2](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/2)) ([15a70ae](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/15a70ae41d5913d65f9168a9949e2d75900a427c))
* write SRS pileup SVG ([#3](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/3)) ([b05c98b](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/b05c98b08309c4ecf6695cd5d6241ce9a9fdf5b5))


### Bug Fixes

* fold header line lengths into the pileup SVG canvas width ([#39](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/39)) ([1ba1c63](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/1ba1c63bf20dd9994074b12164e991b59e44728d))
* name the empty short read result when long read analysis is skipped ([#31](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/31)) ([78b1ca5](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/78b1ca5d9c834bef033ee65e6bbd6bbfb992213f))
* resolve sys.stdout per call in the short read print helpers ([#32](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/32)) ([19f9960](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/19f9960ebdddc82efbc6730a6af1064224a32439))


### Reverts

* rename back to mgm-muc1-vntr ([#6](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/6)) ([4abc2ab](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/4abc2abf68471c898557457d00327e727d0f7f39))


### Documentation

* add CLAUDE.md with the shared agent instructions that apply here ([#13](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/13)) ([6482896](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/6482896553619accdb81393527fa5d1a45902a8f))
* add the worktree conventions and the LFS check to CLAUDE.md ([#34](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/34)) ([6c4e5af](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/6c4e5afd72195c0db3d852c2bbccc060434a574b))
* record that every fetched long read is reported for inspection ([#30](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/30)) ([d213344](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/d213344f9bd1e019da49f9014a57f1a475a4eefc))
* refurbish the README with worked examples on the committed fixtures ([#43](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/43)) ([fdff096](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/fdff096b4159620c8ca78ca55feb83a525e07175))
* require terse commit messages, PR bodies and issue bodies ([#21](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/21)) ([de5105d](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/de5105de881440da0af430f09769284d274fc90f))

## 0.1.0 (2026-08-31)


### Features

* add LRS analysis module ([#4](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/4)) ([dfd7246](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/dfd724692debbef84069c427fb819171411510a4))
* port over SRS analysis ([#2](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/2)) ([15a70ae](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/15a70ae41d5913d65f9168a9949e2d75900a427c))
* write SRS pileup SVG ([#3](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/3)) ([b05c98b](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/b05c98b08309c4ecf6695cd5d6241ce9a9fdf5b5))


### Reverts

* rename back to mgm-muc1-vntr ([#6](https://github.com/medgen-mainz/mgm-muc1-vntr/issues/6)) ([4abc2ab](https://github.com/medgen-mainz/mgm-muc1-vntr/commit/4abc2abf68471c898557457d00327e727d0f7f39))
