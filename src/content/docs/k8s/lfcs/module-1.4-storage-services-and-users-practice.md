---
revision_pending: false
title: "LFCS Storage, Services, and Users Practice"
slug: k8s/lfcs/module-1.4-storage-services-and-users-practice
sidebar:
  order: 104
---

> **LFCS Track** | Complexity: `[COMPLEX]` | Time: 50-70 min for an integrated Linux administration practice module covering identity, storage, services, limits, and verification.

**Reading Time**: 50-70 minutes, with enough hands-on depth to pause between sections, run the commands in a disposable lab, and compare evidence after each change.

## Prerequisites

Before starting this module, make sure the earlier LFCS practice modules feel comfortable enough that you can navigate files, inspect processes, and troubleshoot networking without stopping this storage and identity workflow.
- **Required**: [LFCS Exam Strategy and Workflow](../module-1.1-exam-strategy-and-workflow/)
- **Required**: [LFCS Essential Commands Practice](../module-1.2-essential-commands-practice/)
- **Required**: [LFCS Running Systems and Networking Practice](../module-1.3-running-systems-and-networking-practice/)
- **Helpful**: [Module 1.4: Users & Permissions](/linux/foundations/system-essentials/module-1.4-users-permissions/)
- **Helpful**: [Module 8.1: Storage Management](/linux/operations/module-8.1-storage-management/)

## Learning Outcomes

After this module, you will be able to perform and verify the administrative outcomes below in a lab host without relying on temporary shell state or broad permission shortcuts.
- **Implement** user, group, sudo, ownership, and permission changes that are deliberate, reversible, and easy to verify.
- **Diagnose** resource-limit and PAM-session behavior by distinguishing shell limits, persistent policy, and login-time enforcement.
- **Design** persistent storage changes with filesystem, UUID, `/etc/fstab`, and LVM workflows that remain valid after reboot.
- **Evaluate** service lifecycle state with package installation, systemd enablement, restart behavior, and daemon-reload verification.
- **Debug** integrated LFCS practice scenarios where identity, storage, and service configuration interact on the same host.

## Why This Module Matters

Hypothetical scenario: you are handed a freshly installed Linux server during an LFCS practice session and told to prepare it for a small internal application. The application needs two operators with shared write access, a persistent data mount, a larger logical volume than the default disk layout provides, a stricter open-file limit for one service account, and a web service that must start after reboot. None of those changes is exotic, yet every one of them can break the host if you skip verification or confuse a temporary shell state with persistent configuration.

That is why this module treats users, storage, services, and PAM as one operating routine instead of four unrelated command lists. On a real machine, a service often fails because its user cannot read a file, its mount never came back after reboot, its process limit is lower than expected, or systemd is still using an old unit definition. The LFCS exam uses the same pattern: it rarely rewards memorizing a single command, but it consistently rewards making a change, proving the change happened, and recognizing which layer owns the failure.

The goal is not to turn you into a storage architect or PAM specialist in one sitting. The goal is to make the common administrative path reliable under time pressure, using Kubernetes-era Linux expectations where systemd is the service manager, persistent mounts use stable identifiers, and Kubernetes 1.35+ worker nodes still depend on correct Linux users, filesystems, and services underneath the container layer. You will practice each area in isolation first, then connect them in a hands-on exercise that feels like the exam: make the host match the requested state, verify each layer, and leave no fragile temporary fix behind.

## Identity, Ownership, and Sudo as a Verification Loop

User management starts with identity, but the exam task usually cares about access. Creating a user is only useful if the user lands in the expected primary and supplementary groups, can start a fresh login shell, and can reach the files or commands the task requires. Treat every identity change as a small loop: create or modify the account, inspect the account database, test effective membership, then test the resource the user is supposed to access. This loop keeps you from mistaking a successful command exit code for a successful administrative outcome.

The basic commands are familiar, but their sequencing matters. `useradd` creates an entry, `passwd` sets authentication material, `groupadd` creates a shared administrative boundary, and `usermod -aG` adds supplementary membership without replacing the existing list. The `-a` flag is not decoration; without it, `usermod -G` can remove every supplementary group not named in the command. That is a classic way to break sudo access while trying to grant a different access path.

```bash
useradd alice
passwd alice
usermod -aG sudo alice
groupadd ops
getent passwd alice
getent group ops
id alice
sudo -l -U alice
visudo
```

After running those commands, read the output as evidence rather than noise. `getent passwd alice` confirms the account database can resolve the user through the configured name service, which matters on systems that use local files, LDAP, or another NSS source. `getent group ops` confirms the group exists through the same resolution path. `id alice` shows effective group membership as the system sees it, and `sudo -l -U alice` tests sudo policy for that user rather than assuming the group name is sufficient on every distribution.

Ownership and permissions are where identity becomes operational. A file mode is only meaningful when paired with owner and group, and a directory mode is only meaningful when you remember that directory execute means traversal, not program execution. If a user cannot open `/srv/app/config.yml`, you need to ask two questions before changing anything: can the user traverse every parent directory, and does the final file grant read permission through owner, group, ACL, or other mode bits? Guessing between `chmod` and `chown` is slower than inspecting the path carefully.

```bash
chown alice:ops /srv/app/config.yml
chmod 640 /srv/app/config.yml
chmod u+rwx,g+rx,o-r /srv/app
setfacl -m u:alice:rw /srv/app/shared.txt
```

The first line changes the owner and group, while the next two lines express the access policy in mode bits. A `640` file lets the owner read and write, lets the group read, and grants no access to others. A directory with `u+rwx,g+rx,o-r` lets the owner manage entries, lets the group list and traverse, and removes read permission from everyone else, though you should also think about execute for traversal when you harden directories. The ACL example is useful when one named user needs an exception without changing the group model for everyone.

