---
revision_pending: false
title: "LFCS Running Systems and Networking Practice"
slug: k8s/lfcs/module-1.3-running-systems-and-networking-practice
sidebar:
  order: 103
---

> **LFCS Track** | Complexity: `[COMPLEX]` | Time: 45-60 min | Kubernetes target: 1.35+. This practice module focuses on Linux host operations that also support reliable Kubernetes node administration.

**Reading Time**: 45-60 minutes, depending on whether you only read the chapter or also run the drills in a disposable lab environment.

## Prerequisites

Before starting this module, make sure you can navigate a shell, edit text files safely, and recognize basic process, service, and networking terminology from the prerequisite lessons:
- **Required**: [LFCS Exam Strategy and Workflow](../module-1.1-exam-strategy-and-workflow/)
- **Required**: [LFCS Essential Commands Practice](../module-1.2-essential-commands-practice/)
- **Helpful**: [Module 1.2: Processes & systemd](/linux/foundations/system-essentials/module-1.2-processes-systemd/)
- **Helpful**: [Module 3.1: TCP/IP Essentials](/linux/foundations/networking/module-3.1-tcp-ip-essentials/)
- **Helpful**: [Module 3.2: DNS on Linux](/linux/foundations/networking/module-3.2-dns-linux/)
- **Helpful**: [Module 3.4: iptables & netfilter](/linux/foundations/networking/module-3.4-iptables-netfilter/)

## Learning Outcomes

After this module, you will be able to perform these exam-style tasks with evidence rather than guesswork:
- diagnose systemd service failures using process state, unit status, and journal evidence
- evaluate boot targets, rescue modes, and shutdown actions without making recovery harder
- implement cron and at scheduled tasks with verification, access-control checks, and cleanup
- compare temporary routing fixes with persistent Netplan or NetworkManager configuration
- inspect, load, unload, persist, and blacklist kernel modules with clear operational evidence

## Why This Module Matters

Hypothetical scenario: you sit down at an LFCS terminal and the task says a web service must start at boot and listen on the expected port. The symptom looks simple, but several different faults can produce the same visible failure: the process may be stopped, the unit may be disabled, the configuration may fail validation, the port may already be taken, the address may not exist, or the route back to the client may be missing. A candidate who immediately edits files is guessing. A candidate who first reads process state, unit state, logs, networking state, and persistence state is building a chain of evidence.

This module trains that evidence chain. LFCS running-system work is not about memorizing every possible daemon; it is about using the same small set of Linux inspection tools in a disciplined order. You will practice how to read `systemctl status` without treating the first red line as the whole answer, how to use `journalctl` to separate a service failure from a dependency failure, how to schedule jobs in a way you can prove, and how to decide whether a route or module change must survive reboot. The same habits also transfer directly into Kubernetes operations, where a broken node service, disabled runtime dependency, or incorrect host route can make cluster symptoms look much larger than they are.

The exam pressure matters because the wrong move is often more expensive than waiting ten seconds to inspect. Rebooting early can erase useful state, restarting repeatedly can rotate away the most relevant log line, and editing persistent network configuration before proving a runtime route can strand your session. The goal here is not to move slowly; it is to move in a sequence that preserves your options. When you can explain what changed, why it changed, and how you verified it, you stop treating recovery as luck.

This section covers SSH client reachability; `sshd_config` server hardening (`PermitRootLogin`, host keys) is practiced in the full mock exam (module 1.5) and the Linux track.

## Diagnose systemd Service Failures with Evidence

Running-system diagnosis starts with a simple distinction: a process is a running program, while a `systemd` unit is the manager's record of how that program should be started, stopped, restarted, and connected to dependencies. LFCS tasks often blur those two layers. A daemon can be running even when the unit is disabled for boot, a unit can be enabled even when the process is currently dead, and a process can be alive but bound to the wrong port. If you treat the process list as the truth, you miss persistence. If you treat `systemctl status` as the only truth, you may miss an unrelated process that owns the socket.

The first pass is deliberately small. Look for the process, identify its command line, decide whether it is healthy enough to keep, and only then take action. `kill -TERM` asks the process to exit cleanly, which gives it a chance to flush files and release locks. `kill -KILL` is the last resort because the kernel terminates the process immediately. `nice` and `renice` do not fix a failed service, but they matter in exam scenarios where a background job consumes CPU and makes the machine feel broken while core services are technically healthy.

```bash
ps aux | grep nginx   # also matches the grep process itself; pgrep is cleaner
top
pgrep -a ssh
kill -TERM <pid>
kill -KILL <pid>
nice -n 10 long-job
renice 5 -p <pid>
```

Once you have process evidence, move to the unit. `systemctl status` is useful because it combines active state, recent logs, the main PID, the loaded unit file, and enabled state hints in one view. Do not stop at the word `failed`; read the line that says whether the unit file loaded correctly, the exit code, and the last journal entries. The control commands below are intentionally ordinary because ordinary commands are what you need under time pressure. Starting and restarting test current behavior, while enabling and disabling test boot behavior.

```bash
systemctl status ssh
systemctl start nginx
systemctl stop nginx
systemctl enable nginx
systemctl disable nginx
systemctl restart nginx
systemctl list-units --type=service
systemctl get-default
systemctl set-default multi-user.target
```

Logs are the evidence that keeps the investigation honest. `journalctl -u nginx` narrows the journal to the unit, which is usually better than searching the whole boot for a familiar word. `journalctl -xe` can expose dependency errors, permission problems, and policy messages near the current failure, but it can also show unrelated noise if you do not anchor it to the unit or boot. `journalctl -b -1` is especially valuable after a reboot because it lets you inspect the previous boot instead of pretending the current state contains all history.

