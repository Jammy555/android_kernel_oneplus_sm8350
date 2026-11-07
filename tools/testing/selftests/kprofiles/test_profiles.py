#!/usr/bin/env python3
"""Host regressions for profile policy selection and WALT reference ownership."""
import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]


def function(path, name):
    source = (ROOT / path).read_text()
    match = re.search(r"^\w[^;{}]*\b" + name + r"\([^;{}]*\)\s*\{", source, re.M)
    assert match, name
    start = match.end() - 1
    depth = 1
    end = start + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def run(source):
    with tempfile.TemporaryDirectory(prefix="kprofiles-test-") as tmp:
        path = pathlib.Path(tmp) / "test.c"
        path.write_text(source)
        binary = pathlib.Path(tmp) / "test"
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Werror", str(path),
                        "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


def test_walt_references():
    body = function("kernel/sched/walt/cpu-boost.c", "update_policy_online")
    run(r'''
#include <assert.h>
#include <stdio.h>
struct cpumask { unsigned bits; } mask = {7};
static struct cpumask *cpu_online_mask = &mask;
struct cpufreq_policy { struct cpumask *related_cpus; int refs; };
static struct cpumask related[] = {{3}, {4}};
static struct cpufreq_policy policies[] = {{&related[0], 0}, {&related[1], 0}};
static int locks, missing, updates;
#define for_each_cpu(i, m) for (i = 0; i < 3; i++) if ((m)->bits & (1U << i))
#define pr_err(...) ((void)0)
static void get_online_cpus(void) { ++locks; }
static void put_online_cpus(void) { --locks; }
static void cpumask_andnot(struct cpumask *d, struct cpumask *a, struct cpumask *b)
{ d->bits = a->bits & ~b->bits; }
static struct cpufreq_policy *cpufreq_cpu_get(unsigned cpu) {
    struct cpufreq_policy *p = &policies[cpu == 2];
    if (missing && cpu == 0) return NULL;
    ++p->refs;
    return p;
}
static __attribute__((unused)) void cpufreq_cpu_put(struct cpufreq_policy *p) { --p->refs; }
static void boost_adjust_notify(struct cpufreq_policy *p) { (void)p; ++updates; }
static void update_policy_online(void)
''' + body + r'''
int main(void) {
    update_policy_online();
    assert(locks == 0 && policies[0].refs == 0 && policies[1].refs == 0);
    assert(updates == 2);
    missing = 1;
    update_policy_online();
    assert(locks == 0 && policies[0].refs == 0 && policies[1].refs == 0);
    puts("WALT: shared policies and missing-policy cleanup passed");
}
''')


def test_ceilings():
    active = function("drivers/misc/kprofiles/main.c", "kp_active_mode")
    ceiling = function("drivers/misc/kprofiles/main.c", "kp_policy_ceiling")
    event = function("drivers/misc/kprofiles/main.c", "kp_policy_event")
    changed = function("drivers/misc/kprofiles/main.c", "kp_trigger_mode_change_event")
    source = (ROOT / "drivers/misc/kprofiles/main.c").read_text()
    state = re.search(r"struct kp_policy \{.*?\n\};", source, re.S).group()
    run(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <limits.h>
#include <stddef.h>
#include <stdlib.h>
#include <errno.h>
typedef uint64_t u64;
#define READ_ONCE(x) (x)
#define FREQ_QOS_MAX_DEFAULT_VALUE INT_MAX
#define FREQ_QOS_MAX 1
#define CPUFREQ_CREATE_POLICY 1
#define CPUFREQ_REMOVE_POLICY 2
#define GFP_KERNEL 0
#define struct_size(p, m, n) (sizeof(*(p)) + sizeof((p)->m[0]) * (n))
#define pr_err(...) ((void)0)
#define max(a,b) ((a) > (b) ? (a) : (b))
struct list_head { struct list_head *next, *prev; };
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - offsetof(type, member)))
#define list_entry(ptr, type, member) container_of(ptr, type, member)
#define list_for_each_entry(p, h, m) \
    for (p = list_entry((h)->next, __typeof__(*p), m); &(p)->m != (h); \
         p = list_entry((p)->m.next, __typeof__(*p), m))