Pause and predict: if `alice` is added to `ops` while she already has a shell open, what do you expect `id` inside that old shell to show? Most systems do not rewrite the supplementary groups of an already-running login session just because `/etc/group` changed. That means your verification should use a fresh login shell, a new SSH session, or a command such as `su - alice -c 'id'` when you need to prove the new membership is actually effective.

The most reliable access-debugging habit is to walk the path from the user outward. Confirm the user exists, confirm group membership, check each directory in the path, check the final file, and only then change the smallest thing that explains the failure. If the group is wrong, fix membership or ownership. If the mode is wrong, fix mode bits. If only one exception is needed, consider an ACL and verify it with the ACL-aware tools on the target distribution. The LFCS scoring style rewards that discipline because it leaves the system in a coherent state instead of a permissive state that merely happens to pass one immediate test.

## Resource Limits and PAM Session Enforcement

Resource limits look deceptively simple because `ulimit` prints numbers quickly. The trap is that `ulimit` shows the current shell's effective limits, while persistent policy lives in files that are applied during session setup. If you change `/etc/security/limits.conf` or a drop-in under `/etc/security/limits.d/`, the shell already in front of you will not magically inherit the new values. You need a fresh login session that passes through PAM, and you need `pam_limits.so` in the relevant session stack.

The soft-versus-hard distinction is central. A soft limit is the current effective value that a process receives, and a user may raise it up to the hard limit if policy allows. A hard limit is the ceiling, and raising it generally requires root. For LFCS work, the practical targets are usually open files, process count, maximum file size, core dump size, or address space. Older memory-related fields such as RSS can appear in historical references, but they are not the best modern control point for a clear exam answer.

```bash
ulimit -a                   # all soft limits for current shell
ulimit -Ha                  # all hard limits
ulimit -n                   # soft open-file limit
ulimit -Hn                  # hard open-file limit
su - alice -c 'ulimit -a'  # check limits for another user
```

The command block above is deliberately split between current-shell inspection and another user's fresh login context. `ulimit -n` answers what the current shell can use for open files right now, while `su - alice -c 'ulimit -a'` asks what a login session for `alice` receives. That difference matters when you are troubleshooting a service account or validating an LFCS task after editing persistent policy. Before running this, what output do you expect to change after editing a limits drop-in, and which shell do you expect to stay the same?

| Item | `ulimit` flag | `limits.conf` keyword |
|------|----------------|-----------------------|
| Open files | `-n` | `nofile` |
| Max processes | `-u` | `nproc` |
| Max file size | `-f` | `fsize` |
| Core dump size | `-c` | `core` |
| Address space | `-v` | `as` |

The table gives you a translation layer between interactive inspection and persistent configuration. In an exam, you may be asked to set a limit by name, then verify it using a shell built-in. If the prompt says open files, connect `nofile` to `ulimit -n`. If it says maximum processes, connect `nproc` to `ulimit -u`. When you can translate both directions, you can move from task wording to configuration and back to verification without rummaging through memory under pressure.

Persistent limits can live in `/etc/security/limits.conf`, but a drop-in is often cleaner because it scopes the change and is easier to remove during practice. The format is consistent: domain, type, item, value. A domain can be a specific user, a group prefixed with `@`, or `*` for the default policy. You should set both soft and hard values when the task demands a bounded range, because setting only one can leave behavior ambiguous.

```bash
# Format: <domain> <type> <item> <value>
# Example: set alice's open-file limits
alice    soft    nofile    4096
alice    hard    nofile    8192

# Set for a group (prefix with @)
@ops     soft    nproc     2048
@ops     hard    nproc     4096

# Set for all users
*        soft    nofile    1024
*        hard    nofile    65536
```

The global `*` entry is powerful and should be treated carefully. It can be the right answer when the task explicitly asks for a default applied broadly, but it is the wrong answer when only one account or group needs the change. Prefer the narrowest domain that satisfies the requirement, then verify with the same domain in mind. If the task names `alice`, test `alice`; if it names the `ops` group, test a user whose fresh session actually includes that group.

```bash
echo "alice soft nofile 4096" | sudo tee /etc/security/limits.d/90-alice.conf
echo "alice hard nofile 8192" | sudo tee -a /etc/security/limits.d/90-alice.conf
```

The missing bridge between those files and a running process is PAM. Pluggable Authentication Modules are not only about passwords; PAM also runs account, password, and session modules for services such as login, SSH, sudo, and noninteractive sessions. The module that reads the limits files is `pam_limits.so`, and it must appear in the session stack that the login path uses. Without that module, the file can be perfectly formatted and still have no effect for the user you are testing.

```text
Login -> PAM stack -> pam_limits.so reads limits.conf -> session gets limits applied
```

That simple flow is the mental model you need for LFCS. The login service invokes a PAM stack, the session phase includes modules that prepare the environment, and `pam_limits.so` applies the configured resource limits to the new session. If you skip the PAM check, you may blame the limit syntax when the real failure is that the login path never consulted the limit policy in the first place.

```bash
grep pam_limits.so /etc/pam.d/common-session
grep pam_limits.so /etc/pam.d/common-session-noninteractive
```

Distribution layout varies, so these paths are most familiar on Debian and Ubuntu family systems. Other systems may keep equivalent stack definitions in service-specific files or profile-managed includes, but the idea is unchanged: find the session stack for the login path you are testing and confirm that the limit module participates. If the prompt gives you a Debian-like environment, `common-session` and `common-session-noninteractive` are natural places to inspect. If it gives you a different layout, use the same reasoning and avoid editing randomly.