```bash
journalctl -u nginx
journalctl -xe
journalctl -b
journalctl -b -1
systemctl --failed
systemctl isolate rescue.target
shutdown -r +5 "LFCS practice reboot"
shutdown -c
```

Pause and predict: if `systemctl status nginx` says the unit failed but `ss -tlnp` shows another process already listening on port 80, should you edit the Nginx configuration first or identify the listener first? The better answer is to identify the listener, because the service may be correctly configured but unable to bind the port. Editing configuration without proving the socket conflict can turn one fault into two faults, and two faults are much harder to unwind during a timed exam.

Use a running-system troubleshooting ladder to keep that discipline visible while you move from what is currently executing toward what should survive the next boot:

1. process
2. unit
3. log
4. config
5. network
6. persistence

The ladder is not a law, but it is a good default. Process state tells you what is happening right now, unit state tells you what the service manager thinks should happen, logs tell you why a transition succeeded or failed, configuration tells you what the program was asked to do, network checks tell you whether the service can be reached, and persistence checks tell you whether the fix survives reboot. When the task is vague, following the ladder prevents the common exam failure of changing three things before verifying any one of them.

Authoring unit files from scratch (`[Unit]`/`[Service]`/`ExecStart`, `daemon-reload`) is practiced in [Linux: Processes & systemd](/linux/foundations/system-essentials/module-1.2-processes-systemd/).

There is another reason to keep the ladder explicit: it gives you a defensible stopping point. If a service is active, enabled, logging cleanly, and listening on the expected address, you do not need to keep editing simply because the original symptom made you nervous. If the service is active but the port is closed, you know the next layer is socket ownership or service configuration. If the port is open but the client still cannot connect, you know the next layer is routing, firewall policy, or name resolution. This is how you convert a vague failure into a small set of testable claims.

The same habit protects you from overfitting to familiar services. You may have practiced with SSH or Nginx, but LFCS can ask about any service installed in the environment. The unit names, configuration paths, and ports may change, yet the diagnostic shape remains stable. Identify the process, read the unit, inspect the unit journal, validate the intended configuration, prove the network path, and verify persistence only when the task asks for it. That approach scales because it relies on Linux interfaces rather than on service-specific folklore.

Exercise scenario: a service that used to start now fails immediately after a configuration edit. A good repair workflow is to read `systemctl status`, inspect the unit-specific journal, find the exact parser or permission error, fix only the smallest configuration mistake, restart once, and verify both the active state and the listening socket. That sequence also gives you a clean rollback point. If your first fix does not work, you know which evidence changed and which evidence stayed the same.

### Worked Service Drill

Drill 1, Rescue a Failing Service, should be practiced in a disposable virtual machine or lab node. Simulate a broken service by stopping a service, changing its configuration in a way that prevents startup, and then using `systemctl status` plus `journalctl` to find the failure before you edit again. The learning target is not the specific daemon. The target is the habit of reading service state, using logs as evidence, and making the smallest correction that restores the expected state.

When you repeat the drill, vary the fault. Make one failure a syntax error, one a missing directory, one a permission problem, and one a port conflict. The commands do not change much, but your interpretation changes. That is the point: LFCS is testing whether you can reason from evidence, not whether you have memorized every possible error string. Before running the restart, ask yourself what output you expect from `systemctl status` and what port or process evidence will prove the repair.

## Evaluate Boot Targets Logs and Recovery State

Boot targets describe the operating mode that `systemd` is trying to reach. They replace the old habit of thinking only in SysV runlevels, but the mapping still matters because exam materials and older documentation may mention both. The important distinction is current runtime state versus boot default. `systemctl isolate rescue.target` changes the current system state now. `systemctl set-default multi-user.target` changes what the machine will attempt on future boots. Mixing those up is a reliable way to make a temporary recovery step become a persistent problem.

The exam assumes you can read this mapping without turning it into trivia, because each target describes an operational state you may need during recovery:

| Target | Old Runlevel | Purpose |
|--------|-------------|---------|
| `poweroff.target` | 0 | Halt the system |
| `rescue.target` | 1 | Single-user, minimal services |
| `multi-user.target` | 3 | Full multi-user, no GUI |
| `graphical.target` | 5 | Multi-user with display manager |
| `reboot.target` | 6 | Reboot |
| `emergency.target` | — | Minimal root shell, no services |

`rescue.target` and `emergency.target` are close enough to confuse people and different enough to matter. Rescue mode mounts local filesystems and starts a minimal set of services so you can repair users, packages, logs, and configuration with some system support. Emergency mode gives you a much smaller root shell, often before the normal dependency graph is available, which makes it useful when rescue itself depends on broken state. Choose the least severe target that gives you the access you need, because every step downward removes conveniences you may need for diagnosis.

Think of targets as agreements about how much of the system you want `systemd` to assemble. A full multi-user target says the machine should support normal non-graphical operation, which usually includes networking, logging, and remote access. A rescue target says you want enough structure to repair the system but not the full application surface. An emergency target says the normal structure itself may be part of the problem. Those agreements matter because a recovery command should reduce complexity only as far as necessary. Dropping below the needed target can make the next command harder, especially if networking or logging disappears.

```bash
# Runtime — switch now without changing default
systemctl isolate rescue.target

# Persistent — change what boots next time
systemctl set-default multi-user.target
systemctl get-default

# GRUB override — append to kernel command line during boot:
# systemd.unit=rescue.target
```

