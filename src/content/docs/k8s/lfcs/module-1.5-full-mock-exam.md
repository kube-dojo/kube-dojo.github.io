---
citations_verified: true
title: "LFCS Full Mock Exam"
slug: k8s/lfcs/module-1.5-full-mock-exam
sidebar:
  order: 105
---

> **LFCS Track** | Complexity: `[COMPLEX]` | Time: 90-120 min

**Reading Time**: 25-35 minutes to brief, then one full timed run and one structured debrief.

## Prerequisites

Before starting this module, complete [LFCS Exam Strategy and Workflow](../module-1.1-exam-strategy-and-workflow/) so your command workflow is already intentional under time pressure.

Before starting this module, complete [LFCS Essential Commands Practice](../module-1.2-essential-commands-practice/) so file search, text processing, archives, links, and redirection are not new during the mock.

Before starting this module, complete [LFCS Running Systems and Networking Practice](../module-1.3-running-systems-and-networking-practice/) so you can inspect systemd services, logs, interfaces, routes, DNS, and listening sockets.

Before starting this module, complete [LFCS Storage, Services, and Users Practice](../module-1.4-storage-services-and-users-practice/) so mounts, permissions, users, groups, and scheduled jobs feel familiar enough to combine.

You should also have a disposable Linux VM, cloud instance, or lab machine where you are allowed to create users, change services, edit mounts, and make mistakes without risking production work.

## Learning Outcomes

After this module, you will be able to design an LFCS-style timed run that covers essential commands, users, services, networking, storage, and scheduled tasks without turning the practice into random command drilling.

After this module, you will be able to prioritize mixed-domain exam tasks by effort, risk, and verification cost so easy points are captured before harder tasks consume the session.

After this module, you will be able to execute common LFCS task patterns using runnable shell commands, then prove the system state with independent verification instead of trusting command exit codes alone.

After this module, you will be able to debug failed task attempts by reading symptoms, choosing the next inspection command, and correcting the smallest cause that explains the observed state.

After this module, you will be able to evaluate your own mock-exam performance with a debrief that turns timing mistakes and command gaps into a focused retake plan.

## Why This Module Matters

A junior administrator walks into a maintenance window with a checklist, a clock, and a system that does not care how much theory they studied the night before. The first task looks easy, the second task fails for an unexpected reason, and the third task looks unrelated until a missing group membership explains both permission errors and a service failure. This is the moment when exam preparation stops being about knowing commands and starts being about controlling attention.