| Module | Purpose |
|--------|---------|
| `pam_limits.so` | Enforce resource limits from limits.conf |
| `pam_unix.so` | Standard password authentication |
| `pam_pwquality.so` | Password complexity enforcement |
| `pam_access.so` | Login access control (/etc/security/access.conf) |
| `pam_faildelay.so` | Delay after failed authentication |
| `pam_nologin.so` | Block non-root login when /etc/nologin exists |

PAM configuration reads like a pipeline of decisions, and the control field affects how failures are handled. `required` means the module must succeed, but PAM continues checking other modules before reporting the final result. `requisite` also must succeed, but failure can stop the stack immediately. You do not need deep PAM design for LFCS, yet you do need enough literacy to avoid deleting a required module or placing a session-only module in a password-only context.

```bash
ls /etc/pam.d/                  # per-service PAM configs
cat /etc/pam.d/common-auth      # authentication stack
cat /etc/pam.d/common-session   # session setup stack
cat /etc/pam.d/common-password  # password change rules
cat /etc/pam.d/common-account   # account validation
```

Those files divide authentication, account validation, password changes, and session setup into separate concerns. Password complexity belongs in the password path, not the session path. Login access checks belong in account or auth policy depending on the module and distribution. Resource limits belong in the session path because they shape the process environment that the authenticated user receives after login.

```text
type    control    module-path    [module-arguments]
```

When you read a PAM line, parse it from left to right before making a change. The type tells you when the module runs, the control field tells you how the result influences the stack, the module path identifies the behavior, and optional arguments tune it. That habit prevents a common exam error: finding the right module name, then editing the wrong stack phase because the file was open and looked close enough.

```bash
# Check if pam_pwquality is in the password stack
grep pam_pwquality /etc/pam.d/common-password

# If present, its config is in:
cat /etc/security/pwquality.conf
# minlen = 12
# dcredit = -1    (require at least 1 digit)
# ucredit = -1    (require at least 1 uppercase)
```

The password-quality example is included because it trains the same inspection discipline as limits. First confirm that the module is wired into the stack, then inspect the configuration file that the module reads. Do not assume a package being installed means its policy is active, and do not assume a policy file matters unless the relevant PAM path invokes the module. That separation of package, policy, and enforcement shows up repeatedly in Linux administration.

## Filesystems, Persistent Mounts, and LVM Growth

Storage tasks feel dangerous because they touch durable state, so the safe approach is to slow down at the boundaries. First identify the block device, then create or inspect the filesystem, then mount it, then make the mount persistent, then test the persistent configuration before trusting a reboot. Each step has a verification command, and each verification command answers a different question. `lsblk` shows the device tree, `blkid` shows filesystem identifiers, `findmnt` shows the active mount view, and `df -h` shows usable filesystem capacity from the mounted path.

```bash
lsblk
blkid
# run only ONE of these (choose ext4 OR xfs)
mkfs.ext4 /dev/sdb1
mkfs.xfs /dev/sdb1
mkdir -p /data
mount /dev/sdb1 /data
findmnt /data
```

The formatting commands in that block are intentionally direct because they are powerful. In real work and exam practice, confirm that `/dev/sdb1` is the intended spare device before running `mkfs.ext4` or `mkfs.xfs`; formatting the wrong partition is not a recoverable permission typo. For practice, a loopback file is often safer than a physical spare disk, but the verification pattern stays the same. You should be able to explain which command creates the filesystem and which command merely attaches an existing filesystem to the directory tree.

Persistent mounts should prefer stable identifiers over kernel device names. `/dev/sdb1` may be correct during the current boot, but device names can shift when disks are discovered in a different order. A UUID belongs to the filesystem and remains a better anchor for `/etc/fstab` when the same filesystem should mount consistently. LFCS tasks often care about this exact difference: a mount that works now is incomplete if it disappears or points at the wrong device after reboot.

```bash
UUID=$(blkid -s UUID -o value /dev/sdb1)
echo "UUID=$UUID /data ext4 defaults 0 2" | sudo tee -a /etc/fstab
mount -a
```

The `mount -a` step is the exam-saving step. It asks the system to process `/etc/fstab` entries now, while you can still fix a typo, rather than discovering the problem after boot. If the mount point already has the intended filesystem mounted, you may need to unmount and remount during practice so you are testing the entry rather than a previous manual mount. Either way, the verification path ends with `findmnt /data`, `df -h /data`, and a quick look at the exact line you added.

```text
+----------------------+       +----------------------+       +----------------------+
| Block device         |       | Filesystem identity  |       | Mounted directory    |
| /dev/sdb1            |  -->  | UUID from blkid      |  -->  | /data via /etc/fstab |
+----------------------+       +----------------------+       +----------------------+
```

That diagram is the persistent-mount chain. The block device is where the bytes live, the filesystem identity is what `/etc/fstab` should target, and the mounted directory is the path users and services consume. When a mount fails, locate the broken link in that chain. A missing device is different from a wrong UUID, and both are different from a mount point that lacks the intended permissions for the service user.

LVM adds another layer because plain partitions are rigid once the disk layout is chosen. With LVM, a physical volume contributes capacity to a volume group, and logical volumes are carved from that pool. The tradeoff is extra abstraction: you get easier growth and flexible allocation, but you also need to verify more layers. A correct LVM answer shows the PV, VG, LV, filesystem, mount point, and capacity after each change.

```bash
pvcreate /dev/sdb1
vgcreate vg_data /dev/sdb1
lvcreate -n lv_app -L 10G vg_data
mkfs.ext4 /dev/vg_data/lv_app
mkdir -p /srv/app
mount /dev/vg_data/lv_app /srv/app
```

This path creates a new logical volume and puts a filesystem on it, but the device path is not the whole story. The LV is storage allocation, while the filesystem is the structure that lets Linux store directories and files. You can create an LV and still have nothing mountable until it has a filesystem. You can also create a filesystem and still have no persistent mount until `/etc/fstab` or another system mechanism tells the host where it belongs after boot.