Shutdown control is part of recovery discipline, not an afterthought. Scheduling a reboot with a message gives connected users and your future self a clear signal, while `shutdown -c` gives you a way to cancel after you realize the reboot is unnecessary. In an exam environment, that matters because the clock keeps running and a reboot may hide the log line you needed. In production environments, the same habit prevents avoidable disruption when a service restart or target isolate would have solved the immediate issue.

Drill 2, Rebuild a Boot Target, starts by recording the current default target with `systemctl get-default`. Then set `multi-user.target` as the default, confirm it, isolate into `rescue.target` only in a disposable VM, switch the default back to its original value, and inspect previous boot logs with `journalctl -b -1`. This trains boot-target fluency and recovery without blind rebooting. It also forces you to distinguish a runtime transition from a persistent default, which is the exact distinction many candidates lose under pressure.

Drill 7, Shutdown and Recovery Discipline, extends the same idea. Inspect the default target, switch to `multi-user.target`, isolate into `rescue.target` in a disposable practice environment, schedule a reboot, cancel the reboot, and inspect both current and previous boot logs. Treat each action as a state transition that needs verification. If you can describe the before state, the command, the after state, and the rollback, you are working like an operator rather than a command collector.

When practicing boot recovery, write down the original default target before changing anything. That sounds basic, but it prevents a subtle failure mode: you successfully repair the immediate issue and leave the machine configured to boot into a reduced mode forever. The exam may not reboot the machine for you, so you need to verify the durable state yourself. In real operations, the same mistake creates a delayed incident because the machine behaves normally until the next maintenance reboot. A good recovery note therefore includes the current target, default target, command used, reason for the command, and the command that restores the original default.

## Implement Cron and At Scheduled Tasks

Scheduling tasks is deceptively simple because the command syntax is short, but the operational risk sits around it. A cron entry can run as the wrong user, write to a path that only exists in your login shell, depend on environment variables that cron never receives, or keep running after the test is over because you forgot cleanup. An `at` job can be queued correctly and still fail later because the command was quoted incorrectly or access control denies the user. Verification is therefore part of the task, not an optional cleanup step.

The first scheduling decision is whether the task repeats. If it repeats, cron is usually the right interface because the schedule is part of the configuration. If it happens once, `at` is clearer because the queue expresses a single future action. Avoid turning one-time work into cron plus manual cleanup unless the task explicitly asks for recurring behavior. A recurring job that should have been one-time is a delayed failure waiting to happen, while a one-time job that should have been recurring silently stops after the first run. Good scheduling starts with that intent, then moves to syntax.

The five cron fields are easier to remember when you read them from small to large time units. Minute comes first, then hour, day of month, month, and day of week. Day of week accepts both 0 and 7 for Sunday on many systems, but you should avoid clever expressions during the exam unless the task requires them. A plain schedule you can explain is better than a compact expression you cannot verify quickly.

```text
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-7, 0 and 7 = Sunday)
│ │ │ │ │
* * * * *  command
```

These common patterns cover most practice tasks. Notice that the command path is absolute in every example. Cron does not run inside your interactive shell, so assuming a custom `PATH` is a common source of silent failure. If a script needs environment variables, put them in the crontab or in the script itself where you can inspect them. If the job writes output, redirect it to a file you can check; otherwise you may have no quick evidence that it ran.

```bash
# every 15 minutes
*/15 * * * * /usr/local/bin/healthcheck.sh

# daily at 2:30 AM
30 2 * * * /usr/local/bin/backup.sh

# every Monday at 6 AM
0 6 * * 1 /usr/local/bin/weekly-report.sh

# first of every month at midnight
0 0 1 * * /usr/local/bin/monthly-rotate.sh
```

User crontabs and system-wide cron directories solve different problems. `crontab -e` edits the current user's scheduled jobs, while `sudo crontab -u alice -e` edits another user's jobs. Files in `/etc/cron.d/` are drop-ins with their own format, and scripts in `/etc/cron.daily/`, `/etc/cron.hourly/`, and similar directories are managed by the system's periodic scheduling setup. For LFCS, know how to inspect each place before assuming a job is missing. A duplicate job in the wrong location can look like a daemon bug when it is really a scheduling bug.

```bash
crontab -e                  # edit current user's crontab
crontab -l                  # list current user's crontab
crontab -r                  # remove current user's crontab
sudo crontab -u alice -e    # edit another user's crontab
sudo crontab -u alice -l    # list another user's crontab
```

```bash
ls /etc/cron.d/             # drop-in cron files
ls /etc/cron.daily/         # scripts that run daily
ls /etc/cron.hourly/        # scripts that run hourly
ls /etc/cron.weekly/        # scripts that run weekly
```

`at` is the tool for one-time scheduling. It is useful for delayed cleanup, maintenance windows, and exam tasks that ask for a command to run once rather than forever. The workflow is queue, list, inspect, and remove if necessary. `at -c` is particularly useful because it shows the generated job, including the environment captured when it was submitted. That inspection step catches quoting mistakes before you wait for the job to fail.

```bash
echo "/usr/local/bin/cleanup.sh" | at now + 30 minutes
echo "/usr/local/bin/migrate.sh" | at 02:00 tomorrow
atq                         # list pending at jobs
atrm 3                      # remove job number 3
at -c 3                     # show job 3 contents
```