#define list_for_each_entry_safe(p, t, h, m) \
    for (p = list_entry((h)->next, __typeof__(*p), m), \
         t = list_entry((p)->m.next, __typeof__(*p), m); &(p)->m != (h); \
         p = t, t = list_entry((t)->m.next, __typeof__(*t), m))
static struct list_head kp_policies = {&kp_policies, &kp_policies};
static void list_add_tail(struct list_head *n, struct list_head *h) {
    n->prev = h->prev; n->next = h; h->prev->next = n; h->prev = n;
}
static void list_del(struct list_head *n) { n->prev->next = n->next; n->next->prev = n->prev; }
static int kp_policy_lock, allocations, requests, fail_alloc, fail_request, notices;
static int kp_mode_notifier, KP_MODE_CHANGE;
struct notifier_block { int unused; };
struct freq_qos_request { int prio, active; };
static void mutex_lock(int *l) { assert(!*l); ++*l; }
static void mutex_unlock(int *l) { assert(*l); --*l; }
static void *kzalloc(size_t n, int flags) {
    (void)flags; if (fail_alloc) return NULL; ++allocations; return calloc(1, n);
}
static void kfree(void *p) { assert(allocations > 0); --allocations; free(p); }
static int freq_qos_add_request(int *c, struct freq_qos_request *r, int t, unsigned v) {
    (void)c; (void)t; if (fail_request) return -EIO;
    assert(!r->active); r->active = 1; r->prio = v; ++requests; return 0;
}
static int freq_qos_update_request(struct freq_qos_request *r, unsigned v) {
    assert(r->active); r->prio = v; return 0;
}
static void freq_qos_remove_request(struct freq_qos_request *r) {
    assert(r->active); r->active = 0; --requests;
}
static int notifier_from_errno(int err) { return err; }
static void blocking_notifier_call_chain(int *n, int e, void *v) {
    (void)n; (void)e; (void)v; ++notices;
}
static unsigned kp_mode = 2, kp_override_mode, ratio = 78;
static bool kp_override;
static int kp_active_mode(void)
''' + active + r'''
static int kp_max_freq_ratio(void) { return ratio; }
struct cpufreq_frequency_table { unsigned frequency; };
struct cpufreq_policy {
    struct { unsigned min_freq, max_freq; } cpuinfo;
    struct cpufreq_frequency_table *freq_table;
    int constraints; unsigned cpu;
};
#define cpufreq_for_each_valid_entry(p,t) for (p = t; p->frequency; p++) if (p->frequency != UINT_MAX)
''' + state + r'''
static unsigned kp_policy_ceiling(struct kp_policy *p)
''' + ceiling + r'''
static int kp_policy_event(struct notifier_block *nb, unsigned long event, void *data)
''' + event + r'''
static void kp_trigger_mode_change_event(void)
''' + changed + r'''
int main(void) {
    struct cpufreq_frequency_table ascending[] = {{300}, {UINT_MAX}, {600}, {900}, {1200}, {0}};
    struct cpufreq_frequency_table descending[] = {{1200}, {900}, {600}, {300}, {0}};
    struct cpufreq_policy policy = {.cpuinfo={300, 1200}, .freq_table=ascending};
    assert(kp_policy_event(NULL, CPUFREQ_CREATE_POLICY, &policy) == 0);
    struct kp_policy *p = list_entry(kp_policies.next, struct kp_policy, node);
    assert(p->count == 4 && p->ceiling.prio == INT_MAX && requests == 1);
    kp_mode = 1;
    kp_trigger_mode_change_event();
    assert(p->ceiling.prio == 900);
    /* Driver table lifetime ends before the REMOVE notification. */
    policy.freq_table = (void *)1;
    kp_trigger_mode_change_event();
    assert(p->ceiling.prio == 900);
    ratio = 10;
    assert(kp_policy_ceiling(p) == 300);
    ratio = 100;
    assert(kp_policy_ceiling(p) == 1200);
    assert(kp_policy_event(NULL, CPUFREQ_REMOVE_POLICY, &policy) == 0);
    assert(requests == 0 && allocations == 0);
    ratio = 78; policy.freq_table = descending;
    assert(kp_policy_event(NULL, CPUFREQ_CREATE_POLICY, &policy) == 0);
    p = list_entry(kp_policies.next, struct kp_policy, node);
    assert(p->ceiling.prio == 900);
    assert(kp_policy_event(NULL, CPUFREQ_REMOVE_POLICY, &policy) == 0);
    policy.freq_table = NULL;
    assert(kp_policy_event(NULL, CPUFREQ_CREATE_POLICY, &policy) == 0);
    p = list_entry(kp_policies.next, struct kp_policy, node);
    assert(p->ceiling.prio == 936);
    kp_override = true; kp_override_mode = 3;
    assert(kp_active_mode() == 1);
    kp_mode = 2; kp_override_mode = 0;
    assert(kp_active_mode() == 2);
    kp_override_mode = 3;
    assert(kp_policy_ceiling(p) == INT_MAX);
    assert(kp_policy_event(NULL, CPUFREQ_REMOVE_POLICY, &policy) == 0);
    assert(kp_policy_event(NULL, CPUFREQ_REMOVE_POLICY, &policy) == 0);
    fail_alloc = 1;
    assert(kp_policy_event(NULL, CPUFREQ_CREATE_POLICY, &policy) == -ENOMEM);
    fail_alloc = 0; fail_request = 1;
    assert(kp_policy_event(NULL, CPUFREQ_CREATE_POLICY, &policy) == -EIO);
    assert(!kp_policy_lock && !requests && !allocations && notices == 2);
    assert(kp_policies.next == &kp_policies);
    puts("Kprofiles: cached tables, teardown, allocation failures, ratios and Saver override protection passed");
}
''')


def test_cpu_profile_requests():
    body = function("drivers/cpufreq/cpufreq.c", "store_profile_freq")
    run(r'''
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <limits.h>
#include <sys/types.h>
#define READ_ONCE(x) (x)
#define FREQ_QOS_MIN_DEFAULT_VALUE 0
#define FREQ_QOS_MAX_DEFAULT_VALUE INT_MAX
enum freq_qos_req_type { FREQ_QOS_MIN, FREQ_QOS_MAX };
struct freq_qos_request { struct { int prio; } pnode; };
struct cpufreq_policy {
    struct { unsigned min_freq, max_freq; } cpuinfo;
    struct freq_qos_request profile_min_freq_req, profile_max_freq_req;
};
static int fail;
static int kstrtouint(const char *s, int base, unsigned *out) {
    char *end; unsigned long v = strtoul(s, &end, base);
    if (!*s || *s == '-' || *end || v > UINT_MAX) return -EINVAL;
    *out = v; return 0;
}
static int freq_qos_update_request(struct freq_qos_request *r, unsigned v) {
    if (fail) return -EIO;
    r->pnode.prio = v; return 0;
}
static ssize_t store_profile_freq(struct cpufreq_policy *policy, const char *buf,
        size_t count, enum freq_qos_req_type type)
