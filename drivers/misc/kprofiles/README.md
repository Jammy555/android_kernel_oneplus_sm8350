# Kprofiles on SM8350

This fork integrates Kprofiles with PowerTools, WALT input boost, schedutil,
Adreno and DDR devfreq. It is built into the kernel when `CONFIG_KPROFILES=y`
and requires CPU frequency support.

| Kernel mode | PowerTools mode | Behaviour |
| --- | --- | --- |
| 1 | 0 — Power Save | Apply the CPU ceiling and suppress optional boosts |
| 2 | 1 — Normal | Restore adaptive governors and normal boost policy |
| 3 | 2 — Performance | Allow short boosts within hardware limits |
| 0 | 1 — Normal | Compatibility alias for kernel mode 2 |

The default is Normal. There is no automatic screen-off mode switch or
`auto_kp` parameter in this fork. Low-power idle remains available in every
PowerTools profile.

## CPU limits

`/sys/kernel/kprofiles/kp_mode` selects the mode.
`/sys/kernel/kprofiles/kp_max_freq_ratio` accepts 10–100, with a default of 78.
Power Save selects the highest valid frequency at or below that percentage
of each policy's hardware maximum, never below its hardware minimum.

Each policy gets an independent frequency-QoS maximum request. Changes to mode
or ratio update existing requests immediately; policy removal releases them.
The valid frequency table is copied at policy creation so updates cannot access
a table released by the cpufreq driver. Thermal constraints remain independent.

PowerTools manual limits use `scaling_profile_min_freq` and
`scaling_profile_max_freq` under each cpufreq policy. Zero releases that request.
These nodes do not overwrite the generic `scaling_min_freq`/`scaling_max_freq`
requests managed by Power HAL. Invalid bounds and inverted profile ranges fail.
Read the generic nodes to inspect the effective, combined limits.

## Boost integration

The configured CPU input booster is WALT's `kernel/sched/walt/cpu-boost.c`, with
one QoS request per shared CPU policy. Power Save cancels outstanding boosts and
blocks subsequent touch events. Schedutil keeps utilization/window accounting
while suppressing its optional I/O and WALT boost adjustments.

Adreno suppresses touch and maximum-frequency wakeup boosts in Power Save.
DDR boost requests have a separate minimum; they do not replace Power HAL's
minimum request. Screen-off and Power Save suppress DDR boosts. The devfreq
`profile_min_freq`/`profile_max_freq` nodes provide independent manual requests,
where zero releases the limit and thermal maximums take precedence.

PowerTools also coordinates Power HAL hints and device init settings. Those
userspace changes must be built together with this kernel interface.

## Kernel API

Include `<linux/kprofiles.h>` instead of declaring functions at each caller.

- `kp_active_mode()` reads the effective mode without sleeping. It returns
  Normal when Kprofiles is not configured.
- `kp_set_mode(level)` changes the user mode in a sleepable context.
- `kp_set_mode_rollback(level, duration_ms)` applies a temporary mode and sleeps
  before restoring it. A temporary boost cannot override user-selected Saver.
- `kp_notifier_register_client()` and `kp_notifier_unregister_client()` manage
  the blocking mode-change notifier. Callbacks run in a sleepable context.

## Checks

Run `python3 tools/testing/selftests/kprofiles/test_profiles.py` from the kernel
root. The host checks cover policy references, table lifetime and bounds, failed
requests, independent devfreq limits and thermal priority. A configured kernel
build and device tests of hotplug, profile transitions and idle are still needed.

Based on [Kprofiles](https://github.com/beakthoven/Kprofiles) by Dakkshesh, with
Kprofiles Manager maintained by Cyberknight777. Licensed under GPL-2.0.