Access control files can change the answer even when your syntax is perfect. If `/etc/at.allow` exists, only listed users can use `at`; if it does not exist, `/etc/at.deny` blocks listed users. Cron has similar allow and deny files. Do not memorize this as a footnote. In a troubleshooting task, a denied user may see a scheduling failure that looks unrelated to the command being scheduled.

```bash
cat /etc/at.allow           # if this exists, only listed users can use at
cat /etc/at.deny            # if allow doesn't exist, deny blocks listed users
cat /etc/cron.allow
cat /etc/cron.deny
```

Pause and predict: if a cron job works when you paste the command into your shell but never writes its output from cron, what is your first hypothesis? The strongest first hypothesis is environment or path, not a broken cron daemon. Check the crontab entry, use absolute paths, redirect output and errors, and confirm which user owns the job before restarting services. Restarting cron may be appropriate later, but it is rarely the first useful piece of evidence.

Drill 3, Schedule Work, should use both cron and at with full verification. For cron, run `crontab -l`, add a job that appends `heartbeat` to `/tmp/cron-test.log` every five minutes, verify the entry, wait for one run, inspect the file, remove the job, and confirm removal. For `at`, queue a one-time command that writes `/tmp/at-test.log`, list it with `atq`, inspect it with `at -c`, verify the file after execution, and remove the file. For access control, inspect allow and deny files, test with a disposable user if your lab allows it, and restore the files exactly.

Notice that the verification is deliberately external to the scheduler. Listing a crontab proves the entry exists, but it does not prove the command ran. Seeing an `at` job in the queue proves submission, but it does not prove the future command will produce the intended file. Redirecting output to `/tmp` in a lab gives you a concrete artifact to inspect, and removing that artifact afterward proves cleanup. This is the same evidence model used for services and routes: configuration is not behavior until the system performs the behavior and you observe it.

## Compare Temporary Routing Persistent Networking and Kernel Modules

Network triage should move from local evidence outward. Start with link state and addresses, then route selection, then name resolution, then service reachability. If you start with DNS every time, you will misdiagnose missing routes as resolver failures. If you start by editing persistent configuration, you may make a runtime-only issue survive reboot. The command ladder below is intentionally plain because these tools work across many distributions and reveal different layers of the path.

The route table is the kernel's forwarding plan, not just a list of administrator intentions. `ip route show` tells you the installed routes, while `ip route get` asks which route the kernel would choose for a specific destination. That difference is useful when multiple routes overlap. A broad default route may exist, but a more specific route can still direct a lab network through another gateway. If the selected route is wrong, fixing DNS will not help because packets are already taking the wrong path before a name matters.

```bash
ip addr
ip route
ip route add 10.20.30.0/24 via 192.168.1.1
ip route del 10.20.30.0/24 via 192.168.1.1
ss -tulpen
ping -c 3 8.8.8.8
getent hosts example.com
nmcli device status
systemctl is-enabled NetworkManager
```

Use the output as a sequence of questions. Does the interface have the address you expected? Does the route table choose the gateway you expected? Can the host reach an IP address without DNS? Does `getent hosts` resolve the name through the system's configured resolver path? Resolver files (`/etc/resolv.conf`) and `resolvectl` are covered in [Module 3.2: DNS on Linux](/linux/foundations/networking/module-3.2-dns-linux/); this module stays at `getent hosts`-level name checks. Is a service actually listening on the port you expect, and is it enabled for boot if the task asks for persistence? These questions keep route, DNS, firewall, and service failures from collapsing into a vague statement like "networking is broken."

Service reachability has both a local and a remote side. Locally, `ss` can prove that a daemon is listening on an address and port, but it cannot prove that a remote client can traverse the path. Remotely, a connection failure may reflect routing, firewall policy, service binding, or authentication. Keep those layers separate. If a service listens only on `127.0.0.1`, a remote client cannot reach it even though the local socket looks healthy. If a service listens on the expected address but remote traffic fails, the next question is the path between client and server.

Temporary routes are for proving the path. Persistent routes are for making a proven path survive reboot. That distinction is one of the most valuable exam habits in this module. Add a temporary route with `ip route`, verify route selection with `ip route get`, and remove it cleanly when the test is finished. Only after the route proves the intended behavior should you translate it into Netplan or NetworkManager configuration. The translation step is not diagnosis; it is persistence.

```bash
# Add a route
sudo ip route add 10.20.30.0/24 via 192.168.1.1

# Add a default gateway
sudo ip route add default via 192.168.1.1

# Verify
ip route show
ip route get 10.20.30.5

# Remove
sudo ip route del 10.20.30.0/24 via 192.168.1.1
```

Netplan is common on Ubuntu 22.04 systems, and NetworkManager is common on desktop-style or general-purpose installations. The LFCS skill is not loyalty to one tool; it is recognizing what manages the current interface and making the persistent change in the right place. If Netplan owns the interface, write valid YAML and apply it. If NetworkManager owns the profile, modify the active connection profile and bring it up. In either case, verify the route table afterward instead of trusting the configuration file.

Be careful with interface names in persistent examples. A sample such as `ens33` teaches the shape of the YAML, not a universal interface name. Your lab may use `ens160`, `enp0s3`, `eth0`, or another predictable name. Always read the actual interface from `ip addr` or the active connection profile before writing persistence. A valid YAML file with the wrong interface name can apply cleanly and still fail to change the route you care about. This is one of the reasons runtime proof comes before persistence.

```yaml
# /etc/netplan/01-static-routes.yaml
network:
  version: 2
  ethernets:
    ens33:
      routes:
        - to: 10.20.30.0/24
          via: 192.168.1.1
```