''' + body + r'''
int main(void) {
    struct cpufreq_policy p = {{300, 2000}, {{0}}, {{INT_MAX}}};
    assert(store_profile_freq(&p, "900", 3, FREQ_QOS_MAX) == 3);
    assert(store_profile_freq(&p, "1200", 4, FREQ_QOS_MIN) == -EINVAL);
    assert(p.profile_min_freq_req.pnode.prio == 0);
    assert(store_profile_freq(&p, "600", 3, FREQ_QOS_MIN) == 3);
    assert(store_profile_freq(&p, "300", 3, FREQ_QOS_MAX) == -EINVAL);
    assert(store_profile_freq(&p, "2001", 4, FREQ_QOS_MAX) == -EINVAL);
    assert(store_profile_freq(&p, "299", 3, FREQ_QOS_MIN) == -EINVAL);
    assert(store_profile_freq(&p, "-1", 2, FREQ_QOS_MIN) == -EINVAL);
    assert(store_profile_freq(&p, "x", 1, FREQ_QOS_MIN) == -EINVAL);
    assert(store_profile_freq(&p, "0", 1, FREQ_QOS_MAX) == 1);
    assert(p.profile_max_freq_req.pnode.prio == INT_MAX);
    fail = 1;
    assert(store_profile_freq(&p, "900", 3, FREQ_QOS_MIN) == -EIO);
    assert(p.profile_min_freq_req.pnode.prio == 600);
    puts("CPU profiles: invalid ranges, min/max ordering, release and failed updates passed");
}
''')


def test_devfreq_limits():
    body = function("drivers/devfreq/devfreq.c", "update_devfreq")
    store = function("drivers/devfreq/devfreq.c", "profile_freq_store")
    run(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <limits.h>
#include <sys/types.h>
typedef unsigned u32;
#define min(a,b) ((a) < (b) ? (a) : (b))
#define max(a,b) ((a) > (b) ? (a) : (b))
#define WARN(...) ((void)0)
#define DEVFREQ_FLAG_LEAST_UPPER_BOUND 1
struct devfreq;
struct governor { int (*get_target_freq)(struct devfreq *, unsigned long *); };
struct profile { unsigned max_state; unsigned long *freq_table; };
struct devfreq {
    int lock; struct governor *governor; struct profile *profile;
    unsigned long min_freq, max_freq, scaling_min_freq, scaling_max_freq;
    unsigned long boost_min_freq, profile_min_freq, profile_max_freq;
    bool max_boost;
};
static unsigned long requested, actual;
static int fail, events;
static int mutex_is_locked(int *lock) { return *lock; }
static void mutex_lock(int *lock) { assert(!*lock); *lock = 1; }
static void mutex_unlock(int *lock) { assert(*lock); *lock = 0; }
static void event_mutex_lock(struct devfreq *df) { (void)df; ++events; }
static void event_mutex_unlock(struct devfreq *df) { (void)df; --events; }
static int target(struct devfreq *df, unsigned long *out) { (void)df; *out = requested; return 0; }
static int devfreq_set_target(struct devfreq *df, unsigned long f, u32 flags) {
    (void)df; (void)flags; if (fail) return -EIO; actual = f; return 0;
}
static int kstrtoul(const char *s, int base, unsigned long *out) {
    char *end; *out = strtoul(s, &end, base);
    return !*s || *s == '-' || *end ? -EINVAL : 0;
}
static int update_devfreq(struct devfreq *devfreq)
''' + body + r'''
static ssize_t profile_freq_store(struct devfreq *df, const char *buf, size_t count, bool minimum)
''' + store + r'''
int main(void) {
    unsigned long table[] = {1200, 900, 600, 300};
    struct profile profile = {4, table}; struct governor governor = {target};
    struct devfreq df = {.lock=1, .governor=&governor, .profile=&profile,
        .min_freq=300, .max_freq=1200, .scaling_min_freq=300, .scaling_max_freq=1200};
    requested = 300; df.boost_min_freq = 900;
    assert(update_devfreq(&df) == 0 && actual == 900 && df.min_freq == 300);
    df.profile_max_freq = 600;
    assert(update_devfreq(&df) == 0 && actual == 600);
    df.scaling_max_freq = 450; df.max_boost = true;
    assert(update_devfreq(&df) == 0 && actual == 450);
    df.profile_max_freq = 0; df.max_boost = false; df.boost_min_freq = 0;
    assert(update_devfreq(&df) == 0 && actual == 300);
    df.lock = 0;
    assert(profile_freq_store(&df, "299", 3, true) == -EINVAL);
    assert(profile_freq_store(&df, "1201", 4, false) == -EINVAL);
    assert(profile_freq_store(&df, "600", 3, false) == 3);
    assert(profile_freq_store(&df, "900", 3, true) == -EINVAL);
    assert(profile_freq_store(&df, "300", 3, true) == 3);
    fail = 1;
    assert(profile_freq_store(&df, "900", 3, false) == -EIO);
    assert(df.profile_max_freq == 600 && df.lock == 0 && events == 0);
    fail = 0;
    assert(profile_freq_store(&df, "0", 1, false) == 1 && df.profile_max_freq == 0);
    puts("Devfreq: independent boost/profile limits, thermal priority and failed-write rollback passed");
}
''')


if __name__ == "__main__":
    test_walt_references()
    test_ceilings()
    test_cpu_profile_requests()
    test_devfreq_limits()