```text
+----------------+     +----------------+     +----------------+     +----------------+
| Physical volume | --> | Volume group   | --> | Logical volume | --> | Filesystem     |
| /dev/sdb1       |     | vg_data        |     | lv_app         |     | ext4 or XFS    |
+----------------+     +----------------+     +----------------+     +----------------+
                                                                     |
                                                                     v
                                                          +----------------------+
                                                          | Mount point /srv/app |
                                                          +----------------------+
```

The diagram shows why LVM troubleshooting should not jump straight to `df`. `df` sees the mounted filesystem, not the entire LVM hierarchy. If `df` is too small after an extension, the LV may not have grown, the filesystem may not have grown, or you may be looking at the wrong mount point. Work down the chain with `pvs`, `vgs`, `lvs`, `lsblk`, `findmnt`, and `df -h` until the layer that did not change becomes obvious.

```bash
lvextend -L +5G /dev/vg_data/lv_app
resize2fs /dev/vg_data/lv_app
lvs
lsblk
df -h /srv/app
```

For ext-family filesystems, `resize2fs` grows the filesystem after the logical volume grows. The important idea is that enlarging the block device is not the same as enlarging the filesystem that sits on it. If you stop after `lvextend`, `lvs` may show the new LV size while `df -h /srv/app` still shows the old filesystem capacity. That mismatch is a diagnostic clue, not a reason to run random commands.

```bash
lvextend -L +5G /dev/vg_data/lv_app
xfs_growfs /srv/app
lvs
df -h /srv/app
```

XFS uses a different growth command and targets the mounted filesystem path. That difference is a common LFCS trap because the LV command looks identical but the filesystem command changes. Which approach would you choose here and why if `findmnt /srv/app` reports `xfs` instead of `ext4`? The right answer is to let the actual filesystem type drive the resize command, then verify capacity from the mount point that applications use.

## Services, Boot Persistence, and Systemd Evidence

Service administration links packages, unit files, running processes, and boot policy. Installing a package puts files on disk, but it does not guarantee the service is running or enabled. Starting a service proves it can run now, but it does not guarantee it will start after reboot. Enabling a service creates boot-time intent, but it does not prove the current process is healthy. LFCS service tasks are usually straightforward, yet they require you to prove all of those layers instead of stopping at the first green-looking command.

```bash
apt update
apt install -y nginx
systemctl enable --now nginx
systemctl status nginx
systemctl is-enabled nginx
systemctl daemon-reload
systemctl restart nginx
```

The `enable --now` form is efficient because it expresses both boot persistence and immediate startup. Still, you should inspect state afterward because a unit can be enabled and failed at the same time. `systemctl status nginx` shows the active state and recent log context, while `systemctl is-enabled nginx` answers whether boot policy is set. If the service fails, read the status output before reinstalling packages or changing permissions; many failures are caused by missing paths, invalid configuration, unavailable ports, or a user that cannot read required files.

`systemctl daemon-reload` matters when unit definitions or drop-ins change because systemd keeps a manager view of unit metadata. Restarting a service without reloading after a unit-file edit can test the old definition, which makes debugging feel inconsistent. The correct sequence after editing a unit or drop-in is reload the manager, restart or reload the service as appropriate, inspect status, and verify the behavior the edit was supposed to change. That sequence is small, but it prevents a lot of false conclusions.

Service failures often connect back to identity and storage. A daemon may start manually as root but fail under systemd because its unit uses a less privileged `User=`. A web server may be enabled correctly but fail because `/srv/app` is not mounted yet or is mounted with permissions that exclude the service account. A process may behave normally in a shell but hit lower limits in its real service environment. When the symptoms cross layers, do not flatten the problem into "systemd is broken"; follow the evidence from unit state to logs, user, path, mount, and limits.

Exercise scenario: you install `nginx`, enable it, and create `/srv/app` on an LVM-backed filesystem, but the service returns a permission error when reading a config file under that path. Start with `systemctl status`, then inspect the unit user, then inspect the mount, ownership, and mode bits. If all of those are correct, check whether a fresh shell for the same user sees the expected group membership and limits. This is the integrated style of troubleshooting LFCS tries to encourage.

## Integrated Exam Workflow

The safest way to work through mixed LFCS tasks is to build a short checklist before typing commands. Identify the requested final state, name the layers involved, choose the smallest change for each layer, and write down the verification command that proves it. That is not bureaucracy; it is how you avoid losing time to hidden assumptions. A task that says "create a shared directory for two operators and ensure the web service starts after reboot" involves users, groups, directory permissions, perhaps mount persistence, and systemd state.

For identity tasks, verify from the user's point of view. For storage tasks, verify from both the device tree and the mounted path. For service tasks, verify both current active state and boot enablement. For resource limits, verify from a fresh login context and confirm the PAM stack if the numbers do not change. These are not separate memorized recipes. They are repeated uses of the same operational question: what layer owns the requested behavior, and what evidence proves that layer is now correct?

The most useful exam habit is to leave every change testable by the next person. A clean `/etc/security/limits.d/90-alice.conf` is easier to inspect than an unmarked edit buried in a long main configuration file. A UUID-based `/etc/fstab` line is easier to trust after reboot than a kernel device name that depends on discovery order. A service that is both active and enabled is easier to defend than a service you started once. A group-based permission model is easier to maintain than a pile of one-off broad modes.

When you are under time pressure, resist broad fixes such as `chmod -R 777`, rewriting a PAM stack from memory, or appending untested `/etc/fstab` lines. Those changes create more uncertainty than they remove. Instead, make one bounded change, verify it, and then move to the next layer. If a later layer fails, your earlier verification becomes useful evidence rather than something you must revisit from scratch.