```bash
sudo netplan apply
ip route show | grep 10.20.30
```

```bash
sudo nmcli connection modify "Wired connection 1" +ipv4.routes "10.20.30.0/24 192.168.1.1"
sudo nmcli connection up "Wired connection 1"
```

Network services add a second persistence question. A service can be listening now but disabled for the next boot, or enabled for boot but currently failed. Check both. For SSH, for example, `systemctl is-enabled ssh` answers the boot question, while `ss -tlnp | grep :22` answers the runtime socket question. A correct answer to an exam task usually needs both pieces of evidence when the wording says the service must be available after reboot.

```bash
# Check what manages networking
systemctl is-active NetworkManager
systemctl is-active systemd-networkd

# Ensure the right service is enabled at boot
systemctl is-enabled NetworkManager
sudo systemctl enable NetworkManager

# Check a specific network-facing service
systemctl is-enabled ssh
sudo systemctl enable --now ssh
ss -tlnp | grep :22
```

```bash
# After enabling, confirm the symlink exists
ls -l /etc/systemd/system/multi-user.target.wants/ | grep ssh

# Or use:
systemctl list-unit-files --type=service --state=enabled | grep ssh
```

Kernel modules are another place where runtime and persistence diverge. `lsmod` shows what is loaded now, `modinfo` explains what a module is and which parameters it accepts, and `modprobe` loads or unloads by name while resolving dependencies. Prefer `modprobe` over `insmod` for exam work because `insmod` loads a file path directly and does not resolve dependencies. The safe workflow is inspect, load, verify, use, unload if required, and only then decide whether persistence or blacklisting is part of the task.

Modules also force you to think about evidence from the kernel's point of view. A configuration file can request loading, but `lsmod` shows whether the module is actually resident now. A blacklist file can prevent automatic loading, but a manually loaded module may still appear until it is removed. A parameter in a command line can look correct, but `/sys/module` is the stronger place to confirm the active value when the module exposes it. Treat every module task as two questions: what is configured, and what is the kernel currently doing?

```bash
lsmod                           # list all loaded modules
lsmod | grep '^dummy'           # check if a specific module is loaded
modinfo dummy                   # show module description, parameters, dependencies
sudo modprobe dummy             # load module (resolves dependencies automatically)
sudo modprobe -r dummy          # unload module
```

Persistent module loading uses `/etc/modules-load.d/`, while blacklisting uses `/etc/modprobe.d/`. They solve opposite problems, so do not confuse them. Loading at every boot is useful for a required driver or virtual interface module. Blacklisting prevents automatic loading when a module causes unwanted behavior or conflicts with the intended driver. In both cases, the file is only part of the answer; you still need runtime evidence from `lsmod`, `modinfo`, or `/sys/module`.

```bash
# Load at every boot — add a file in /etc/modules-load.d/
echo "dummy" | sudo tee /etc/modules-load.d/dummy.conf

# Verify the file is in place
cat /etc/modules-load.d/dummy.conf
```

```bash
# Prevent a module from loading automatically
echo "blacklist pcspkr" | sudo tee /etc/modprobe.d/blacklist-pcspkr.conf

# Verify
grep pcspkr /etc/modprobe.d/*.conf
```

Module parameters are worth checking before you guess. `modinfo -p` shows available parameters when the module exposes them, and `/sys/module/<name>/parameters/` may show the active value after load. Not every module exposes parameters, and not every parameter can be changed after load. The operational answer is to inspect what the module actually supports, load with the needed parameter only when appropriate, and verify the resulting state from the kernel's view.

```bash
# Show available parameters
modinfo -p dummy

# Load with a parameter
sudo modprobe dummy numdummies=2

# Check current parameter value (if module exposes it)
cat /sys/module/dummy/parameters/numdummies 2>/dev/null
```

Drill 4, Network Triage, should be practiced as a ladder: verify link state, check IP address assignment, inspect the route table, test DNS resolution, and verify service reachability on the expected port. Drill 5, Static Routes and Network Services at Boot, adds a route to `10.99.0.0/16` through the default gateway, verifies route selection, removes it, then repeats the idea persistently through Netplan or NetworkManager. Drill 6, Kernel Module Practice, uses a safe module such as `dummy` when available, inspects it with `modinfo`, loads it with `modprobe`, confirms it with `lsmod`, removes it, and explains how persistence would work if required.

## SSH and Remote Access

SSH is the bridge between local recovery and remote administration. LFCS can include tasks where you connect to another host, copy a file, or prove that a remote service is reachable. The basic commands are small, but the evidence matters: `ssh -v` can show authentication and host-key progress, `scp` proves file transfer, and the server-side `systemctl` plus `ss` checks prove the service is available. Treat remote access as another service with runtime, network, and persistence dimensions.

Remote access should also change how you think about risk. A local console lets you repair a bad route or target mistake directly, but an SSH session depends on the route, address, firewall, service, and authentication path staying intact. Before applying persistent network changes over SSH, make sure you have a rollback plan or a console path. In an exam lab this may simply mean using temporary route tests first. In production it may mean an out-of-band console, a delayed rollback job, or a maintenance window with a second operator watching the session.

```bash
ssh user@server
scp file.txt user@server:/tmp/
ssh -v user@server
```

## Patterns & Anti-Patterns

Patterns are useful only when they change what you do under pressure. The strongest pattern in this module is evidence before mutation: inspect process, unit, log, config, network, and persistence state before changing files. The second pattern is runtime proof before persistent configuration: test a route or service state now, then encode the durable version after you know it solves the task. The third pattern is reversible practice: record the original target, route, crontab, or module state before you change it, so cleanup is a planned step rather than a memory test.

