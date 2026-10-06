// SPDX-License-Identifier: GPL-2.0
#include <linux/fs.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>
#include <linux/utsname.h>
#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME
#include <linux/susfs.h>
DECLARE_STATIC_KEY_FALSE(susfs_is_uname_spoof_buffer_set);
extern void susfs_spoof_uname(struct new_utsname* tmp);
#endif

static int version_proc_show(struct seq_file *m, void *v)
{
#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME
	struct new_utsname tmp;

	down_read(&uts_sem);
	memcpy(&tmp, utsname(), sizeof(tmp));
	if (static_branch_unlikely(&susfs_is_uname_spoof_buffer_set))
		susfs_spoof_uname(&tmp);
	up_read(&uts_sem);

	seq_printf(m, linux_proc_banner,
		tmp.sysname,
		tmp.release,
		tmp.version);
#else
	seq_printf(m, linux_proc_banner,
		utsname()->sysname,
		utsname()->release,
		utsname()->version);
#endif
	return 0;
}

static int __init proc_version_init(void)
{
	proc_create_single("version", 0, NULL, version_proc_show);
	return 0;
}
fs_initcall(proc_version_init);