## Patterns & Anti-Patterns

The strongest pattern for this module is verify-after-each-layer. In storage work, that means you do not wait until the end to discover that the filesystem type was not what you expected. In identity work, it means you do not wait until the service fails to learn that a user never received the intended group membership. In service work, it means you do not mistake an installed package for an enabled and active daemon. This pattern scales because it turns a multi-layer task into a sequence of confirmed states.

Another useful pattern is narrow policy before broad policy. A user-specific limits drop-in is safer than changing the global default when only one user is named. Group ownership is safer than world-writable modes when two operators need shared access. UUID-based mounts are safer than device-name mounts when persistence is part of the requirement. Narrow policy works because it gives exactly the requested subject exactly the required access, which leaves less unintended behavior to debug later.

A third pattern is fresh-context verification. If the change is applied during login, test a fresh login. If the change is applied by systemd, test the systemd service rather than only an interactive shell. If the change is applied through `/etc/fstab`, test `mount -a` rather than only the existing manual mount. This pattern prevents you from validating the wrong context, which is one of the easiest ways to produce a configuration that looks correct in practice but fails under exam grading.

The most common anti-pattern is permission widening as a debugging shortcut. It happens because `chmod 777` appears to make an access problem disappear, but it also destroys the evidence that would have told you whether ownership, group membership, directory traversal, ACLs, or service user identity was the real issue. A better alternative is to inspect each path component and change only the owner, group, ACL, or mode bit that explains the failure.

Another anti-pattern is persistent configuration without a test. Appending to `/etc/fstab`, editing a limits file, or changing a unit drop-in without running the matching verification command leaves you with a deferred failure. The better alternative is immediate validation: `mount -a` for fstab syntax and mountability, a fresh login for PAM-applied limits, and `systemctl daemon-reload` plus status inspection for systemd metadata. The test is part of the change, not an optional cleanup step.

The final anti-pattern is treating Linux layers as interchangeable. `df` does not prove the LV grew, `lvs` does not prove the filesystem grew, `sudo -l` does not prove a service account can traverse `/srv/app`, and `systemctl is-enabled` does not prove the service is currently healthy. Each tool reports one layer. The better approach is to choose the tool that matches the claim you are trying to prove, then stop when the evidence directly answers the question.

| Pattern | Use It When | Why It Works | Verification Signal |
|---------|-------------|--------------|---------------------|
| Verify after each layer | A task spans users, storage, services, or limits | It isolates failures before they compound | `id`, `findmnt`, `df -h`, `systemctl status` match the requested state |
| Narrow policy first | A named user, group, mount, or service has a specific requirement | It avoids broad side effects and preserves least privilege | The named subject works while unrelated subjects are unchanged |
| Fresh-context testing | PAM, group membership, fstab, or systemd should apply policy | It tests the context that actually consumes the configuration | A new login, `mount -a`, or reloaded unit shows the new behavior |

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Using world-writable modes to fix access | The real owner, group, ACL, or service-user problem is hidden | Inspect the path and grant the narrowest access that satisfies the task |
| Editing persistent files without validation | The host may fail after reboot or the next login | Run the command that exercises the persistent file immediately |
| Checking only one storage layer | LV size, filesystem size, and mounted capacity can diverge | Verify the LVM hierarchy and the mounted filesystem separately |

## Decision Framework

Use this framework whenever a practice task asks for an administrative outcome rather than a single command. First, name the consumer: user, group, service, or mounted path. Second, name the layer that grants or blocks the behavior: account database, group membership, file mode, ACL, PAM session, block device, filesystem, mount table, LVM, or systemd unit. Third, choose the command that changes only that layer. Fourth, choose the command that proves the consumer now sees the intended behavior.

```text
+-------------------------+
| What is failing?        |
+-----------+-------------+
            |
            v
+-------------------------+     user cannot act      +---------------------------+
| Is the consumer a user  | -----------------------> | Check getent, id, sudo,  |
| or service account?     |                          | ownership, modes, ACLs   |
+-----------+-------------+                          +---------------------------+
            |
            | path or capacity problem
            v
+-------------------------+     mount missing        +---------------------------+
| Is the storage visible  | -----------------------> | Check lsblk, blkid,      |
| from the mounted path?  |                          | findmnt, fstab, df       |
+-----------+-------------+                          +---------------------------+
            |
            | daemon state problem
            v
+-------------------------+                          +---------------------------+
| Is systemd managing the | -----------------------> | Check status, enablement,|
| expected unit metadata? |                          | logs, daemon-reload      |
+-------------------------+                          +---------------------------+
```

The decision tree is intentionally simple because LFCS time pressure punishes elaborate mental models. If a user cannot act, inspect identity and path access first. If a path or capacity is wrong, inspect storage from device to mount point. If a daemon is wrong, inspect systemd state and then the resources the unit consumes. The framework does not replace knowledge of commands; it tells you which command family belongs to the next question.

| Situation | Prefer | Avoid | Reason |
|-----------|--------|-------|--------|
| One named user needs higher open-file limits | A user-specific file under `/etc/security/limits.d/` | A broad `*` policy unless requested | It satisfies the task without changing unrelated users |
| A mount must survive reboot | UUID in `/etc/fstab` plus `mount -a` verification | Bare `/dev/sdX` names without testing | UUIDs stay stable when device discovery order changes |
| A service unit was edited | `systemctl daemon-reload`, restart, status inspection | Restarting without reloading manager metadata | systemd may otherwise keep using the old unit definition |
| A shared directory needs team write access | Group ownership, mode bits, and fresh membership testing | Recursive world-writable permissions | Group policy remains auditable and constrained |
| An LV was extended but capacity looks unchanged | Grow the filesystem with the correct filesystem tool | Running more `lvextend` commands blindly | The LV and filesystem are separate layers |