Those patterns are intentionally repetitive because Linux recovery rewards boring consistency. A service fix, a route fix, a cron fix, and a module fix all have different command surfaces, but the operational grammar is the same. Read the current state, make the smallest useful change, observe the changed behavior, and either persist or clean up depending on the task. If you practice that grammar across unrelated subsystems, you spend less exam time deciding how to begin. Beginning well is a major advantage because most timed failures start with an unfocused first minute.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---|---|---|---|
| Evidence ladder | Any unclear service or network symptom | It narrows the fault without creating extra changes | Teach the same ladder to teammates so incident notes stay comparable |
| Runtime before persistence | Routes, services, modules, and boot targets | It proves the behavior before encoding it for reboot | Automation should capture both the test and the durable configuration |
| Verify and clean up | Cron, at, temporary routes, test users, modules | It prevents practice artifacts from becoming future faults | Shared labs need cleanup checklists because leftover state misleads the next learner |

Anti-patterns usually come from impatience rather than ignorance. Restarting a service repeatedly without reading logs feels active, but it destroys time and may hide the first useful error. Editing Netplan before proving a temporary route feels thorough, but it risks breaking your session with a persistent mistake. Loading a kernel module before reading `modinfo` feels harmless until the module has parameters, dependencies, or side effects you should have known first.

The better alternative is to make each action earn its place. If a command will not answer a question, repair a proven fault, verify a result, or clean up test state, it can probably wait. This is especially important on shared lab machines where old practice artifacts can mimic new failures. A leftover cron entry may rewrite a file after you fix it, a stale route may make a network task behave differently from the documentation, and a persistent module file may reload state you thought you removed. Cleanup is not neatness; it is diagnostic hygiene.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|---|---|---|
| Restart loop | The same failure repeats while useful evidence is ignored | Read unit status and journal output, then restart once after a targeted fix |
| Persistent-first networking | A bad route or YAML mistake survives reboot | Prove with `ip route` first, then persist through the active manager |
| Cleanup by memory | Test jobs, routes, users, or module files remain behind | Write cleanup into the exercise plan and verify the final state |

## Decision Framework

Use the decision framework as a quick exam map rather than a rigid script. First ask what kind of symptom you have: service state, boot state, scheduling state, network path, remote access, or kernel capability. Then ask whether the task is asking for current behavior, boot-persistent behavior, or both. Finally choose the smallest tool that answers the next question. That sequence prevents you from using a durable configuration tool when you only need a runtime test, and it prevents you from declaring success when the task explicitly requires reboot persistence.

| Symptom or Requirement | First Evidence | Next Action | Persistence Check |
|---|---|---|---|
| Service not running | `systemctl status`, `journalctl -u`, `pgrep -a` | Fix the logged cause, then restart once | `systemctl is-enabled`, enabled unit file, listening socket |
| Wrong boot mode | `systemctl get-default`, current target | Isolate only when needed, set default only when required | Recheck default and previous boot logs |
| Scheduled command missing | `crontab -l`, `/etc/cron.*`, `atq` | Add or repair the job with absolute paths | Confirm output, queue contents, and cleanup |
| Host cannot reach network | `ip addr`, `ip route`, `getent hosts`, `ss` | Test route or service state before editing config | Netplan, NetworkManager, or enabled service state |
| Module capability required | `modinfo`, `lsmod`, `/sys/module` | Load with `modprobe`, verify, then unload if temporary | `/etc/modules-load.d/` or `/etc/modprobe.d/` |

When you are uncertain, prefer a read-only command or a temporary runtime change. Read-only commands preserve options, and temporary changes let you test a hypothesis without committing it to boot. The exception is a task that explicitly asks for persistence; then you still inspect first, but you do not stop until the persistent state is visible. A concise exam answer often has four verbs: inspect, change, verify, clean.

The framework also helps when two symptoms appear at once. Suppose SSH fails and a static route is missing. You could spend time on host keys, credentials, or service restarts, but the path evidence tells you the remote service cannot be reached until the route is repaired. Suppose a service is enabled but not active, and the journal says a module-backed device is missing. The service layer is still the symptom, but the module layer may be the cause. A good framework lets lower layers explain higher-layer failures without encouraging random jumps.

Use the same decision habit for Kubernetes-adjacent host work. A kubelet problem may be reported as a node readiness issue, but the root cause can still be a disabled service, missing route, full journal clue, or kernel module state. The LFCS exam is not a Kubernetes troubleshooting exam, yet the Linux host skills are directly reusable when cluster components depend on host networking, process supervision, and boot persistence. This is why the module keeps returning to evidence. Kubernetes adds orchestration, but the node still obeys Linux.

## Did You Know?