The LFCS exam is a [performance assessment](https://docs.linuxfoundation.org/tc-docs/certification/instructions-lfcs-and-lfce), which means the system judges the final machine state more than the story in the candidate's head. A learner may understand cron, systemd, storage, networking, and permissions in separate study sessions, yet still lose time switching between them when the tasks arrive in a mixed order. This module exists because real competence appears when those domains are combined under time pressure.

A senior operator does not win by typing the most commands; they win by forming a small hypothesis, running a precise check, making a minimal change, and verifying the result from another angle. That behavior is learnable, but it has to be practiced as a complete loop. The mock exam in this module is therefore less about discovering brand-new Linux features and more about rehearsing the way a reliable operator thinks.

The module begins with the operating model for a timed run, then demonstrates the command patterns you will use, then asks you to perform a structured mock with success criteria. That sequence matters because unsupported practice creates noise. You should see a worked example before you are asked to solve the same kind of problem independently.

## The Mock Exam Operating Model

A full mock exam needs boundaries, otherwise it becomes ordinary study with a timer nearby. The goal is to practice the exact behavior you need when the environment is unfamiliar, the tasks are mixed, and the safest answer is the one you can verify quickly. Treat the mock as a small production change window where every completed item must leave evidence behind.

The operating model has four phases: read, rank, execute, and debrief. Reading means scanning all tasks before touching the terminal so you understand the shape of the session. Ranking means deciding which tasks are quick wins, which tasks are risky, and which tasks should wait until you have secured easier points. Execution means working one task at a time and verifying each result before moving on. Debrief means extracting a practice plan from the run instead of simply feeling good or bad about the score.

```ascii
+------------------+      +------------------+      +------------------+      +------------------+
|  Read all tasks  | ---> | Rank by payoff   | ---> | Execute + verify | ---> | Debrief evidence |
|  before typing   |      | effort, and risk |      | one task at time |      | not impressions  |
+------------------+      +------------------+      +------------------+      +------------------+
```

The diagram is deliberately simple because the exam workflow should stay simple when your stress level rises. If you invent a complicated tracking system during the run, the tracking system becomes another task competing for attention. A useful candidate note is short enough to read at a glance and specific enough to tell you what remains unfinished.

A practical note format uses one line per task, a status marker, and a verification command. You are not writing documentation for a teammate during the mock. You are leaving yourself a navigation aid so you do not reopen solved work or forget which result still needs proof.

```text
[ ] users: create operator1, add supplementary group, verify with id and file write
[ ] service: inspect failed unit, fix cause, verify active and journal has no new failure
[ ] storage: mount device or loop image, persist in fstab, verify with findmnt and df
[ ] network: prove route, DNS, listening socket, or firewall state depending on symptom
```

The best mock-exam habit is to separate solving from proving. Solving is the change that should make the task true. Proving is an independent check that shows the task is true now. Many candidates lose points because they complete the change but never run the command that would reveal a typo, wrong path, missing group, stale service, or nonpersistent mount.

Stop and think before you continue: if a task says "make this survive reboot," which command proves the current state, and which command proves the persistent configuration? A current-state command like `mount` or `systemctl status` is useful, but persistence often requires reading `/etc/fstab`, checking enabled units, or using the tool that owns the configuration. This distinction appears repeatedly in the mock.

A good timed run also needs an explicit skip rule. If a task produces no progress after several focused inspection commands, mark it as blocked and move to another item. Returning later with a fresh context is usually cheaper than spending the entire session trying to rescue one stubborn task while untouched tasks remain available.

The skip rule is not a sign of weak knowledge; it is a scoring strategy. In real operations, unresolved work may need escalation, rollback, or a second pair of eyes. In an exam, unresolved work needs containment so it does not steal time from tasks you can complete.

## Preparing the Practice Environment

Run the mock in a disposable Linux environment where `sudo` is available and where system-level changes are acceptable. A local VM is ideal because you can take a snapshot, break the machine, and restore it without hesitation. A cloud instance also works, but confirm that storage devices, firewall behavior, and service management resemble the distribution you intend to practice on.

Before starting the timer, create a workspace that holds temporary files, logs, archives, and small scripts. Keeping mock artifacts under one directory reduces cleanup time and makes verification easier. The exam environment may give you existing files instead, but practicing with a tidy workspace helps you learn the command flow without making the first run unnecessarily chaotic.

```bash
mkdir -p ~/lfcs-mock/{docs,logs,archives,restore,scripts,service-data}
printf 'alpha\nbravo\ncharlie\nerror: disk warning\n' > ~/lfcs-mock/logs/app.log
printf 'operator=maya\nteam=platform\nrole=oncall\n' > ~/lfcs-mock/docs/operator.conf
printf 'daily backup completed\nweekly backup pending\n' > ~/lfcs-mock/docs/backup-notes.txt
```

The sample files above are intentionally small, but the command patterns scale to larger trees. The exam rarely rewards complex one-liners for their own sake. It rewards choosing a command that reliably finds the requested object, extracts the right data, and leaves a verifiable result.

Use one shell session for execution and one lightweight note area for task tracking if your lab allows it. If you only have one terminal, keep notes in a plain text file under the mock directory. Avoid building elaborate aliases, functions, or custom scripts that would not be available on the real exam machine unless they save more time than they cost.

```bash
printf 'LFCS mock started: %s\n' "$(date -Is)" > ~/lfcs-mock/mock-notes.txt
printf '[ ] essential commands\n[ ] users and permissions\n[ ] service\n' >> ~/lfcs-mock/mock-notes.txt
printf '[ ] networking\n[ ] storage\n[ ] scheduled task\n' >> ~/lfcs-mock/mock-notes.txt
```

A clean environment does not mean a sterile environment. The mock should include enough friction that you practice diagnosis, not only happy-path command recall. Add a few files with similar names, a permission boundary, and a service or scheduled job that must be inspected rather than guessed.

If you are sharing a lab host, do not create usernames that could conflict with real accounts. Use a predictable practice prefix, such as `lfcsop1`, and remove the accounts after the exercise. Safe naming is part of professional system administration because careless test artifacts become tomorrow's mystery.

Stop and think: which changes in this mock are reversible by deleting files, and which changes alter global system state? Creating files under your home directory is low risk, while changing `/etc/fstab`, creating users, opening firewall rules, and enabling services require more deliberate cleanup. This risk ranking should influence both your practice environment and your task order.

A useful preflight check records the current distribution, kernel, storage view, and service manager. These commands are not answers to mock tasks by themselves, but they give you orientation. When a later command behaves unexpectedly, you can tell whether the environment is using systemd, which package tools exist, and what storage devices are present.

```bash
cat /etc/os-release
uname -r
systemctl --version | head -n 1
lsblk
ip -br address
```

The most important preflight result is not a particular version string. The important result is that you have seen the machine before the clock starts. Candidates often lose time because they assume a command exists, assume a device name, or assume a service name instead of inspecting the environment.

## Reading and Ranking the Task List

The first pass through a full mock should take only a few minutes, but it changes the entire session. You are looking for tasks whose commands are familiar, whose verification is clear, and whose blast radius is small. You are also looking for tasks that can break the machine if done carelessly, such as filesystem mounts or service configuration changes.

A simple ranking table helps you choose the first tasks without overthinking. The "verification cost" column is especially important because a task that is easy to change but hard to prove may be more expensive than it looks. The best first tasks usually have a clear command, a clear output, and no dependency on a later task.

| Task Type | Typical Payoff | Typical Risk | Fast Verification |
|---|---|---|---|
| Essential commands | High if syntax is familiar | Low because files are local | `find`, `grep`, `tar -tf`, restored file comparison |
| Users and permissions | High if names are exact | Medium because ownership mistakes block access | `id`, `namei -l`, `sudo -u`, actual write test |
| Running services | Medium to high | Medium because restart loops hide root cause | `systemctl is-active`, `journalctl`, service-specific check |
| Networking | Variable because symptoms differ | Medium because firewall and DNS confuse each other | `ip`, `ss`, `getent hosts`, `curl` or `nc` |
| Storage | High but risky | High because persistence errors can affect boot | `findmnt`, `df`, `mount -a`, controlled test file |
| Scheduled tasks | Medium and quick | Low to medium depending on user context | `crontab -l`, spool inspection, log or output file |

Ranking also prevents the common trap of doing tasks in the order they are printed. Printed order is not necessarily difficulty order, and exam tasks are not emotional obligations. You should treat the task list as a backlog, not a script.

A useful rank mark has three pieces: estimated effort, confidence, and verification command. For example, "E/high/tar -tf" means an essential-command task looks easy and can be proved by listing the archive. "M/medium/findmnt + mount -a" means a storage task may be manageable, but it needs both current-state and persistence checks.

Your first pass should not solve the tasks in your head. It should identify the first two or three tasks to attempt. Over-planning creates the same failure mode as under-planning: the clock advances while the machine state remains unchanged.

A strong candidate starts with tasks that create momentum and evidence. Momentum matters because early wins reduce stress. Evidence matters because the final system state is what earns credit. A task that feels complete but has no verification output is only a guess.

Stop and think: if you had ten minutes left and three tasks remained, which one would you choose first? The right answer depends on the environment, but the reasoning should include time to verify. A partial storage task with no persistence proof may be worth less than a fully verified scheduled job.

## Worked Example: Essential Commands Under Exam Pressure

The essential-commands task usually looks harmless, which is why it deserves disciplined verification. Candidates often find the right file, extract the right line, build an archive, and then lose points because the archive contains the wrong parent directory or cannot be restored cleanly. The fix is to use a small command sequence that proves each step.

Suppose the task says: find the configuration file that contains the word `platform`, save the matching line to `~/lfcs-mock/result.txt`, create a compressed archive of the `docs` directory, and prove the archive restores. The task combines search, redirection, archiving, and verification. None of those pieces is hard alone, but the exam tests whether you combine them without drifting.

Start by searching with both filename and content in mind. `find` answers questions about paths, while `grep` answers questions about file contents. When the task gives a word inside a file, `grep -R` is the natural first tool because it reports the file that contains the content.

```bash
grep -R "platform" ~/lfcs-mock/docs
grep -R "platform" ~/lfcs-mock/docs > ~/lfcs-mock/result.txt
cat ~/lfcs-mock/result.txt
```

The verification here is not simply that `grep` returned success. The verification is that the result file contains the requested line and that the path is the one you expected. Reading the result file is cheap, and it catches mistakes such as redirecting output to the wrong directory or matching an unintended file.

Now create the archive from the parent directory so the stored path is predictable. This avoids the common problem where the archive contains absolute paths or an unexpected deep prefix. The `-C` option changes directory for the archive operation without changing your shell's current directory.

```bash
tar -czf ~/lfcs-mock/archives/docs.tgz -C ~/lfcs-mock docs
tar -tzf ~/lfcs-mock/archives/docs.tgz
```

The list operation proves what the archive contains before you restore it. If the archive contains `docs/operator.conf`, that is easy to restore into a separate directory. If it contains a long home-directory path, the archive may still function, but it is less clean and may not match the requested output.

Finally restore the archive into an empty location and compare one known file. You are not verifying compression theory; you are verifying that your specific archive can recreate the requested content. A restored file comparison is stronger evidence than an archive listing alone.

```bash
rm -rf ~/lfcs-mock/restore/docs
mkdir -p ~/lfcs-mock/restore
tar -xzf ~/lfcs-mock/archives/docs.tgz -C ~/lfcs-mock/restore
diff -u ~/lfcs-mock/docs/operator.conf ~/lfcs-mock/restore/docs/operator.conf
```

The senior habit in this simple example is the independent check. `tar` creation, `tar` listing, extraction, and `diff` each inspect a different part of the result. You would not always run every command in a real exam if time is tight, but practicing the full loop teaches you what a trustworthy result looks like.

The pattern generalizes to many file tasks. Find the object, transform or store the object, inspect the output, and test the output in a clean place. When the task involves text processing, prefer commands whose output you can immediately read, count, or compare.

## Worked Example: Users and Permissions

User and permission tasks are easy to start and easy to verify poorly. The system may accept a `useradd` command, but that does not prove the user belongs to the required group, can traverse the parent directories, or can write to the target path. Permission work must be tested as the target identity, not only inspected as root.

Suppose the task says: create a group named `platformops`, create a user named `lfcsop1`, make the user a supplementary member of the group, create `/srv/platform-reports`, and allow group members to create files there. This task involves account creation, group membership, ownership, mode bits, and an actual access test.

```bash
sudo groupadd platformops
sudo useradd -m -s /bin/bash -G platformops lfcsop1
sudo mkdir -p /srv/platform-reports
sudo chown root:platformops /srv/platform-reports
sudo chmod 2770 /srv/platform-reports
```

The setgid bit in `2770` is deliberate. It causes new files created inside the directory to inherit the directory's group, which is often what a shared operational directory needs. Without setgid, files may be created with the user's primary group instead, which can surprise the next operator who expects group collaboration.

Verification starts with identity. `id` confirms the account and group membership from the system's perspective. It does not prove path access by itself, but it catches wrong usernames, missing supplementary groups, and account creation mistakes immediately.

```bash
id lfcsop1
namei -l /srv/platform-reports
sudo -u lfcsop1 bash -c 'printf "ok\n" > /srv/platform-reports/access-test.txt'
ls -l /srv/platform-reports/access-test.txt
```

The `sudo -u` command is the key proof because it performs the requested action as the requested user. A mode string can look correct while a parent directory still blocks traversal. A group membership can look correct while an existing login session has not picked up the new group. An actual file write reduces those uncertainties.

If the write test fails, resist changing permissions blindly to `777`. Diagnose the path one layer at a time. `namei -l` shows each component in the path, and `id` shows the effective groups. The smallest correction that explains the failure is almost always safer than opening the directory to everyone.

```bash
namei -l /srv/platform-reports
sudo -u lfcsop1 id
sudo -u lfcsop1 test -w /srv/platform-reports && echo writable
```

The exam may not ask for setgid explicitly, and you should not add extra behavior when the task only asks for ordinary ownership. However, when the goal is a shared group directory, understanding setgid helps you choose a configuration that continues to work after the first file is created. This is the difference between passing a one-time test and building a stable result.

## Worked Example: Running Systems and systemd

Service tasks test whether you can move from symptom to cause without random restarts. A failed service has at least three layers: the unit state, the recent journal entries, and the configuration or executable the unit depends on. Restarting repeatedly without reading those layers often destroys the evidence you need.

For practice, create a small systemd service that intentionally fails because it points to a missing script. This example is safe on a disposable VM and demonstrates the inspection sequence. If your lab does not allow creating units, read the example as a command pattern and practice on an existing harmless user service instead.

```bash
sudo tee /etc/systemd/system/lfcs-mock.service >/dev/null <<'EOF'
[Unit]
Description=LFCS mock failing service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/lfcs-mock-start

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl start lfcs-mock.service || true
```

The service fails because `/usr/local/bin/lfcs-mock-start` does not exist. The exam version may be more subtle, such as a wrong path, missing permission, bad environment file, or invalid config. The workflow is the same: inspect state, read logs, make the smallest correction, reload if unit files changed, restart, and verify.

```bash
systemctl status lfcs-mock.service --no-pager
journalctl -u lfcs-mock.service -n 20 --no-pager
systemctl cat lfcs-mock.service
```

`systemctl status` gives the high-level state, `journalctl` gives recent failure details, and `systemctl cat` shows the effective unit content. Those commands answer different questions. If you only run one of them, you may see the symptom but miss the cause.

Now create the missing script with executable permissions. The content can be minimal because the task is about the service path and executable state. After changing an executable script, you do not need `daemon-reload`; after changing the unit file itself, you do.

```bash
sudo tee /usr/local/bin/lfcs-mock-start >/dev/null <<'EOF'
#!/usr/bin/env bash
printf 'lfcs mock service ran at %s\n' "$(date -Is)" >> /var/log/lfcs-mock-service.log
EOF
sudo chmod 755 /usr/local/bin/lfcs-mock-start
sudo systemctl start lfcs-mock.service
systemctl is-active lfcs-mock.service || true
tail -n 5 /var/log/lfcs-mock-service.log
```

A oneshot service may not remain `active` after it exits, depending on the unit configuration. That is an important detail because "verify it remains active" and "verify it completed successfully" are different task requirements. Read the task text carefully and verify the state it asks for, not the state you wish the service had.

When a service should stay active, use a long-running process or inspect the main process with `systemctl status` and `systemctl show`. When a service is meant to perform a one-time action, success may be `inactive` with a successful result. The exam rewards matching verification to intent.

```bash
systemctl show lfcs-mock.service -p ActiveState -p SubState -p Result
journalctl -u lfcs-mock.service -n 10 --no-pager
```

This worked example also teaches cleanup. Practice services should not remain on shared systems after the mock. Removing the unit and reloading systemd is part of responsible lab behavior and prepares you for tasks that ask you to undo or disable a service cleanly.

```bash
sudo systemctl disable --now lfcs-mock.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/lfcs-mock.service /usr/local/bin/lfcs-mock-start
sudo systemctl daemon-reload
sudo rm -f /var/log/lfcs-mock-service.log
```

## Worked Example: Networking Diagnosis

Networking tasks are difficult because similar symptoms can come from different layers. A failed `curl` can mean no address, wrong route, failed DNS, blocked port, stopped service, firewall policy, or application error. The solution is not to memorize one command; the solution is to inspect layers in an order that narrows the problem.

A reliable order is local address, route, name resolution, listening socket, firewall, and application test. This order starts with facts about the local host and moves outward. It also prevents you from blaming DNS when the interface has no address or blaming a firewall when the service is not listening.

```ascii
+-------------+     +-------------+     +-------------+     +-------------+     +-------------+
| IP address  | --> | Route table | --> | Name lookup | --> | Local ports | --> | App request |
| ip -br addr |     | ip route    |     | getent      |     | ss -ltnp    |     | curl / nc   |
+-------------+     +-------------+     +-------------+     +-------------+     +-------------+
```

Start with facts that do not require the remote service to cooperate. `ip -br address` shows interface addresses compactly, and `ip route` shows how packets should leave the host. If either of those is wrong, higher-level tests will only produce confusing errors.

```bash
ip -br address
ip route
```

Then inspect name resolution separately from connection testing. `getent hosts` uses the system's configured name service path, which can include `/etc/hosts`, DNS, and other sources. This is often more representative than a DNS-only tool when the task asks how the host resolves names.

```bash
getent hosts localhost
getent hosts example.com
```

For local services, confirm that something is listening before testing from another host. `ss -ltnp` shows TCP listeners and, when permissions allow, the owning process. A firewall cannot forward traffic to a service that is not listening, so this check belongs before firewall guessing.

```bash
ss -ltnp
```

If the task involves an HTTP service, a local request gives fast feedback. Use `curl -I` for headers when the content does not matter, and use a full request when you need to verify a body. If `curl` is not installed, `nc` or distribution-specific tools may be available, but do not spend the mock installing utilities unless the task requires it.

```bash
curl -I http://127.0.0.1/ 2>/dev/null || true
```

Firewall commands vary by distribution, and LFCS tasks may expect `firewalld`, `nftables`, `iptables`, or a distribution wrapper. The senior habit is to identify the active firewall mechanism before changing rules. Running commands from the wrong firewall family can give you a false sense of completion.

```bash
systemctl is-active firewalld 2>/dev/null || true
sudo nft list ruleset 2>/dev/null | head -n 40 || true
sudo iptables -S 2>/dev/null | head -n 20 || true
```

Stop and think: if name resolution fails but `curl http://93.184.216.34/` succeeds, what layer would you inspect next? The likely problem is the resolver path, not the route. You would check `/etc/resolv.conf`, `getent hosts`, and any local host entries before changing interface or firewall configuration.

Networking verification should prove the required path, not merely a nearby path. If the task asks for connectivity to a name, verify the name. If it asks for a local listener, verify the listener. If it asks for a firewall opening, verify that the service is reachable after the rule, not only that a rule exists.

## Worked Example: Storage and Persistence

Storage tasks deserve extra care because a wrong command can damage data or make a system boot poorly. In a real exam environment, you may be given a spare disk, partition, logical volume, or existing filesystem. In a practice VM, a loopback file lets you rehearse the mount and persistence workflow without needing extra hardware.

The loopback example creates a file, formats it, mounts it, writes a test file, and adds an `/etc/fstab` entry using a UUID. [Using a UUID is usually more stable than using a loop device name because loop device numbers can change.](https://raw.githubusercontent.com/util-linux/util-linux/master/sys-utils/mount.8.adoc) On real disks, UUIDs are also safer than device names that may shift between boots.

```bash
mkdir -p ~/lfcs-mock/storage
dd if=/dev/zero of=~/lfcs-mock/storage/data.img bs=1M count=64
mkfs.ext4 -F ~/lfcs-mock/storage/data.img
sudo mkdir -p /mnt/lfcs-data
sudo mount -o loop ~/lfcs-mock/storage/data.img /mnt/lfcs-data
```

Current-state verification comes first. `findmnt` shows what is mounted where, and `df` confirms the filesystem is visible as usable storage. A write test proves that the mounted path is not merely an empty directory that happens to exist.

```bash
findmnt /mnt/lfcs-data
df -h /mnt/lfcs-data
printf 'storage ok\n' | sudo tee /mnt/lfcs-data/proof.txt >/dev/null
cat /mnt/lfcs-data/proof.txt
```

Persistence is a separate requirement. For real block devices, `blkid` can return a UUID directly. For loopback practice, you can still inspect the filesystem UUID and write an `/etc/fstab` line, but remember that loopback mounts in `/etc/fstab` may behave differently across distributions unless the backing file is available early enough.

```bash
sudo blkid ~/lfcs-mock/storage/data.img
```

A realistic fstab line uses the UUID, mount point, filesystem type, options, dump field, and fsck order. You should understand every field because a missing field or bad option can break the verification. The following command prints a candidate line; review it before appending on your practice machine.

```bash
UUID_VALUE="$(sudo blkid -s UUID -o value ~/lfcs-mock/storage/data.img)"
printf 'UUID=%s /mnt/lfcs-data ext4 loop,defaults 0 0\n' "$UUID_VALUE"
```

If you choose to append the line during practice, make a backup first. Then run `mount -a` to test fstab syntax without rebooting. This is one of the most important LFCS storage habits because it catches errors while you still have a working shell.

```bash
sudo cp /etc/fstab /etc/fstab.lfcs-mock.bak
UUID_VALUE="$(sudo blkid -s UUID -o value ~/lfcs-mock/storage/data.img)"
printf 'UUID=%s /mnt/lfcs-data ext4 loop,defaults 0 0\n' "$UUID_VALUE" | sudo tee -a /etc/fstab
sudo mount -a
findmnt /mnt/lfcs-data
```

If `mount -a` fails, do not reboot to "see what happens." Read the error, inspect the line, and restore the backup if necessary. A candidate who can safely recover from a bad fstab line is practicing like an administrator, not just a command typist.

```bash
sudo cp /etc/fstab.lfcs-mock.bak /etc/fstab
sudo umount /mnt/lfcs-data 2>/dev/null || true
sudo mount -a
```

The storage pattern is therefore: identify the device or filesystem, mount it, verify current state, configure persistence, verify persistence syntax, and prove data survives remount. Each step has a different failure mode, so one command cannot replace the whole chain.

## Worked Example: Scheduled Tasks

Scheduled task questions test both syntax and execution context. A cron entry installed for root is not the same as a cron entry installed for a normal user. [A command that works interactively may fail under cron because the environment is smaller, the path is different, or output is discarded.](https://raw.githubusercontent.com/cronie-crond/cronie/master/man/crontab.5)

For a safe practice task, create a user crontab entry that writes a timestamp to a file under your mock directory. Use absolute paths where practical. Cron examples should avoid depending on interactive shell startup files, because cron does not behave like an interactive login shell.

```bash
mkdir -p ~/lfcs-mock/cron-output
CRON_FILE="$(mktemp)"
crontab -l 2>/dev/null > "$CRON_FILE" || true
printf '* * * * * /usr/bin/date -Is >> %s/cron-output/timestamps.log\n' "$HOME/lfcs-mock" >> "$CRON_FILE"
crontab "$CRON_FILE"
rm -f "$CRON_FILE"
```

Verification has two layers: confirm the schedule exists, then confirm the scheduled command produces the expected effect. The first check catches syntax and installation mistakes. The second check catches environment and permission mistakes.

```bash
crontab -l
sleep 70
tail -n 5 ~/lfcs-mock/cron-output/timestamps.log
```

If the output file does not appear, inspect whether the cron service is active and whether the command path exists. Distribution service names can vary, so use `systemctl list-units` if a direct service name fails. Do not assume the scheduler is broken before checking the command itself.

```bash
command -v date
systemctl list-units '*cron*' '*crond*' --no-pager
```

When the practice task is complete, remove the specific mock line without destroying unrelated crontab entries. This is an important habit because real systems may already have scheduled work. Overwriting an entire crontab to clean one practice line is the kind of mistake that passes a toy lab but fails operational judgment.

```bash
crontab -l | grep -v 'lfcs-mock/cron-output/timestamps.log' | crontab -
crontab -l
```

A one-time `at` job has a similar pattern: create the job, list the job, inspect the job if needed, and remove it if the task asks for cleanup. If `at` is not installed or the daemon is inactive, that becomes part of the diagnosis. The key is to verify the scheduling system, not merely type the scheduling command.

## The Mock Exam Structure

The mock exam below is a representative integrated run. It is not a promise about exact LFCS task wording, and it should not become a script you memorize. Its purpose is to force you to combine the command families from earlier modules while maintaining a clear verification discipline.

Use a 90-minute timer for the first full run. Spend the first few minutes reading and ranking, then begin with the tasks that look most controllable. Leave a final review window at the end, even if that means stopping work on an unresolved task.

```ascii
+-------------------+-------------------+-------------------+
| First pass        | Main execution    | Final review      |
| read and rank     | solve + verify    | inspect evidence  |
| 5-8 minutes       | 70-78 minutes     | 7-12 minutes      |
+-------------------+-------------------+-------------------+
```

The final review window is not optional decoration. It is where you catch missing verification, wrong paths, tasks left in a temporary state, and changes that need persistence. Many mock runs improve immediately when the learner stops working until the last second and instead reserves time to inspect the final state.

### Task 1: Essential Commands and Archives

You are given a directory tree with configuration notes, logs, and reports. Locate the file that contains a requested phrase, extract the matching line into a result file, create a compressed archive of the requested directory, and prove the archive restores into a clean location.

Before solving, identify whether the task is asking for a filename, file content, file metadata, or a transformed output. Those are different questions. `find` is strong for names and metadata, `grep` is strong for content, `tar` is strong for archives, and `diff` is strong for restored-content proof.

A good completion leaves evidence in three places: the extracted result file, the archive listing, and the restored copy. If any of those is missing, you may have done the work but not proved the work. The proof is especially important if the archive command used `-C`, because the stored path may not be what you assume.

Stop and think: if the archive lists `home/student/lfcs-mock/docs/operator.conf` instead of `docs/operator.conf`, would the task still be acceptable? The answer depends on the wording, but the safer exam habit is to archive from a controlled parent directory so restoration creates the expected structure.

### Task 2: Users, Groups, and Shared Directory Access

You are asked to provision access for a new operator. Create the required group if it does not exist, create the user if needed, add the user to the correct supplementary group, set directory ownership and mode, and verify with both identity inspection and an actual file operation as that user.

The task is not complete when `useradd` exits successfully. Account state, group state, directory ownership, parent traversal, setgid behavior, and write access all matter. A clean verification uses `id`, `namei -l`, `ls -ld`, and `sudo -u USER` for an actual test.

Be careful with existing accounts and groups. If the task says to modify an existing user, do not recreate it and risk changing its shell, home directory, or UID. Use inspection commands first, then apply the smallest modification that produces the requested state.

A strong answer also avoids over-permissioning. Setting a shared directory to world-writable may make a test file succeed, but it violates the intent of controlled group access. The correct fix should explain why the named user gains access and why unrelated users do not.

### Task 3: Running Systems and Service Failure

A service is not starting as expected. Inspect the unit state, read recent logs, identify the smallest cause that explains the failure, correct it, restart or reload as appropriate, and verify the service state matches the task wording.

Do not begin by editing the first file that looks related. Start with `systemctl status`, `journalctl -u`, and `systemctl cat` so you know what systemd is actually trying to run. If the unit references an environment file, script, socket, mount, or user, inspect that dependency before changing the unit itself.

If you edit a unit file, run `systemctl daemon-reload` before restarting. If you edit only a script or config file consumed by the service, a daemon reload may not be required, but a service restart usually is. The important point is to understand which layer changed.

Verification should match service type. A long-running daemon should become active and stay active. [A oneshot unit may complete successfully and become inactive](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.service.xml). A timer-related task may require checking both the timer and the service it triggers.

### Task 4: Networking and Name Resolution

A host is not behaving correctly on the network. Verify local address state, route selection, name resolution, listening services, and firewall state as needed. Prove the requested connectivity after the fix with a command that exercises the same path the task describes.

Networking tasks often contain misleading symptoms because many layers can produce a connection failure. If a name fails, separate name lookup from transport. If a port fails, separate local listener state from firewall state. If an external host fails, separate route problems from remote service problems.

Use compact commands first so you do not drown in output. `ip -br address`, `ip route`, `getent hosts`, and `ss -ltnp` usually give enough direction for the next step. Save deep packet inspection and large firewall dumps for cases where the first commands point there.

Stop and think: if `ss -ltnp` shows no listener on the requested port, should you edit firewall rules first? No. A firewall rule cannot expose a service that is not listening. Start or fix the service, then verify listener state, then inspect firewall policy if remote access still fails.

### Task 5: Storage, Mounts, and Reboot Survival

A data path needs to be persistent. Identify the requested device or filesystem, mount it at the correct path, configure persistence, and validate with `findmnt`, `df`, a write test, and a safe persistence check such as `mount -a`.

Storage work has a higher blast radius than ordinary file tasks, so slow down enough to identify the device. `lsblk -f` and `blkid` are safer than guessing from device names. If the task gives you a device, verify that you are using that device and not another disk with a similar name.

Use `/etc/fstab` carefully. Create a backup before editing during practice, prefer UUIDs when appropriate, and [test the file with `mount -a` before considering the task complete](https://raw.githubusercontent.com/util-linux/util-linux/master/sys-utils/mount.8.adoc). A line that works only until reboot does not satisfy a persistence requirement.

A complete answer proves both the mounted state and the data path. `findmnt /path` shows the source and options, `df -h /path` shows usable space, and a write-read test proves the path is writable as intended. If permissions matter, test with the correct user identity.

### Task 6: Scheduled Administrative Action

A recurring or one-time administrative action must run automatically. Add the cron entry or `at` job in the correct user context, verify that it exists, prove that the command can run, and remove or preserve it according to the task wording.

The key decision is user context. A root crontab, a user crontab, and a file under `/etc/cron.d` have different syntax and different execution privileges. Read the task closely before choosing the scheduler location.

Use absolute paths in scheduled commands whenever possible. The PATH under cron is often smaller than your interactive shell PATH. A command that works in your terminal may fail silently when scheduled if the executable or output path is not explicit.

Verification should include both schedule presence and command effect when time allows. `crontab -l` proves installation, while a log file, output file, or service state proves execution. If the schedule interval is too long to wait, prove the command manually and prove the schedule exists.

## Pacing Strategy for the Timed Run

Pacing is not only about typing faster. It is about choosing when to inspect, when to change, when to verify, and when to move on. A candidate who types quickly but keeps reopening solved tasks may finish less than a candidate who types steadily and tracks state well.

Use three labels during the run: ready, blocked, and verify. A ready task has a clear next command. A blocked task needs a different idea or should be skipped temporarily. A verify task appears solved but lacks proof. These labels are more useful than vague notes like "almost done."

```text
ready: users task, next command is sudo -u lfcsop1 write test
blocked: service task, journal says permission denied but target file ownership unclear
verify: storage task, mounted now but fstab still needs mount -a test
```

You should expect at least one task to misbehave during the mock. That is not a failed run; that is the point of the mock. The skill is noticing when the task has become a time sink and switching to work that can still produce verified results.

A practical skip rule is based on progress, not emotion. If three inspection commands have not changed your understanding, or if two fixes have failed without producing a new clue, mark the task blocked and move on. When you return later, begin by reading your last note instead of repeating the same commands.

Final review should be mechanical. Read each task, run the verification command, and mark the evidence. Do not make large new changes during the final minutes unless the fix is obvious and low risk. The final review is designed to catch omissions, not to start a new investigation.

## Scoring the Mock

Score the mock in four categories: correctness, verification, pacing, and recovery. Correctness asks whether the final system state matches the task. Verification asks whether you proved the state with meaningful commands. Pacing asks whether your task order protected easy points. Recovery asks whether you handled mistakes without making them worse.

| Category | Strong Performance | Weak Performance | Evidence to Review |
|---|---|---|---|
| Correctness | Requested users, files, services, routes, mounts, and schedules exist in the intended state | Commands were typed but the final state is incomplete or wrong | Final inspection commands and task-by-task state |
| Verification | Each task has an independent check that matches the requirement | Completion is based on memory, command success, or visual guesswork | Notes, shell history, output files, service status |
| Pacing | Easy tasks were completed early and final review time was preserved | One hard task consumed the run while easier work remained untouched | Timestamps, task order, blocked-task notes |
| Recovery | Mistakes were diagnosed, narrowed, and corrected with minimal changes | Fixes became broader, riskier, or unrelated to the symptom | Failed commands, rollback steps, restored files |

Do not score yourself by mood. A stressful run with clear evidence and a precise weakness list is more valuable than a relaxed run where you cannot explain what happened. The debrief converts the run into the next practice plan.

A strong debrief names command families, not personality traits. "I am bad at Linux" is unusable. "I lost twelve minutes because I confused current mounts with fstab persistence" is actionable. The second statement tells you exactly what to rehearse.

Review your shell history after the run, but do not confuse history with proof. Shell history shows what you attempted. The system state shows what survived. Both are useful, and they answer different questions.

```bash
history | tail -n 80
findmnt
systemctl --failed --no-pager
crontab -l 2>/dev/null || true
```

The best retake plan has one or two focused drills, not a vague promise to study everything. If storage persistence failed, do two short fstab drills. If service diagnosis failed, create two broken units and fix them. If pacing failed, rerun the same mock with a stricter skip rule.

## Debrief Questions That Produce Better Practice

The first debrief question is: which task produced the most time without evidence? This identifies where your attention leaked. A task can be hard and still productive if each command reveals something. The problem task is the one where time passed but your understanding did not improve.

The second question is: which verification did you skip or postpone? Skipped verification is often invisible until a reviewer or exam grader finds the mismatch. Naming the skipped proof makes it easier to build a habit next time.

The third question is: which command family needs deliberate practice? File search, archive handling, user management, systemd diagnosis, route inspection, filesystem persistence, and cron syntax each have different muscle memory. The debrief should point to one family for the next short drill.

The fourth question is: what would you do earlier on the retake? This question turns experience into strategy. You may decide to rank storage later, verify users sooner, inspect service logs before editing files, or reserve a longer final review.

The fifth question is: which mistake was caused by task wording rather than command knowledge? Exam tasks often hide important qualifiers such as "persistently," "as this user," "supplementary group," or "after reboot." If wording caused the mistake, practice underlining requirements before touching the terminal.

The final question is: what evidence would convince a skeptical reviewer that each task is complete? This question raises your standard from "I think it works" to "I can prove it works." That shift is central to senior operational behavior.

## What Strong Performance Looks Like

A strong mock run is calm, but not because nothing goes wrong. It is calm because every wrong turn is contained. The candidate reads the symptom, chooses a diagnostic command, learns something, and either fixes the cause or deliberately moves on.

A strong run captures quick wins early. Essential command tasks, simple user changes, and clear scheduled jobs often create momentum. Harder service, networking, or storage tasks can then receive focused attention without the pressure of an untouched backlog.

A strong run verifies with the correct identity. Permission tasks are tested as the target user, not only as root. Service tasks are verified through systemd and logs, not only by editing files. Storage tasks are verified through mount state and fstab behavior, not only by creating a directory.

A strong run leaves a short debrief. The debrief does not need to be elegant. It needs to identify the next practice target. A candidate who can name the weakest command pattern after the mock is already improving faster than one who only repeats full mocks.

A strong run also includes cleanup when appropriate. Practice accounts, loopback mounts, temporary unit files, and cron entries should not remain on a shared machine. Cleanup reinforces the habit that system administration includes lifecycle ownership, not only initial creation.

## Did You Know?

1. LFCS-style performance tasks often reward partial workflow discipline because a candidate who verifies each completed task can protect earned work even when one task remains unresolved.

2. The `/etc/fstab` file has been a source of real production outages because a single bad persistence entry can affect boot behavior long after the original administrator leaves the terminal.

3. Supplementary group changes may not appear inside an already-running login session, which is why testing with a fresh command context such as `sudo -u USER` can reveal different behavior.

4. A systemd oneshot service can complete successfully without staying active, so the right verification depends on the unit type and the task wording rather than a universal "active" expectation.

## Common Mistakes

| Mistake | What Goes Wrong | Better Exam Behavior |
|---|---|---|
| Starting with the task that feels most urgent | One difficult item consumes the run while easier verified points remain untouched | Read all tasks, rank by effort and proof cost, then secure quick wins first |
| Trusting command success without checking state | A command exits successfully but creates the wrong path, user context, archive shape, or mount behavior | Pair every change with an independent verification command that matches the requirement |
| Using root to test a non-root access task | Root can write almost anywhere, so the test does not prove the requested user's access | Use `sudo -u USER` or a fresh user context to perform the actual operation |
| Editing service files before reading logs | The first edit may miss the real failure and make the evidence harder to interpret | Inspect `systemctl status`, `journalctl -u`, and `systemctl cat` before changing anything |
| Confusing current state with persistent state | A mount, service, or route works now but disappears after restart or reload | Verify the runtime state and the persistent owner such as fstab, enabled units, or config files |
| Opening permissions too broadly to make a test pass | The task appears solved, but the system is less secure and may violate the requirement | Apply the narrowest ownership, group, mode, or ACL change that explains the needed access |
| Forgetting cleanup in a practice environment | Mock users, cron entries, mounts, and services remain behind and confuse later runs | Track practice artifacts and remove them after the debrief unless the task says to preserve them |
| Repeating the same failed command without a new hypothesis | Time passes, stress rises, and the failure produces no new information | Change the inspection angle, record the blocker, or move to another task until you can return productively |

## Quiz

1. Your mock begins with six tasks, and the storage task looks familiar but requires editing `/etc/fstab`. The user task and archive task both look straightforward and have obvious verification commands. What order should you choose, and why?

   <details>
   <summary>Answer</summary>

   Start with the archive and user tasks unless the exam wording creates a dependency that changes the risk. They have lower blast radius and faster proof, so completing them first captures verified progress. The storage task may still be important, but fstab changes deserve a slower verification loop that includes a backup and `mount -a`. This answer applies the ranking model: choose tasks by payoff, effort, risk, and verification cost rather than printed order.

   </details>

2. You create a shared directory, set its group correctly, and confirm with `ls -ld` that the mode is `2770`. The target user still cannot create a file there during your test. What should you inspect before changing the mode to something broader?

   <details>
   <summary>Answer</summary>

   Inspect the user's effective groups with `id USER` or `sudo -u USER id`, then inspect every path component with `namei -l /path/to/shared-directory`. The failure may come from missing supplementary group membership, a stale session, or a parent directory without execute permission. Broadening the final directory mode may hide the symptom without fixing the actual access path. The right test is an actual write as the target user after the identity and path checks explain why access should work.

   </details>

3. You fix a systemd unit file by correcting the `ExecStart` path, then immediately restart the service and see the same old failure in the logs. What did you likely forget, and how should you verify the corrected unit is the one systemd sees?

   <details>
   <summary>Answer</summary>

   You likely forgot `systemctl daemon-reload`, which tells systemd to reload changed unit files. After running it, use `systemctl cat UNIT` to confirm the effective unit content includes the corrected `ExecStart`. Then restart the service and check `systemctl status` plus `journalctl -u UNIT -n 20`. The key is verifying the manager's loaded view, not only the file you edited.

   </details>

4. A networking task says users cannot reach `app.internal` on port 8080. `getent hosts app.internal` returns an address, but `curl http://app.internal:8080` fails. What is a good next diagnostic sequence?

   <details>
   <summary>Answer</summary>

   Since name resolution works, move to transport and service checks. Inspect the route with `ip route get ADDRESS` if available, check local or target listener state with `ss -ltnp` when you are on the host that should serve the port, and inspect firewall rules only after confirming that the service is actually listening. If the service is remote, use a connection test such as `nc -vz app.internal 8080` if available. The sequence avoids changing DNS because DNS has already produced an address.

   </details>

5. You mount a filesystem at `/data`, write a proof file, and `df -h /data` looks correct. The task explicitly says the mount must survive reboot. What additional verification should you perform before marking the task complete?

   <details>
   <summary>Answer</summary>

   Verify the persistence configuration, usually `/etc/fstab`, and test it safely with `mount -a` after backing up the file during practice. Also use `findmnt /data` to confirm the source and options. A current mount plus a write test proves runtime behavior, but it does not prove reboot survival. Persistence requires checking the configuration that will be used later.

   </details>

6. A cron task works when you run the command manually, but the scheduled output file never appears. What differences between your shell and cron should you evaluate?

   <details>
   <summary>Answer</summary>

   Check whether the cron service is active, whether the entry is installed for the correct user, whether the command uses absolute paths, and whether the output path is writable by the scheduled user. Cron runs with a smaller environment than an interactive shell, so PATH, working directory, and permissions often differ. Verify with `crontab -l`, service inspection, and a command written with explicit executable and output paths.

   </details>

7. During final review, you find that a service task is still failing, but three other tasks are complete and verified. You have only a few minutes left. What should you do with the remaining time?

   <details>
   <summary>Answer</summary>

   Protect the verified work first by running the final proof commands for the completed tasks and ensuring no cleanup or persistence step is missing. If the service fix is obvious and low risk, apply it and verify quickly; otherwise, record it as unresolved rather than making broad changes that could damage other results. The final review phase is for evidence and small corrections, not for starting a risky investigation under severe time pressure.

   </details>

## Hands-On Exercise

**Task**: Run a full LFCS-style mock exam in a disposable Linux environment, using the six task domains from this module and producing evidence for each completed item.

### Step 1: Build the practice workspace

Create a mock workspace under your home directory, add sample files, and prepare a short task tracker. The purpose of this step is to remove setup ambiguity before the timer starts, not to solve the mock in advance.

```bash
mkdir -p ~/lfcs-mock/{docs,logs,archives,restore,cron-output,storage}
printf 'platform team owns this file\n' > ~/lfcs-mock/docs/ownership.txt
printf 'service warning: missing executable\n' > ~/lfcs-mock/logs/service.log
printf 'network target: localhost\n' > ~/lfcs-mock/docs/network.txt
printf '[ ] essential commands\n[ ] users and permissions\n[ ] service\n[ ] networking\n[ ] storage\n[ ] scheduled task\n' > ~/lfcs-mock/mock-notes.txt
```

Success criteria:

- [ ] The directory `~/lfcs-mock` exists with separate subdirectories for docs, logs, archives, restore tests, cron output, and storage practice.
- [ ] The file `~/lfcs-mock/mock-notes.txt` contains one trackable line for each of the six mock task domains.
- [ ] You can explain which practice artifacts are local files and which later steps may change global system state.

### Step 2: Perform the first-pass ranking

Read the six domain tasks in this module and write a ranked order into your notes before changing the system. Include at least one verification command next to each task. This step trains the habit of planning by proof, not by anxiety.

```bash
{
  printf '\nRanked order:\n'
  printf '1. essential commands - verify with grep output, tar listing, restore diff\n'
  printf '2. users and permissions - verify with id, namei, sudo -u write test\n'
  printf '3. scheduled task - verify with crontab -l and output file\n'
  printf '4. service - verify with systemctl, journalctl, service-specific output\n'
  printf '5. networking - verify with ip, getent, ss, curl or nc\n'
  printf '6. storage - verify with findmnt, df, mount -a, proof file\n'
} >> ~/lfcs-mock/mock-notes.txt
```

Success criteria:

- [ ] Your ranked order appears in `~/lfcs-mock/mock-notes.txt` before you perform system-changing work.
- [ ] Every task line names at least one verification command that would prove completion.
- [ ] Your ranking identifies at least one task as higher risk because it affects persistence, service state, or global access.

### Step 3: Complete and verify the essential-commands task

Find the file containing the phrase `platform team`, save the matching line, create a compressed archive of the docs directory, list the archive, restore it into a clean directory, and compare one restored file with the original.

```bash
grep -R "platform team" ~/lfcs-mock/docs > ~/lfcs-mock/result-essential.txt
tar -czf ~/lfcs-mock/archives/docs.tgz -C ~/lfcs-mock docs
tar -tzf ~/lfcs-mock/archives/docs.tgz
rm -rf ~/lfcs-mock/restore/docs
tar -xzf ~/lfcs-mock/archives/docs.tgz -C ~/lfcs-mock/restore
diff -u ~/lfcs-mock/docs/ownership.txt ~/lfcs-mock/restore/docs/ownership.txt
```

Success criteria:

- [ ] The file `~/lfcs-mock/result-essential.txt` contains the matching line and the source path that produced it.
- [ ] The archive `~/lfcs-mock/archives/docs.tgz` lists a predictable `docs/...` path rather than an accidental absolute path.
- [ ] The restored file comparison succeeds without output from `diff`, proving the archive can recreate the content.

### Step 4: Complete and verify the users-and-permissions task

Create a practice group and user if your disposable environment allows it, then create a shared directory and verify access as the target user. If you cannot create users in your environment, write the exact commands and explain which verification would prove the result.

```bash
sudo groupadd lfcsops 2>/dev/null || true
id lfcsop1 2>/dev/null || sudo useradd -m -s /bin/bash -G lfcsops lfcsop1
sudo usermod -aG lfcsops lfcsop1
sudo mkdir -p /srv/lfcsops
sudo chown root:lfcsops /srv/lfcsops
sudo chmod 2770 /srv/lfcsops
id lfcsop1
namei -l /srv/lfcsops
sudo -u lfcsop1 bash -c 'printf "user access ok\n" > /srv/lfcsops/proof.txt'
ls -l /srv/lfcsops/proof.txt
```

Success criteria:

- [ ] The command `id lfcsop1` shows the user as a member of the `lfcsops` group.
- [ ] The directory `/srv/lfcsops` is owned by group `lfcsops` and has permissions that support controlled group collaboration.
- [ ] A file write performed as `lfcsop1`, not as root, succeeds inside `/srv/lfcsops`.

### Step 5: Complete and verify the service task

Create or inspect a harmless service failure, identify the cause through systemd output and logs, apply the smallest correction, and verify the final service result. Use the worked example service if your lab allows creating unit files.

```bash
sudo tee /etc/systemd/system/lfcs-mock.service >/dev/null <<'EOF'
[Unit]
Description=LFCS mock service for hands-on practice

[Service]
Type=oneshot
ExecStart=/usr/local/bin/lfcs-mock-start

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl start lfcs-mock.service || true
systemctl status lfcs-mock.service --no-pager || true
journalctl -u lfcs-mock.service -n 20 --no-pager || true
```

```bash
sudo tee /usr/local/bin/lfcs-mock-start >/dev/null <<'EOF'
#!/usr/bin/env bash
printf 'service proof %s\n' "$(date -Is)" >> /tmp/lfcs-mock-service-proof.log
EOF
sudo chmod 755 /usr/local/bin/lfcs-mock-start
sudo systemctl start lfcs-mock.service
systemctl show lfcs-mock.service -p ActiveState -p SubState -p Result
tail -n 5 /tmp/lfcs-mock-service-proof.log
```

Success criteria:

- [ ] You captured the original failure with `systemctl status` or `journalctl` before applying the fix.
- [ ] The fixed service reports a successful result that matches its oneshot service type.
- [ ] The service-specific proof file shows that the intended command actually ran.

### Step 6: Complete and verify the networking task

Inspect local network state in layers, then prove at least one meaningful connectivity path. If your environment does not expose a real remote target, use localhost and focus on separating address, route, name resolution, listener state, and application request.

```bash
ip -br address
ip route
getent hosts localhost
ss -ltnp 2>/dev/null | head -n 20
curl -I http://127.0.0.1/ 2>/dev/null || true
```

Success criteria:

- [ ] You recorded local address and route information before making any network-related change.
- [ ] You tested name resolution separately from application connectivity.
- [ ] Your final proof command exercises the same path described by your chosen networking task.

### Step 7: Complete and verify the storage task

Use a loopback filesystem in a disposable environment to practice mounting, writing proof data, and testing persistence syntax. Back up `/etc/fstab` before editing, and restore it during cleanup if this is only a practice run.

```bash
dd if=/dev/zero of=~/lfcs-mock/storage/data.img bs=1M count=64
mkfs.ext4 -F ~/lfcs-mock/storage/data.img
sudo mkdir -p /mnt/lfcs-data
sudo mount -o loop ~/lfcs-mock/storage/data.img /mnt/lfcs-data
findmnt /mnt/lfcs-data
df -h /mnt/lfcs-data
printf 'storage proof\n' | sudo tee /mnt/lfcs-data/proof.txt >/dev/null
cat /mnt/lfcs-data/proof.txt
```

```bash
sudo cp /etc/fstab /etc/fstab.lfcs-mock.bak
UUID_VALUE="$(sudo blkid -s UUID -o value ~/lfcs-mock/storage/data.img)"
printf 'UUID=%s /mnt/lfcs-data ext4 loop,defaults 0 0\n' "$UUID_VALUE" | sudo tee -a /etc/fstab
sudo mount -a
findmnt /mnt/lfcs-data
```

Success criteria:

- [ ] The mount point `/mnt/lfcs-data` is backed by the loopback filesystem, as shown by `findmnt`.
- [ ] A proof file can be written and read through the mounted path.
- [ ] The fstab configuration is tested with `mount -a`, and you can restore the backup during cleanup.

### Step 8: Complete and verify the scheduled-task item

Create a cron entry that writes timestamps to your mock workspace, verify the entry exists, wait long enough for one run, and inspect the output. Then remove only the mock line so unrelated crontab content is preserved.

```bash
CRON_FILE="$(mktemp)"
crontab -l 2>/dev/null > "$CRON_FILE" || true
printf '* * * * * /usr/bin/date -Is >> %s/lfcs-mock/cron-output/timestamps.log\n' "$HOME" >> "$CRON_FILE"
crontab "$CRON_FILE"
rm -f "$CRON_FILE"
crontab -l
sleep 70
tail -n 5 ~/lfcs-mock/cron-output/timestamps.log
```

```bash
crontab -l | grep -v 'lfcs-mock/cron-output/timestamps.log' | crontab -
crontab -l 2>/dev/null || true
```

Success criteria:

- [ ] The crontab contains the scheduled mock command before you wait for execution.
- [ ] The output file under `~/lfcs-mock/cron-output` contains at least one timestamp created by the scheduled command.
- [ ] Cleanup removes the mock cron line without intentionally destroying unrelated scheduled entries.

### Step 9: Debrief and create a retake plan

Review the notes, final command outputs, and shell history from the run. Identify the single weakest domain and schedule a focused drill before repeating the full mock. The point of the debrief is to choose a next action, not to write a long diary.

```bash
{
  printf '\nDebrief:\n'
  printf 'Longest task:\n'
  printf 'Weakest command family:\n'
  printf 'Skipped or late verification:\n'
  printf 'Task to drill before retake:\n'
} >> ~/lfcs-mock/mock-notes.txt
tail -n 30 ~/lfcs-mock/mock-notes.txt
```

Success criteria:

- [ ] Your debrief names the task that consumed the most time without producing evidence.
- [ ] Your retake plan identifies one command family to drill before running the full mock again.
- [ ] Your notes distinguish between completed tasks, verified tasks, and tasks that were only partially attempted.

### Step 10: Clean up practice artifacts where appropriate

Remove practice services, restore fstab if you edited it only for the lab, unmount loopback storage, and decide whether the practice user should remain. Cleanup is part of the exercise because administrators own the lifecycle of the changes they make.

```bash
sudo systemctl disable --now lfcs-mock.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/lfcs-mock.service /usr/local/bin/lfcs-mock-start
sudo systemctl daemon-reload
sudo cp /etc/fstab.lfcs-mock.bak /etc/fstab 2>/dev/null || true
sudo umount /mnt/lfcs-data 2>/dev/null || true
sudo rm -f /tmp/lfcs-mock-service-proof.log
```

Success criteria:

- [ ] The mock systemd unit and helper script are removed, and systemd has been reloaded after removal.
- [ ] Any practice fstab edit has either been intentionally preserved for the lab or restored from the backup.
- [ ] You can rerun the mock later without stale services, mounts, or cron entries confusing the next attempt.

## Next Module

This is the final module in the LFCS sequence; continue by returning to the [LFCS track overview](./) and scheduling a timed retake based on your debrief.

## Sources

- [Linux Foundation LFCS Important Instructions](https://docs.linuxfoundation.org/tc-docs/certification/instructions-lfcs-and-lfce) — Authoritative source for LFCS exam format, timing, and performance-based structure.
- [systemd.service unit configuration reference](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.service.xml) — Primary reference for `Type=oneshot`, `RemainAfterExit`, and service-state verification details.
- [util-linux mount(8) reference](https://raw.githubusercontent.com/util-linux/util-linux/master/sys-utils/mount.8.adoc) — Primary reference for UUID-vs-device-name guidance and `mount -a` behavior when checking persistence.