## Did You Know?

- Linux file permission bits use separate owner, group, and other classes, so a single octal mode such as `640` encodes three different access decisions in three digits.
- The `/etc/fstab` sixth field controls filesystem check order for tools that honor it; root filesystems commonly use `1`, while many non-root filesystems use `2`.
- systemd became the default init system on many major Linux distributions during the 2010s, which is why LFCS service tasks now assume `systemctl` fluency.
- LVM separates physical volumes, volume groups, and logical volumes, which lets you grow a logical volume without redesigning the entire disk partition layout.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Replacing a user's supplementary groups with `usermod -G` | The command looks like the right group-management tool, but missing `-a` makes the new list replace the old one | Use `usermod -aG group user`, then verify from a fresh login with `id user` |
| Changing mode bits when ownership is the real problem | The error says permission denied, so learners reach for `chmod` before checking owner and group | Inspect each path component, then choose `chown`, `chmod`, or `setfacl` based on the evidence |
| Editing limits files and checking the same shell | `ulimit` is quick, but the current shell already has its limits | Start a fresh login session with `su - user -c 'ulimit -a'` and confirm `pam_limits.so` is in the session stack |
| Adding an `/etc/fstab` entry without testing it | The manual mount worked, so the persistent line feels like paperwork | Run `mount -a`, then verify with `findmnt` and `df -h` before considering the task complete |
| Extending only the logical volume | `lvextend` reports success, which can hide that the filesystem is still the old size | Run `resize2fs` for ext-family filesystems or `xfs_growfs` for XFS, then verify from the mount point |
| Enabling a service without checking active state | Enablement and runtime health are easy to conflate | Use both `systemctl is-enabled` and `systemctl status`, then read logs if the unit is failed |
| Editing a systemd unit and skipping daemon reload | Restarting feels like it should reread everything from disk | Run `systemctl daemon-reload` after unit or drop-in changes, then restart and inspect status |

## Quiz

### Question 1

Exercise scenario: you added `alice` to the `ops` group so she can read `/srv/app/config.yml`, but her existing terminal still cannot read the file. The file is owned by `root:ops` with mode `640`, and the parent directory allows group traversal. What should you check first?

A. Whether `alice` has started a fresh login session that includes the new supplementary group
B. Whether `/srv/app/config.yml` should be changed to mode `777`
C. Whether `mkfs.ext4` needs to be rerun on the backing device
D. Whether `systemctl daemon-reload` was run after the group change

<details><summary>Answer and reasoning</summary>

Option A is correct because supplementary group changes do not necessarily appear inside an already-running login session. A fresh login or `su - alice -c 'id'` verifies the group membership that the access decision will actually use. Option B is wrong because world-writable permissions hide the real access model and grant far more than the task requested. Option C is unrelated to a permission failure on an existing file, and option D is wrong because systemd manager metadata does not control interactive group membership.

</details>

### Question 2

Exercise scenario: you created `/etc/security/limits.d/90-alice.conf` with `alice soft nofile 4096`, but `ulimit -n` in your root terminal still prints the old value. What is the best next verification step?

A. Run `su - alice -c 'ulimit -n'` and confirm the PAM session stack includes `pam_limits.so`
B. Delete `/etc/security/limits.d/90-alice.conf` because limits never apply after login
C. Edit `/etc/fstab` because open-file limits are mounted from disk at boot
D. Restart `nginx` because all limits are service-specific by default

<details><summary>Answer and reasoning</summary>

Option A is correct because persistent limits are applied to new sessions, and PAM must include `pam_limits.so` for the limits file to matter. The root terminal's current `ulimit` value does not prove anything about Alice's next login shell. Option B is wrong because limits can apply, but only in the correct context. Option C is unrelated to resource-limit policy, and option D is wrong because the task names a user limit, not necessarily a systemd service override.

</details>

### Question 3

Exercise scenario: `/data` is mounted manually from `/dev/sdb1`, and the task says it must survive reboot. Which action best satisfies the persistence requirement?

A. Add a UUID-based `/etc/fstab` entry, run `mount -a`, and verify with `findmnt /data`
B. Run `df -h` once and assume the existing mount will return after reboot
C. Add `/dev/sdb1` to `/etc/passwd` so the device name resolves consistently
D. Enable `nginx` because systemd automatically remounts all manual mounts

<details><summary>Answer and reasoning</summary>

Option A is correct because a stable filesystem UUID in `/etc/fstab` expresses boot-time mount intent, and `mount -a` tests that intent before reboot. Option B is wrong because `df -h` only proves current mounted capacity. Option C is incorrect because `/etc/passwd` stores account information, not block-device persistence. Option D is wrong because enabling a web service does not create persistent mount policy for arbitrary filesystems.

</details>

### Question 4

Exercise scenario: you ran `lvextend -L +5G /dev/vg_data/lv_app`, and `lvs` shows the larger logical volume, but `df -h /srv/app` still shows the old size. What is the most likely missing step?

A. Grow the filesystem using the command appropriate for its filesystem type
B. Create the `ops` group again so the directory can refresh capacity
C. Run `passwd alice` because storage growth is applied during authentication
D. Remove `/etc/fstab` because persistent mounts prevent filesystem resizing

<details><summary>Answer and reasoning</summary>

Option A is correct because logical volume growth and filesystem growth are separate operations. For ext-family filesystems, `resize2fs` grows the filesystem; for XFS, `xfs_growfs` targets the mounted path. Option B is wrong because group creation cannot change filesystem capacity. Option C confuses account authentication with storage layout, and option D is wrong because a valid persistent mount does not prevent proper filesystem growth.