- `systemd` became the default init system in several major Linux distributions during the 2010s, which is why LFCS expects target and unit fluency rather than only SysV runlevel memorization.
- Cron uses five time fields before the command in user crontabs, and day-of-week values commonly accept both 0 and 7 as Sunday, which can surprise learners who expect a single value.
- `modprobe` reads module dependency information and configuration, while `insmod` loads a specific module file directly, so `modprobe` is the practical default for dependency-aware operations.
- `ip route get <destination>` does not send traffic to the destination; it asks the kernel which route it would choose, making it a fast and low-risk route-selection check.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Restarting a failed service repeatedly | The red `failed` state feels like the problem instead of a symptom | Read `systemctl status` and `journalctl -u` first, fix the logged cause, then restart once |
| Treating enabled as running | Boot persistence and current process state are different layers | Check both `systemctl is-enabled` and `systemctl status`, then verify the listening socket when relevant |
| Editing persistent network files before a runtime test | Persistent tools feel more official than temporary route commands | Prove the route with `ip route add` and `ip route get`, then encode the durable version |
| Forgetting cron environment differences | The command worked in an interactive shell, so the schedule is blamed | Use absolute paths, redirect output, and inspect the job under the correct user |
| Confusing `rescue.target` and `emergency.target` | Both feel like single-user recovery modes | Use rescue for minimal services and emergency for the smallest root-shell recovery path |
| Loading modules without reading metadata | The module name looks familiar, so parameters and dependencies are ignored | Run `modinfo`, load with `modprobe`, and verify with `lsmod` or `/sys/module` |
| Leaving practice artifacts behind | The repair succeeded, so cleanup feels optional | Remove test routes, scheduled jobs, module files, and temporary logs, then verify the clean state |

## Quiz

<details>
<summary>Question 1: A web service is enabled, but after boot it is not listening on port 80. What evidence do you gather before editing configuration?</summary>

Start with `systemctl status` for the unit, then inspect `journalctl -u` for the same unit and use `ss -tlnp` to see whether another process owns the port. Enabled state only proves a boot attempt, not a healthy process or socket. If the journal shows a bind error and `ss` shows another listener, the correct repair is to resolve the listener conflict rather than rewrite unrelated service configuration. This question assesses the outcome to diagnose systemd service failures using process state, unit status, and journal evidence.
</details>

<details>
<summary>Question 2: You need to enter a minimal recovery mode now, but the machine should still boot normally later. Which target action is safest?</summary>

Use `systemctl isolate rescue.target` in the disposable recovery environment and avoid changing the default target unless the task explicitly asks for a persistent boot-mode change. `isolate` changes the current transaction, while `set-default` changes future boots. If you set the default during a temporary recovery task, you create a second problem that appears after reboot. This tests whether you can evaluate boot targets, rescue modes, and shutdown actions without making recovery harder.
</details>

<details>
<summary>Question 3: A cron job runs correctly when pasted into your shell but produces no file from cron. What should you inspect first?</summary>

Inspect the exact crontab entry, the user that owns it, absolute command paths, and output redirection before restarting cron. Cron does not inherit your interactive shell environment, so `PATH`, working directory, and variables are common differences. A useful fix is to use full paths and redirect both standard output and errors to a file you can verify. This tests the ability to implement cron and at scheduled tasks with verification and cleanup.
</details>

<details>
<summary>Question 4: You add a temporary route and connectivity starts working. The task says the route must survive reboot. What is the next correct move?</summary>

Identify the active network manager, then encode the proven route through Netplan or NetworkManager as appropriate and verify the route table after applying the change. The temporary route proves the hypothesis, but it disappears on reboot. The persistent configuration is the durable answer, yet it should be based on a route that already worked at runtime. This checks the outcome to compare temporary routing fixes with persistent Netplan or NetworkManager configuration.
</details>

<details>
<summary>Question 5: `modprobe dummy` succeeds, but a reboot should load the same module automatically. What evidence and file location matter?</summary>

Verify the module is loaded now with `lsmod` or `/sys/module`, inspect it with `modinfo`, then add the module name to a file under `/etc/modules-load.d/`. Runtime loading and boot loading are separate states, so `modprobe` alone is not enough for a persistence requirement. After writing the file, inspect it and be prepared to remove it during cleanup if this was only a practice task. This assesses the ability to inspect, load, unload, persist, and blacklist kernel modules with evidence.
</details>

<details>
<summary>Question 6: DNS lookup fails for a host, but `ping` to an external IP also fails. Why is DNS not your first repair target?</summary>

If IP reachability also fails, the route, interface, firewall, or link layer may be broken before DNS is even involved. Check `ip addr`, `ip route`, and `ip route get` before changing resolver configuration. DNS may still be broken later, but you need a working path to the network before a resolver can help. This reinforces the networking ladder and the difference between path failures and name-resolution failures.
</details>

<details>
<summary>Question 7: You scheduled an `at` cleanup job and then realize the maintenance step is cancelled. What should you do?</summary>

List queued jobs with `atq`, inspect the relevant job with `at -c` if there is any doubt, and remove it with `atrm` using the correct job number. Leaving a one-time cleanup queued after the maintenance task is cancelled creates delayed state change that is hard to explain later. The same principle applies in the exam: scheduling is not complete until you can verify or remove the queued work. This also tests scheduling verification and cleanup discipline.
</details>

## Hands-On Exercise

This exercise is designed for a disposable VM, lab instance, or local sandbox where you can safely change service state, routes, scheduled jobs, and module state. Record the original state before each task, especially default targets, crontabs, routes, and module persistence files. If your lab distribution does not have a particular service or module, substitute a safe equivalent and keep the same evidence pattern. The goal is not to damage a machine creatively; it is to practice inspect, change, verify, and clean up until the sequence feels automatic.

Run the tasks as a single scenario instead of isolated command practice. Begin by writing a short state note with the service you will inspect, the current default target, the current crontab status, the default route, the active network manager, and the module you intend to test. After each task, update the note with the command that changed state and the command that verified it. This creates a compact audit trail, which is exactly what you want during an exam review or a real maintenance window. It also exposes weak spots because any state you cannot record is a state you probably do not understand yet.

