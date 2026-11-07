/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _LINUX_KPROFILES_H
#define _LINUX_KPROFILES_H

#include <linux/kconfig.h>
#include <linux/notifier.h>

#if IS_REACHABLE(CONFIG_KPROFILES)
int kp_active_mode(void);
int kp_max_freq_ratio(void);
void kp_set_mode(unsigned int level);
void kp_set_mode_rollback(unsigned int level, unsigned int duration_ms);
int kp_notifier_register_client(struct notifier_block *nb);
int kp_notifier_unregister_client(struct notifier_block *nb);
#else
static inline int kp_active_mode(void) { return 2; }
static inline int kp_notifier_register_client(struct notifier_block *nb) { return 0; }
static inline int kp_notifier_unregister_client(struct notifier_block *nb) { return 0; }
#endif

#endif