</details>

### Question 5

Exercise scenario: you edited a systemd unit drop-in for `nginx`, restarted the service, and nothing changed. The unit file syntax is valid. What step should you add to the workflow?

A. Run `systemctl daemon-reload`, then restart the service and inspect status
B. Reformat the data filesystem because unit metadata lives inside the filesystem journal
C. Use `setfacl` on `/etc/systemd/system` so systemd notices new files
D. Replace `systemctl is-enabled` with `getent group nginx`

<details><summary>Answer and reasoning</summary>

Option A is correct because systemd needs `daemon-reload` after unit or drop-in metadata changes before the manager uses the new definition. Restarting without reloading can keep testing the old manager view. Option B is unrelated and destructive. Option C is wrong because file ACLs are not the normal notification mechanism for systemd unit metadata, and option D checks a different layer than the service manager state.

</details>

### Question 6

Exercise scenario: a service account can read a file from an interactive shell, but the systemd service running as that same account fails with permission denied after reboot. Which investigation order is most defensible?

A. Check systemd status and logs, confirm the unit user, verify the mount with `findmnt`, then inspect ownership and modes
B. Immediately run `chmod -R 777 /srv/app` because any permission error means all modes are too strict
C. Recreate the logical volume because services cannot read from LVM-backed filesystems
D. Disable the service at boot because enabled services cannot access mounted paths

<details><summary>Answer and reasoning</summary>

Option A is correct because it follows the evidence across the layers involved in the failure: unit state, service identity, mount availability, and path access. Option B is wrong because it widens access before diagnosing the real cause. Option C is incorrect because services can use LVM-backed filesystems normally when mounted and permitted. Option D misunderstands enablement; boot persistence is required, but it must be paired with correct dependencies, mounts, and permissions.

</details>

### Question 7

Exercise scenario: an LFCS task asks you to prepare a shared admin area for two operators and prove the result. Which verification set best matches the requirement?

A. Use `getent group`, `id` from a fresh session, path ownership/mode inspection, and a real read-write test as one operator
B. Use only `lsblk` because groups are represented as storage devices after login
C. Use only `systemctl is-enabled` because sudo policy and directory access are service properties
D. Use only `passwd` because setting a password proves shared directory access

<details><summary>Answer and reasoning</summary>

Option A is correct because the task spans group existence, effective membership, path permissions, and actual access. Verifying all four pieces gives direct evidence that the shared area works for the intended users. Option B is wrong because `lsblk` reports block devices, not groups. Option C checks service boot policy, not directory access, and option D proves only that authentication material changed for an account.

</details>

## Hands-On Exercise

Exercise scenario: build a small LFCS practice host for an internal application. You will create a shared operator area, set a resource limit for a test account, prepare a persistent filesystem, grow storage with LVM, and install a service that survives reboot. Use a disposable VM, lab host, or loopback-backed practice disk; do not run destructive storage commands on a machine that contains important data.

The exercise is intentionally integrated because real administration rarely isolates these topics. You should record the command you used, the evidence it produced, and the next layer you plan to verify. If a step fails, diagnose the layer that owns the failure before moving on. A clean partial result is better than a broad workaround that hides the real state of the host.

### Task 1: Build a Shared Admin Area

Create a group, create two users, add both users to the group, create a shared directory, and ensure the group can read and write the shared location. Verify the user records, group membership, ownership, directory mode, and access from a fresh user context. This trains the full identity loop rather than only the account-creation commands.

- [ ] The `ops` group exists and resolves through `getent group ops`.
- [ ] Two practice users exist and show `ops` in `id` output from a fresh session.
- [ ] The shared directory has group ownership set to `ops` and grants the intended group access.
- [ ] At least one practice user can create and read a test file in the shared directory.

<details><summary>Suggested solution</summary>

```bash
sudo groupadd ops
sudo useradd -m alice
sudo useradd -m bob
sudo usermod -aG ops alice
sudo usermod -aG ops bob
sudo mkdir -p /srv/app/shared
sudo chown root:ops /srv/app/shared
sudo chmod 2770 /srv/app/shared
getent group ops
id alice
id bob
su - alice -c 'touch /srv/app/shared/alice-test && ls -l /srv/app/shared/alice-test'
```

The setgid bit on the directory helps new files inherit the group, which is a common shared-directory pattern. If the touch command fails, inspect the directory path with `namei -l /srv/app/shared` or equivalent path checks before changing modes broadly.

</details>

### Task 2: Set and Verify Resource Limits

Create a temporary test account or reuse one practice account, set both soft and hard open-file limits in a drop-in file, verify that the PAM session path includes `pam_limits.so`, and test from a fresh login shell. The important part is proving the new session sees the configured values; checking the old shell is not sufficient.

- [ ] A limits drop-in exists under `/etc/security/limits.d/` for the practice account.
- [ ] The session PAM stack used by the lab host includes `pam_limits.so`.
- [ ] A fresh login shell reports the expected soft and hard open-file limits.
- [ ] The drop-in can be removed cleanly after practice.

<details><summary>Suggested solution</summary>

```bash
# Create a test user
sudo useradd -m testlimits

# Check default limits
su - testlimits -c 'ulimit -n'    # open files
su - testlimits -c 'ulimit -u'    # max processes

# Set custom limits
echo "testlimits soft nofile 4096" | sudo tee /etc/security/limits.d/90-testlimits.conf
echo "testlimits hard nofile 8192" | sudo tee -a /etc/security/limits.d/90-testlimits.conf
echo "testlimits soft nproc 512" | sudo tee -a /etc/security/limits.d/90-testlimits.conf

# Verify PAM is wired (critical — limits won't apply without this)
grep pam_limits.so /etc/pam.d/common-session

# Start a FRESH login shell and verify (same shell won't show new limits)
su - testlimits -c 'ulimit -n'    # should show 4096
su - testlimits -c 'ulimit -Hn'   # should show 8192
su - testlimits -c 'ulimit -u'    # should show 512
```