- [ ] Diagnose systemd service failures using process state, unit status, and journal evidence. Stop a harmless service, inspect process state, read unit status, check the unit journal, start it again, and verify whether it is enabled for boot.
- [ ] Evaluate boot targets and shutdown actions. Record the current default target, identify whether rescue or emergency mode would be appropriate for a hypothetical broken configuration, schedule a reboot, cancel it, and inspect current plus previous boot logs.
- [ ] Implement cron and at scheduled tasks with cleanup. Add a cron heartbeat that writes to `/tmp/cron-test.log`, verify it runs, remove it, then queue an `at` job that writes `/tmp/at-test.log`, inspect the queue, and clean up the file.
- [ ] Compare temporary routing with persistent network configuration. Add a temporary route to a lab-only destination through your gateway, verify route selection, remove it, then explain whether Netplan or NetworkManager would own the persistent version on your system.
- [ ] Inspect and manage a safe kernel module. Use `modinfo` on `dummy` or another harmless module, load it with `modprobe`, verify it with `lsmod`, unload it, and describe how `/etc/modules-load.d/` or `/etc/modprobe.d/` would change boot behavior.
- [ ] Verify SSH or another network-facing service. Check whether the service is active, enabled, and listening; if you use a remote host, copy a harmless file and use verbose SSH output only long enough to prove connection progress.

<details>
<summary>Solution guidance for task 1</summary>

Use the service evidence ladder instead of jumping directly to a restart. Capture process evidence with `pgrep -a` or `ps`, read `systemctl status`, and inspect `journalctl -u` for the unit. After starting or restarting the service, verify both the active state and any listening socket that the service should expose. If the task asks for boot persistence, finish with `systemctl is-enabled`.
</details>

<details>
<summary>Solution guidance for task 2</summary>

Keep runtime and default boot state separate. `systemctl get-default` records the durable target, while an isolate operation changes the current state. Use shutdown scheduling and cancellation to practice controlled reboot behavior without actually losing the session. Previous boot logs are available with `journalctl -b -1` after a reboot, and current boot logs are available with `journalctl -b`.
</details>

<details>
<summary>Solution guidance for task 3</summary>

For cron, use absolute paths and redirect output so you can prove the run. For `at`, list the queue with `atq` and inspect the generated job with `at -c` before it runs. Cleanup is part of success: remove test crontab entries, remove queued jobs when appropriate, and delete temporary output files only after you have verified they were created.
</details>

<details>
<summary>Solution guidance for task 4</summary>

Use a temporary route first because it is easy to remove and proves whether the gateway is correct. `ip route get` is the fastest verification for route selection. For persistence, inspect whether Netplan, NetworkManager, or another manager owns the interface before editing files. Apply the persistent change only after the temporary route proves the intended path.
</details>

<details>
<summary>Solution guidance for task 5</summary>

Start with `modinfo` so you know what the module is and whether it has parameters. Use `modprobe` to load by name because it handles dependencies, then confirm with `lsmod` or `/sys/module`. For persistence, place the module name under `/etc/modules-load.d/`; for prevention, use a blacklist file under `/etc/modprobe.d/`. Remove any practice files you created and verify the final state.
</details>

<details>
<summary>Solution guidance for task 6</summary>

For a network-facing service, verify the unit, the enabled state, and the socket. SSH adds host-key and authentication details, so `ssh -v` is useful when a connection fails before the shell opens. Avoid leaving verbose logs or copied test files behind. The completed evidence should show that the service is active now and configured for the next boot when the task requires it.
</details>

Success criteria should prove both repair and cleanup, so do not mark the exercise complete until each final state is visible from the command line:

- [ ] You can explain a failed service from logs instead of from guesses.
- [ ] You can distinguish a current target change from a default boot target change.
- [ ] You can schedule, inspect, verify, and remove both recurring and one-time jobs.
- [ ] You can prove a route at runtime before describing or applying persistence.
- [ ] You can load and unload a module safely and identify the files that control boot behavior.
- [ ] You can verify a network-facing service across process, socket, and boot-persistence layers.

## Sources

- [systemctl manual](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html)
- [journalctl manual](https://www.freedesktop.org/software/systemd/man/latest/journalctl.html)
- [systemd special units and targets](https://www.freedesktop.org/software/systemd/man/latest/systemd.special.html)
- [ps manual](https://man7.org/linux/man-pages/man1/ps.1.html)
- [kill manual](https://man7.org/linux/man-pages/man1/kill.1.html)
- [crontab file format](https://man7.org/linux/man-pages/man5/crontab.5.html)
- [at utility specification](https://man7.org/linux/man-pages/man1/at.1p.html)
- [ip-route manual](https://man7.org/linux/man-pages/man8/ip-route.8.html)
- [ss manual](https://man7.org/linux/man-pages/man8/ss.8.html)
- [modprobe manual](https://man7.org/linux/man-pages/man8/modprobe.8.html)
- [modinfo manual](https://man7.org/linux/man-pages/man8/modinfo.8.html)
- [modules-load.d manual](https://www.freedesktop.org/software/systemd/man/latest/modules-load.d.html)
- [Netplan YAML reference](https://netplan.readthedocs.io/en/stable/netplan-yaml/)
- [NetworkManager nmcli manual](https://networkmanager.pages.freedesktop.org/NetworkManager/NetworkManager/nmcli.html)
- [Kubernetes Nodes](https://kubernetes.io/docs/concepts/architecture/nodes/)

## Next Module

Continue to [LFCS Storage, Services & Users Practice](../module-1.4-storage-services-and-users-practice/).