```bash
# Inspect the full session PAM stack
cat /etc/pam.d/common-session

# Confirm pam_limits.so is present and required
grep -n pam_limits /etc/pam.d/common-session

# Check password complexity rules
grep pam_pwquality /etc/pam.d/common-password
cat /etc/security/pwquality.conf 2>/dev/null
```

```bash
sudo rm /etc/security/limits.d/90-testlimits.conf
sudo userdel -r testlimits
```

If your distribution uses a different PAM layout, adapt the inspection to the service stack that handles the login path you are testing. The verification principle is the same: persistent limit policy must be read by the session mechanism that creates the user's process environment.

</details>

### Task 3: Make Storage Persistent

Use a spare lab disk, a partition created for practice, or a loopback device. Create a filesystem, mount it at `/data`, add a UUID-based `/etc/fstab` entry, test the entry with `mount -a`, and verify the result with `findmnt` and `df -h`. Do not use a production disk for this practice step.

- [ ] `lsblk` shows the intended practice device or loopback mapping.
- [ ] The filesystem has a UUID reported by `blkid`.
- [ ] `/etc/fstab` contains a UUID-based entry for `/data`.
- [ ] `mount -a`, `findmnt /data`, and `df -h /data` all confirm the expected persistent mount.

<details><summary>Suggested solution</summary>

```bash
lsblk
blkid
# run only ONE of these (choose ext4 OR xfs)
mkfs.ext4 /dev/sdb1
mkfs.xfs /dev/sdb1
mkdir -p /data
mount /dev/sdb1 /data
findmnt /data
```

```bash
UUID=$(blkid -s UUID -o value /dev/sdb1)
echo "UUID=$UUID /data ext4 defaults 0 2" | sudo tee -a /etc/fstab
mount -a
```

Choose either ext4 or XFS for the actual lab run; the commands are shown together so you can compare both filesystem choices. If you choose XFS, make the `/etc/fstab` filesystem type match `xfs`, not `ext4`.

</details>

### Task 4: Create and Grow LVM Storage

Create a physical volume, volume group, and logical volume from a lab device. Format it, mount it at `/srv/app`, then extend the logical volume and grow the filesystem with the correct filesystem-specific tool. Verify the LVM hierarchy and the mounted capacity after growth.

- [ ] `pvs`, `vgs`, or `lvs` shows the expected LVM objects.
- [ ] `/srv/app` is mounted from the logical volume.
- [ ] The logical volume and filesystem are both larger after the growth step.
- [ ] Verification uses both LVM tools and mounted-filesystem tools.

<details><summary>Suggested solution</summary>

```bash
pvcreate /dev/sdb1
vgcreate vg_data /dev/sdb1
lvcreate -n lv_app -L 10G vg_data
mkfs.ext4 /dev/vg_data/lv_app
mkdir -p /srv/app
mount /dev/vg_data/lv_app /srv/app
```

```bash
lvextend -L +5G /dev/vg_data/lv_app
resize2fs /dev/vg_data/lv_app
lvs
lsblk
df -h /srv/app
```

```bash
lvextend -L +5G /dev/vg_data/lv_app
xfs_growfs /srv/app
lvs
df -h /srv/app
```

Use the ext4 growth block only for an ext-family filesystem and the XFS growth block only for XFS. The exam skill is selecting the resize command that matches the filesystem you created, then proving the mounted path reflects the new capacity.

</details>

### Task 5: Install and Persist a Service

Install a simple service, enable it at boot, start it, inspect current state, and confirm enablement. If you edit unit metadata during practice, reload the systemd manager before restarting the unit. Tie the service back to the earlier tasks by checking whether the service account can read the path it needs.

- [ ] The package installs without unresolved dependency errors.
- [ ] The service is active after startup.
- [ ] The service is enabled for boot.
- [ ] Any unit or drop-in edit is followed by `systemctl daemon-reload` before restart.

<details><summary>Suggested solution</summary>

```bash
apt update
apt install -y nginx
systemctl enable --now nginx
systemctl status nginx
systemctl is-enabled nginx
systemctl daemon-reload
systemctl restart nginx
```

After the service starts, check the exact success condition the task names. If the task only asks for boot persistence, `systemctl is-enabled` is relevant. If the task asks for a running service, `systemctl status` and logs are relevant. If the task asks the service to read from `/srv/app`, path ownership, mode bits, mount state, and service user identity are all relevant.

</details>

## Sources

- https://man7.org/linux/man-pages/man8/useradd.8.html
- https://man7.org/linux/man-pages/man8/usermod.8.html
- https://man7.org/linux/man-pages/man1/chmod.1.html
- https://man7.org/linux/man-pages/man1/chown.1.html
- https://man7.org/linux/man-pages/man5/limits.conf.5.html
- https://man7.org/linux/man-pages/man8/pam_limits.8.html
- https://man7.org/linux/man-pages/man5/pam.conf.5.html
- https://man7.org/linux/man-pages/man8/mount.8.html
- https://man7.org/linux/man-pages/man5/fstab.5.html
- https://man7.org/linux/man-pages/man8/blkid.8.html
- https://man7.org/linux/man-pages/man8/lsblk.8.html
- https://man7.org/linux/man-pages/man1/systemctl.1.html
- https://man7.org/linux/man-pages/man8/lvm.8.html

## Next Module

Next: [LFCS Full Mock Exam](../module-1.5-full-mock-exam/) brings these skills together in a timed end-to-end practice run where identity, storage, service, and verification habits must work as one coherent operating routine.
