---
title: "Module 0.3: Process & Resource Survival Guide"
slug: linux/foundations/everyday-use/module-0.3-processes-resources
citations_verified: true
revision_pending: false
sidebar:
  order: 4
lab:
  id: "linux-0.3-processes-resources"
  url: "https://killercoda.com/kubedojo/scenario/linux-0.3-processes-resources"
  duration: "40 min"
  difficulty: "intermediate"
  environment: "ubuntu"
---

> **Complexity**: `[QUICK]`
>
> **Time to Complete**: 90–120 minutes (long-form read + hands-on exercise)
>
> **Prerequisites**: See [Prerequisites](#prerequisites) below
>
> This quick module is still written as a full operational lesson because process and resource triage becomes useful only when the commands fit into a repeatable diagnostic sequence.

## Prerequisites

Before starting this module, make sure you are comfortable moving around a shell, reading command output, and distinguishing your own user account from system-owned services. You do not need root access for the process exercises, although disk inspection may show more complete results on a machine where you can use `sudo` responsibly.
- **Required**: [Module 0.1: The CLI Power User](../module-0.1-cli-power-user/)
- **Helpful**: [Module 0.2: Environment & Permissions](../module-0.2-environment-permissions/)
- **Environment**: Any Linux system (VM, WSL, or native)

## What You'll Be Able to Do

After this module, you will be able to perform the following tasks in a live shell and explain the reasoning behind each step. Each outcome appears again in the quiz or hands-on exercise so the lesson stays aligned with what you will actually practice.
- Diagnose process and resource pressure using `ps`, `top`, `htop`, `free`, `df`, and `du`.
- Evaluate whether a process should be watched, signaled, moved to the background, or terminated.
- Implement a safe disk investigation workflow with `df`, `du`, `lsblk`, and log cleanup judgment.
- Compare Linux process behavior with Kubernetes 1.35+ pod shutdown, PID 1, cgroups, and node pressure.

## Why This Module Matters

**Hypothetical scenario:** Picture a 2 AM page during a regional promotion when checkout latency jumps from seconds to minutes. The application looks healthy in the monitoring dashboard, the load balancer still accepts requests, and the database shows no obvious deadlocks. Before anyone checks disk pressure on a worker node, several application processes can sit stuck waiting on I/O while a full `/var` filesystem and a runaway log file go unnoticed.

The painful part was not that Linux behaved mysteriously. The painful part was that Linux was reporting the facts the whole time, but the responders did not have a repeatable way to read them. `df` showed the full filesystem, `du` could have found the log file, `top` showed high wait time, and `ps` showed which processes were blocked. Once the team followed that trail, the fix was straightforward; before that, every restart only moved the problem around.

This module teaches that trail. You will learn how Linux represents running programs as processes, how to inspect CPU and memory pressure without guessing, how to stop work politely before using force, how job control changes what happens inside your terminal session, and how disk checks connect to Kubernetes node health. Treat these commands less like trivia and more like a triage kit: each tool answers one specific question, and the order you ask those questions determines whether you diagnose the system or disturb it.

Your Linux machine is running dozens, and often hundreds, of programs right now. Your browser, terminal, SSH session, editor, shell, background update checks, and forgotten scripts are all competing for CPU time, memory, file handles, and disk throughput. A program on disk is like a recipe in a cookbook; a process is the active cooking station with ingredients out, burners on, and timers running. The kitchen can handle many cooks, but only if someone notices when a pan is smoking.

## What Is a Process?

A process is a running instance of a program, not the program file itself. When you type `ls`, the shell asks the kernel to start the `ls` executable, the kernel assigns it a process ID, the process reads directory entries, prints output, and exits. For that brief moment, `ls` has memory, permissions, open files, a parent process, a working directory, and a place in the scheduler's queue.

Every process has a PID, which is the number you use when you want to inspect or signal it. Every normal process also has a parent PID, because something started it: your shell started `ps`, systemd started `sshd`, a web server master process started worker processes, and a container runtime started your application process. This family relationship matters because process cleanup, terminal hangups, and Kubernetes pod shutdown all follow the parent-child tree.

Linux does not treat "your app" as a special category separate from "the operating system." It schedules all runnable processes, tracks their memory, exposes their open files, and delivers signals through the same kernel mechanisms. That is why a Kubernetes container can look like an isolated application from the platform view while still being a Linux process tree from the node view. Containers add namespaces and cgroups, but they do not stop being processes.

Here is the mental model you should keep while reading every command in this module. A process has identity, ancestry, resources, and state; resource tools answer which process or filesystem is stressed; signal tools change the process lifecycle. The same model works on a laptop, a VM, a bare-metal server, and a Kubernetes worker node.

```text
+----------------------------- Linux system -----------------------------+
|                                                                        |
|  PID 1: systemd                                                        |
|      |                                                                 |
|      +-- sshd -- ssh session -- shell -- ps                            |
|      |                                                                 |
|      +-- containerd -- app container PID 1 -- worker child             |
|      |                                                                 |
|      +-- cron -- backup script -- gzip                                 |
|                                                                        |
|  Scheduler: chooses runnable processes for CPU time                    |
|  Memory manager: tracks resident pages, cache, swap, and pressure      |
|  Filesystems: expose disk capacity, mounts, and block devices          |
+------------------------------------------------------------------------+
```

That diagram is intentionally simple because the first debugging move should also be simple. Ask what is running, ask which process owns the pressure, ask whether the pressure is CPU, memory, disk, or external virtualization, then decide whether to observe, tune, terminate, or escalate. Skipping straight to `kill -9` is like cutting power to the kitchen because one timer is beeping.

## Seeing What Is Running with `ps`

The `ps` command takes a snapshot of the process table. It is a photograph, not a live video feed, which makes it excellent for scripts, one-off checks, and careful investigation when a system is already under stress. A snapshot also has a limitation: a process can start and exit between two commands, so use `ps` to establish facts and `top` or `htop` when you need to watch behavior over time.

Start with the smallest version so the output shape is not overwhelming. In a terminal, `ps` usually shows only processes attached to that terminal session, so you see your shell and the `ps` command itself. That is useful because it proves the process table is not magic; even the diagnostic command becomes a process while it is collecting the diagnostic output.

```bash
# Show processes in your current terminal session
ps
```

The minimal output looks like the following example, with one row for the shell and one row for the diagnostic command. Your PID values will differ, but the columns should have the same meaning.

```text
    PID TTY          TIME CMD
   1234 pts/0    00:00:00 bash
   5678 pts/0    00:00:00 ps
```

The everyday production view is wider. `ps aux` shows processes from all users, including services without a terminal, kernel helper threads, web workers, database processes, and commands owned by other accounts. The output is intentionally dense because it tries to answer ownership, identity, resource consumption, process state, accumulated CPU time, and launch command in one row.

```bash
# Show ALL processes from ALL users
ps aux
```

```text
USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.0  0.1 171584 13324 ?        Ss   Mar20   0:15 /sbin/init
root         2  0.0  0.0      0     0 ?        S    Mar20   0:00 [kthreadd]
www-data  1500  0.5  2.0 500000 40000 ?        S    Mar20   1:30 nginx: worker
you       3456  0.0  0.1  23456  5678 pts/0    Ss   10:00   0:00 -bash
```

Focus on `PID`, `RSS`, `STAT`, and `COMMAND` first. The `PID` gives you a handle for follow-up commands, `RSS` tells you actual resident memory, `STAT` tells you whether the process is running, sleeping, stopped, blocked, or unreaped, and `COMMAND` tells you whether the row is really the thing you think it is. The other columns matter, but these four are enough to avoid most beginner mistakes.

| Column | What It Tells You |
|--------|-------------------|
| USER | Who owns the process |
| PID | The process ID number |
| %CPU | How much CPU it is using right now |
| %MEM | How much memory it is using |
| VSZ | Virtual memory size (includes shared libraries, so it can look misleadingly large) |
| RSS | Resident Set Size, the physical memory currently used |
| TTY | Which terminal it is attached to; `?` means it is a background service |
| STAT | Process state, with extra flags for session and foreground status |
| TIME | Total CPU time consumed |
| COMMAND | The command that started the process |

When the process list is long, do not scroll and hope. Filter deliberately, but remember that a plain `grep` search often matches the `grep` command itself. `pgrep -a` avoids that noise and returns matching processes with their command lines, which makes it a better choice for scripts and quick triage.

```bash
# Find all processes with "nginx" in the name
ps aux | grep nginx

# Better: use pgrep (no grep noise in results)
pgrep -a nginx
```

Pause and predict: run `ps aux` now and find the row with the largest RSS. Before you inspect the command name, guess whether it will be your browser, editor, terminal multiplexer, container runtime, or something else. The value of this exercise is not memorizing a number; it is training yourself to ask whether the largest process is expected for the workload you are actually running.

The `STAT` column is your first clue about why a process is or is not making progress. Most healthy services spend much of their time sleeping because they are waiting for network input, timers, disk reads, or child processes. A row in `R` means it is runnable or currently running on a CPU, while a row in `D` means uninterruptible disk sleep, which is especially important during storage incidents because normal signals may not take effect until the I/O returns.

| Code | Meaning |
|------|---------|
| S | Sleeping, usually waiting for input, a timer, or another event |
| R | Running or runnable, actively competing for CPU |
| T | Stopped, often because job control paused it |
| Z | Zombie, finished but not yet reaped by its parent |
| D | Disk sleep, waiting for I/O and cannot be interrupted normally |

A lowercase `s` after the state, such as `Ss`, means the process is a session leader. A plus sign means the process belongs to the foreground process group for that terminal. Those flags explain job-control behavior later in the module, so do not worry about memorizing every variant now. The operational habit is simpler: treat `R`, `D`, and `Z` as prompts to ask a follow-up question, not as final diagnoses.

**Hypothetical scenario:** During a batch export incident, a team sees hundreds of `gzip` workers in `S` state and assumes the server is idle. The real bottleneck was a single slow network mount; the workers were sleeping while waiting for reads, and killing them only caused the orchestrator to start new workers that blocked again. The useful observation was the state transition pattern, not the raw process count.

## Watching CPU and Memory Pressure with `top`, `htop`, and `free`

If `ps` is a photograph, `top` is the live dashboard. It refreshes repeatedly, sorts processes by resource usage, and shows system-wide CPU, task, memory, swap, and load information above the process list. Use it when the system feels slow, when an alert says CPU or memory is high, or when you need to observe whether a suspected process keeps consuming resources after a change.

```bash
# Launch top
top
```

The screen will refresh continuously and show a system summary above the process table. The exact numbers will differ on your machine, but the placement of load, task state, CPU, memory, swap, and process rows is consistent enough to practice reading it.

```text
top - 10:30:00 up 3 days,  2:15,  2 users,  load average: 0.52, 0.58, 0.59
Tasks: 143 total,   2 running, 140 sleeping,   0 stopped,   1 zombie
%Cpu(s):  5.0 us,  2.0 sy,  0.0 ni, 92.0 id,  1.0 wa,  0.0 hi,  0.0 si,  0.0 st
MiB Mem :   7953.5 total,   2345.2 free,   3210.1 used,   2398.2 buff/cache
MiB Swap:   2048.0 total,   2048.0 free,      0.0 used.   4320.5 avail Mem

    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
   1500 www-data  20   0  500000  40000   8192 S   5.0   2.0   1:30.00 nginx
   2100 mysql     20   0 1200000 300000  12000 S   3.0  15.0  12:45.00 mysqld
```

Read `top` from the top down before blaming the process list. The load average tells you how many tasks were runnable or waiting on uninterruptible I/O over one, five, and fifteen minutes. On a four-core machine, a load around four can mean the CPUs are fully subscribed; a load far above that means work is queued or blocked. The process list explains contributors only after the system summary tells you which pressure category is plausible.

The CPU line is a compact language. `us` is user-space work, `sy` is kernel work, `id` is idle time, `wa` is time spent waiting for I/O, and `st` is steal time taken by the hypervisor in a virtualized environment. High `us` usually points toward application CPU, high `sy` can point toward kernel or networking overhead, high `wa` points toward storage, and high `st` means the VM is not receiving the CPU time it requested.

CPU steal is easy to misread because the Linux guest looks slow even when your processes are not using much CPU. On shared cloud hardware, the hypervisor can schedule another tenant or another VM on the physical CPU while your guest waits. Killing your own processes rarely fixes that; the usual response is to move workload, change instance placement, upgrade instance class, or involve the provider if the steal remains sustained.

Memory pressure is similarly easy to misread if you focus on the `free` column. Linux uses spare RAM for filesystem cache because cached files make the system faster, and it can release much of that cache when applications need memory. The `available` field is the practical indicator: it estimates how much memory can be given to applications without heavy swapping. When `available` gets low and swap usage grows, processes may slow dramatically before the out-of-memory killer intervenes.

Use the interactive keys in `top` to answer one question at a time. Sorting by CPU helps during runaway loops, sorting by memory helps during leaks, and showing individual CPU cores helps when one hot thread pins a single core while the total machine still has idle capacity. Quitting quickly after you collect the fact also matters, because on a badly loaded node you do not want a troubleshooting tool to become part of the noise.

| Key | Action |
|-----|--------|
| `q` | Quit |
| `M` | Sort by memory usage |
| `P` | Sort by CPU usage |
| `k` | Kill a process after entering its PID |
| `1` | Toggle showing individual CPU cores |

Pause and predict: launch `top` and compare the one-minute load average with the number of CPUs visible when you press `1`. If the load is higher than the CPU count but `%Cpu` is mostly idle, what resource might be causing the queue? That question trains you to separate CPU saturation from I/O wait instead of treating all slowness as the same failure.

`htop` gives a friendlier interface over the same basic ideas. It adds color, scrolling, search, tree view, and easier signal selection, which makes it excellent when a human is exploring an unfamiliar host. It is not guaranteed to be installed on minimal servers, so treat `htop` as a convenience and `top` as the baseline survival tool.

```bash
# Install htop
# Debian/Ubuntu:
sudo apt install htop -y
# RHEL/Fedora:
sudo dnf install htop -y

# Run it
htop
```

For beginners, `htop` lowers the cost of asking better questions. Press `F5` to see a tree view and discover which parent launched a worker, press `/` to search by name, press `F6` to change sort order, and press `F9` to send a signal after selecting a process. The visual bars are helpful, but the discipline is the same: classify the pressure before you act.

The `free` command gives the system-wide memory picture without opening an interactive dashboard. It is useful in scripts, incident notes, and quick checks when a system is slow enough that you want a single command that exits. Use `free -h` for human-readable values, then inspect `available` and swap before concluding that memory is actually scarce.

```bash
# Show memory in human-readable format (megabytes/gigabytes)
free -h
```

```text
               total        used        free      shared  buff/cache   available
Mem:           7.8Gi       3.1Gi       2.3Gi        45Mi       2.3Gi       4.2Gi
Swap:          2.0Gi          0B       2.0Gi
```

The most important column is `available`, not `free`. In this example, only 2.3 GiB is completely unused, but about 4.2 GiB can be made available to new processes because some cache can be reclaimed. If swap grows while available memory remains low, expect latency spikes because the kernel is moving memory pages to disk, and disk is much slower than RAM.

Worked example: suppose an API node reports high latency. `top` shows load average above CPU count, `%Cpu` shows high `wa`, `free -h` shows plenty of available memory, and the top process list does not show a CPU hog. That combination points away from application CPU and toward disk or storage-backed network I/O, so your next move should be `df`, `du`, mount checks, and logs rather than restarting application workers.

## Stopping Work with Signals, `kill`, `killall`, and `pkill`

Signals are how the operating system tells a process that something happened. Despite the command name, `kill` does not always kill a process; by default, it sends SIGTERM, which is a polite request to shut down. A well-written process handles SIGTERM by closing listeners, finishing in-flight work, flushing files, and exiting cleanly. A stuck process may ignore it, delay it, or be unable to handle it while blocked in uninterruptible I/O.

The distinction between polite and forceful shutdown matters because processes own external state. A database may be writing a transaction, a log shipper may be holding a file offset, a queue worker may be acknowledging a message, and a backup process may be updating a partial archive. SIGKILL stops the process immediately through the kernel, but it gives the process no chance to clean up those responsibilities.

| Signal | Number | What Happens |
|--------|--------|-------------|
| SIGTERM | 15 | "Please shut down gracefully." The process can clean up, save files, close connections, and exit. |
| SIGKILL | 9 | "You are done now." The kernel terminates the process immediately, with no cleanup. |
| SIGHUP | 1 | "Hangup." Many services reload configuration when they receive this. |
| SIGINT | 2 | Interrupt. This is what Ctrl+C sends to the foreground process. |
| SIGSTOP | 19 | Pause the process. It cannot be caught or ignored. |
| SIGCONT | 18 | Resume a paused process. |

Before signaling a process, confirm that the PID still belongs to the target you intend to affect. PIDs are reused after processes exit, and a copied value from old notes can point to a different process later. A quick `ps -p <PID> -o pid,user,stat,cmd` prevents the most embarrassing class of operational mistake: correctly using the wrong command on the wrong process.

```bash
# Send SIGTERM (the default -- always try this first)
kill 1234

# Explicitly send SIGTERM
kill -15 1234
kill -TERM 1234

# Send SIGKILL (the forceful option -- use only if SIGTERM fails)
kill -9 1234
kill -KILL 1234

# Reload a service's config
kill -HUP 1234
```

The safe operational rhythm is simple: confirm, send SIGTERM, wait, confirm again, then escalate only if needed. Waiting is not wasted time because it gives a cooperative service a chance to flush data and release locks. If the process is still present after a reasonable grace period and business risk favors termination, SIGKILL is the tool that ends the process without asking it to cooperate.

```text
Step 1:  ps -p <PID> -o pid,user,stat,cmd
Step 2:  kill <PID>          # Sends SIGTERM -- give it a few seconds
Step 3:  ps -p <PID> -o pid,user,stat,cmd
Step 4:  kill -9 <PID>       # SIGKILL only if still running and escalation is justified
```

When you know a process name but not the PID, `killall` and `pkill` can save time, but they also widen the blast radius. `killall nginx` affects all processes with that exact name, while `pkill sleep` can match more broadly depending on the options you choose. These commands are useful during labs and controlled maintenance; in production, prefer a precise filter and one final confirmation.

```bash
# Kill all processes named "nginx"
killall nginx

# Kill by partial name match
pkill sleep

# Kill all processes by a specific user
pkill -u username
```

Stop and think: before reading further, if you run `kill` on a normal `sleep` process, should it terminate or ignore the signal? Try `sleep 120 &`, save `$!`, send `kill $PID`, and confirm the result. Then imagine replacing `sleep` with a database process that needs time to close files, and the reason for SIGTERM-first becomes more concrete.

The same pattern appears in Kubernetes 1.35+ pod termination. When a pod is deleted, kubelet asks the container runtime to send SIGTERM to the container's main process, waits for the configured grace period, and then sends SIGKILL if the process has not exited. That behavior only works well if PID 1 inside the container forwards or handles signals correctly. A shell wrapper that ignores SIGTERM can turn a graceful rollout into repeated forced kills.

**Hypothetical scenario:** A team uses `kill -9` on a stuck log processor because it looks harmless. The processor had already read data from a queue but had not committed its checkpoint, so the replacement process replayed a large batch and duplicated downstream events. SIGTERM would not have guaranteed perfection, but it would have given the process a chance to persist the offset before exiting.

## Managing Foreground, Background, and Disconnects

Your terminal also manages processes. When you run a command normally, it belongs to the foreground process group, receives keyboard signals such as Ctrl+C, and occupies the prompt until it exits. When you append `&`, the shell starts the command in the background, prints a job number and PID, and returns the prompt while the process continues in the same session.

```bash
# Run sleep in the background
sleep 300 &
# Output: [1] 12345
# [1] is the job number, 12345 is the PID
```

The job number is local to the shell, while the PID belongs to the whole system. That difference matters when you use `fg %1` or `bg %2`, because `%1` and `%2` mean shell jobs, not process IDs. If you open a second terminal, it will not know the first terminal's job numbers, but it can still see the processes by PID with `ps`.

```bash
# See all background jobs in this terminal
jobs
# Output:
# [1]+  Running                 sleep 300 &
```

Job control gives you a way to recover from small mistakes without restarting work. If a long command is already running in the foreground, Ctrl+Z sends a stop signal and returns the prompt. `bg` resumes the stopped job in the background, and `fg` brings it back to the foreground later. Ctrl+C is different: it sends SIGINT and usually terminates the foreground process.

```bash
# Start a long-running command
sleep 300

# Oh no, it is blocking my terminal! Press Ctrl+Z to PAUSE it
# Output: [1]+  Stopped                 sleep 300

# Now resume it in the BACKGROUND
bg
# Output: [1]+ sleep 300 &

# Or bring a background job back to the FOREGROUND
fg
# (Now sleep 300 is running in the foreground again)

# If you have multiple jobs, specify the job number
fg %1
bg %2
```

Before running this, what output do you expect from `jobs` after you pause `sleep 300` with Ctrl+Z? Predict whether the job will be marked running or stopped, then test it. The prediction matters because the terminal is not just displaying processes; it is also controlling which process group receives your keyboard signals.

Backgrounding a command does not make it independent from your login session. If you SSH into a server, start a migration with `&`, and then the SSH session drops, the terminal can send SIGHUP to its child processes. Many shells and programs exit when they receive that hangup, so the command can die even though it was not in the foreground.

`nohup`, short for "no hangup," tells the command to ignore SIGHUP and keep running after the terminal disconnects. It also redirects output to `nohup.out` by default if you do not choose a destination. For serious work, `tmux`, `screen`, systemd services, or a real job runner are usually better, but `nohup` is a useful emergency tool when you cannot redesign the workflow.

```bash
# This will survive even if you disconnect from SSH
nohup ./long-running-script.sh &

# Output goes to nohup.out by default
# Redirect it if you prefer
nohup ./long-running-script.sh > /tmp/my-output.log 2>&1 &
```

| Action | Command |
|--------|---------|
| Run in background | `command &` |
| List background jobs | `jobs` |
| Pause foreground process | `Ctrl+Z` |
| Resume in background | `bg` or `bg %N` |
| Bring to foreground | `fg` or `fg %N` |
| Survive disconnect | `nohup command &` |

Stop and think: you accidentally ran a database migration in the foreground, it will take 20 minutes, and you cannot restart it. The recoverable path is Ctrl+Z followed by `bg`, but that still leaves the process attached to the session. If the task must survive a disconnect, you should have started it under `nohup`, a terminal multiplexer, or a service manager before beginning the migration.

## Finding Disk Pressure with `df`, `du`, and `lsblk`

Disk incidents often look like unrelated application failures. A node stops accepting writes, logs disappear, databases refuse transactions, package installs fail, containers cannot unpack layers, and health checks time out. The kernel is usually behaving consistently; the filesystem is out of space, out of inodes, mounted read-only, or blocked behind slow storage. Your job is to move from "the app is broken" to "which filesystem and which path are responsible?"

Start with `df` because it shows the mounted filesystems and their capacity. It answers the big-picture question: which filesystem is full? That matters because `/`, `/var`, `/home`, and `/tmp` may be separate mounts. Deleting files from a roomy filesystem will not help a full `/var`, and expanding the wrong volume wastes time during an incident.

```bash
# Show disk usage in human-readable format
df -h
```

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        50G   35G   13G  73% /
/dev/sda2       200G  180G   10G  95% /var
tmpfs           3.9G     0  3.9G   0% /dev/shm
```

In this example, `/var` is the urgent filesystem because it is at 95 percent. That is a common server failure mode because `/var` holds logs, package caches, container runtime data, databases on some systems, and other state that grows while the machine runs. The correct next question is not "what can I delete anywhere?" but "which directory under `/var` is consuming the space?"

| Column | Meaning |
|--------|---------|
| Size | Total size of the filesystem |
| Used | How much is consumed |
| Avail | How much is free |
| Use% | Percentage used; investigate above 80 percent and treat 95 percent as urgent |
| Mounted on | Where this filesystem appears in the directory tree |

`du` answers the path question by walking directories and summing file sizes. Use it hierarchically: start at the mount point, sort by size, inspect the largest child, and repeat. Redirect permission errors away from the screen when exploring system paths, because otherwise the useful size lines get buried under noisy access-denied messages.

```bash
# Show the size of the current directory
du -sh .

# Show sizes of immediate subdirectories, sorted by size
du -sh /* 2>/dev/null | sort -rh | head -10
```

```text
15G     /var
8G      /usr
5G      /home
3G      /opt
1G      /tmp
```

After the wide scan identifies `/var` as the biggest offender, narrow the question to that mount instead of jumping across unrelated directories. This preserves the investigation path and helps you avoid deleting data that cannot affect the pressured filesystem.

```bash
# Dig into /var
du -sh /var/* 2>/dev/null | sort -rh | head -10
```

```text
12G     /var/log
2G      /var/lib
500M    /var/cache
```

At this point, `/var/log` is the likely problem, but the fix still depends on the exact file or log family. Continue one more level so you can distinguish one oversized rotated file from a broader logging or retention problem.

```bash
du -sh /var/log/* 2>/dev/null | sort -rh | head -5
```

```text
10G     /var/log/syslog.1
1.5G    /var/log/auth.log
500M    /var/log/kern.log
```

The pattern is the important asset: start wide with `df -h`, then drill down with `du -sh <dir>/* | sort -rh | head`. Once you find a file, think before deleting. If a running process still has a deleted file open, space may not be released until that process closes the file. If the file is an active log, truncating it may be safer than removing it because the writer keeps the same file handle.

Pause and predict: run `df -h` and identify the filesystem with the highest `Use%`. Before running `du`, predict which top-level directory will be largest on your machine. The prediction step helps you learn your environment, and the command output teaches you when your instincts are wrong.

`lsblk` shows the physical or virtual block devices, partitions, and mount points. It does not tell you which directory is wasting space, but it explains why a particular mount has the size it does. On cloud VMs and Kubernetes nodes, this helps you distinguish between "a directory grew too much" and "the mounted volume was simply too small for its role."

```bash
lsblk
```

```text
NAME   MAJ:MIN RM  SIZE RO TYPE MOUNTPOINT
sda      8:0    0   50G  0 disk
├─sda1   8:1    0   49G  0 part /
└─sda2   8:2    0    1G  0 part [SWAP]
sdb      8:16   0  200G  0 disk
└─sdb1   8:17   0  200G  0 part /var
```

That output tells you `/var` is backed by a separate 200 GiB disk in the example. If `/var` fills, expanding `/dev/sda1` would not help because `/var` is on `sdb1`. This is the kind of simple infrastructure fact that prevents a tired responder from spending an hour on the wrong volume.

**Hypothetical scenario:** A platform team cleans several gigabytes from `/home` while kubelet continues failing image pulls. The alert referred to node disk pressure, but the exhausted path was under `/var/lib/containerd` on a separate mount. `df -h` would have shown the mount, and `du` under `/var` would have found the image store before anyone touched user directories.

## Kubernetes Connection: Processes in Pods

Kubernetes does not replace Linux process mechanics; it builds scheduling, isolation, and policy on top of them. A pod may feel like a platform object, but the node still runs processes, tracks memory through cgroups, uses filesystems for images and logs, and delivers signals during termination. When you understand the Linux layer, Kubernetes node behavior becomes much less surprising.

Before using short `k` commands, define the common alias once in your shell. The full command is `kubectl`, and the alias `k` is only a typing shortcut; it does not change what the Kubernetes API receives. In production notes, be clear about whether you used `kubectl` or the alias so another responder can reproduce the command.

```bash
alias k=kubectl
```

From there, `k get pods`, `k describe node`, and `k top pod` are Kubernetes views over workload and resource state, while Linux commands such as `ps`, `top`, `free`, `df`, and `du` show what the node itself is experiencing. The useful skill is moving between those views without confusing them. A pod can be pending because of Kubernetes scheduling policy, or a running pod can be slow because the node underneath is waiting on disk.

| Kubernetes concept | Linux mechanism underneath | Operational clue |
|--------------------|----------------------------|------------------|
| Container main command | PID 1 inside the container namespace | If PID 1 exits, the container stops |
| Pod termination | SIGTERM, grace period, then SIGKILL | Bad signal handling causes forced shutdowns |
| Memory limit | cgroup memory accounting | Exceeding the limit can trigger OOM kill |
| Node memory pressure | Kernel memory pressure and kubelet eviction signals | Pods may be evicted before the node collapses |
| Ephemeral storage pressure | Filesystems under kubelet and container runtime paths | Logs and image layers can fill `/var` |

```bash
# Kubernetes 1.35+ examples using the k alias
k get pods -A
k describe node worker-1
k top pod -A
k exec -it my-pod -- ps aux
```

When you run `k exec -it my-pod -- bash`, you are not SSHing into a little VM. You are asking the container runtime to start a new process in the pod's namespaces and attach your terminal to it. That distinction matters because tools inside the container may be minimal, process IDs may be namespace-relative, and the node can still have pressure that the container view hides.

Resource limits are also Linux limits with Kubernetes policy around them. When you set `resources.limits.memory` on a container, kubelet and the runtime configure cgroups so the kernel can account for that process tree. If the process exceeds its limit, the kernel may kill it even when the node has total free memory. If the node itself runs out of available memory, kubelet may evict pods to protect the machine.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: resource-demo
spec:
  containers:
    - name: app
      image: busybox:1.36
      command: ["sh", "-c", "sleep 3600"]
      resources:
        requests:
          cpu: "100m"
          memory: "64Mi"
        limits:
          cpu: "500m"
          memory: "128Mi"
```

Which approach would you choose here and why: if `k describe node` reports disk pressure but `top` shows low CPU and plenty of memory, should you restart the busiest application pod or inspect node filesystems first? The better first move is usually `df -h` and `du` on the node, because restarting pods can create more image and log churn on the same full disk.

Graceful shutdown is the most direct bridge between this module and Kubernetes operations. If an application runs as PID 1 and ignores SIGTERM, kubelet waits for the grace period and then sends SIGKILL. That can interrupt writes, drop requests, and make rollouts look flaky. A small init process, correct signal handling, and realistic `terminationGracePeriodSeconds` are application design choices that depend on understanding Linux signals.

## Patterns & Anti-Patterns

Good process troubleshooting is mostly sequencing. You gather a low-cost snapshot, classify pressure, confirm the target, and only then change the system. That sequence feels slower than typing the first dramatic command that comes to mind, but it is faster across a real incident because it reduces reversals. It also leaves better notes for the next responder.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| Snapshot first | You need an initial fact without disturbing the host | `ps`, `free`, and `df` exit quickly and create incident notes | Automate these checks in runbooks before interactive tools |
| Classify pressure before acting | The symptom is "slow" or "stuck" | CPU, memory, disk, and steal require different fixes | Dashboards should separate wait, steal, memory, and filesystem alerts |
| SIGTERM before SIGKILL | A process must stop but may own state | Graceful shutdown protects files, sockets, and checkpoints | Tune Kubernetes grace periods around real shutdown time |
| Drill down by mount point | Disk usage alerts fire | `df` finds the filesystem and `du` finds the path | Track container runtime paths and log retention separately |

Anti-patterns usually come from impatience, stale assumptions, or treating the terminal as if it were only a text box. A command that is safe in a lab can be risky on a shared host because it changes many processes or hides the reason a process was stuck. The alternative is not paralysis; it is a tiny verification step before each destructive action.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Starting with `kill -9` | The process cannot flush data, release locks cleanly, or write checkpoints | Confirm the PID, send SIGTERM, wait, then escalate if justified |
| Reading only `%CPU` | Disk wait, memory pressure, and CPU steal get missed | Read load average, `wa`, `st`, memory, and process state together |
| Searching process lists by scrolling | Important rows are missed and grep matches can fool you | Use `pgrep -a`, precise `ps` options, and targeted filters |
| Deleting large logs blindly | Space may not be released if a process still holds the file open | Prefer log rotation or truncation after confirming the writer |
| Backgrounding critical work with only `&` | The command can die when the SSH session disconnects | Use `nohup`, `tmux`, `screen`, systemd, or a real job runner |
| Restarting pods for node disk pressure | New containers may write more data to the same full filesystem | Inspect `df`, `du`, kubelet paths, and container runtime storage first |

Use these tables as operating habits, not as trivia. The point is to preserve optionality: you can always move from observation to termination, but you cannot recover graceful cleanup after a force kill has already happened. You can always inspect a filesystem before deleting data, but you cannot always reconstruct which file mattered after a broad cleanup script has run.

## When You'd Use This vs Alternatives

For a quick module, the decision framework is a practical comparison rather than a heavyweight flowchart. Choose the tool that matches the question you are asking. If you do not know the question yet, start with the least invasive command that gives system-wide context, then narrow the scope.

| Question | First Tool | Follow-Up Tool | Avoid Starting With |
|----------|------------|----------------|---------------------|
| What processes exist right now? | `ps aux` | `pgrep -a`, `ps -p` | `killall` |
| Which process is hot over time? | `top` or `htop` | `ps`, logs, profiler | Random restarts |
| Is memory actually scarce? | `free -h` | `top`, application metrics | Reading only `free` memory |
| Which filesystem is full? | `df -h` | `lsblk` | Deleting files from unrelated mounts |
| Which path is consuming space? | `du -sh <dir>/*` | log rotation, cleanup plan | Recursive deletes without confirmation |
| Will work survive disconnect? | `nohup`, `tmux`, or systemd | `jobs`, `ps` | Plain `command &` |

The decision flow is also a communication tool. During an incident, saying "load is high, CPU is idle, wait time is high, and `/var` is nearly full" gives teammates a reasoned diagnosis. Saying "the node is weird" gives them a mood. Senior operators sound calm because they have a vocabulary for separating evidence from fear.

Use process termination when a specific process is confirmed harmful and graceful shutdown has been attempted or is impossible. Use job control when the issue is your terminal session, not the system. Use disk tools when capacity or I/O wait is suspicious. Use Kubernetes commands when you need the API server's view, then drop to Linux commands when the node's local resources are the likely constraint.

## Did You Know?

- **Your system has a family tree of processes.** Every process has a parent, and PID 1 is the ancestor of normal user-space work. On most modern distributions PID 1 is systemd, while inside a container your application may become PID 1, which is why signal handling and child reaping matter during Kubernetes pod termination.
- **`kill` does not always kill.** The command sends signals, and the default signal is SIGTERM, a graceful shutdown request that a process can handle. SIGKILL is different because the kernel terminates the process directly, which is powerful but removes the process's chance to save state.
- **Zombie processes are already dead.** A zombie has finished running but remains in the process table because its parent has not collected the exit status. One zombie uses no CPU and almost no memory, but a large buildup can exhaust process table space and reveal a broken parent process.
- **`/proc` is a live kernel interface, not a normal folder of logs.** Each running process appears under `/proc/<PID>/`, with files such as `cmdline`, `status`, and `environ` exposing current process information. Tools like `ps` and `top` rely on kernel data that is conceptually similar to what you can inspect there.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Using `kill -9` as the first option | The process looks stuck, and SIGKILL feels decisive during pressure | Always try `kill <PID>` first, wait a few seconds, verify, then use `kill -9` only when escalation is justified |
| Forgetting `&` and pressing Ctrl+C on a long task | The terminal is blocked, and Ctrl+C feels like the fastest way back to a prompt | Use Ctrl+Z and `bg` to move recoverable work into the background without terminating it |
| Running `du -sh /` without `2>/dev/null` | System directories produce permission errors that obscure the useful size lines | Use `du -sh /* 2>/dev/null \| sort -rh \| head` and drill into the largest mounted path |
| Ignoring `df` until the disk is completely full | Disk growth is gradual, so warnings feel less urgent than application errors | Check `df -h` during triage and alert before critical mounts reach emergency capacity |
| Using `nohup` but forgetting `&` | `nohup` protects against hangup but does not automatically return the prompt | Combine them as `nohup command > /tmp/output.log 2>&1 &` when the command should continue independently |
| Killing a process by PID without checking first | PIDs can be reused after the original process exits | Run `ps -p <PID> -o pid,user,stat,cmd` immediately before signaling the process |
| Treating Kubernetes pods as tiny VMs | `k exec` feels like SSH, so node-level pressure gets overlooked | Remember that containers are process trees using node CPU, memory, cgroups, and filesystems |
| Reading `free` memory instead of available memory | Linux cache makes used memory look scary even when it is reclaimable | Use the `available` column and swap usage to judge actual memory pressure |

## Quiz

<details><summary>Question 1: Your monitoring script must diagnose whether an application process is running every minute. Should it use `ps`, `pgrep`, `top`, or `htop`, and why?</summary>

Use `pgrep -a` or a precise `ps` command because the script needs a snapshot that exits cleanly. `top` and `htop` are interactive dashboards, so they are better for a human watching live behavior and worse for simple automation. A snapshot command also makes it easier to capture exit codes and avoid terminal formatting. If the script later needs resource numbers, use explicit `ps` output columns rather than scraping an interactive screen.

</details>

<details><summary>Question 2: You evaluate a runaway Python process, confirm the PID, send `kill 5678`, and the process remains after a short wait. What happened, and what is the safe next step?</summary>

The first `kill` sent SIGTERM, which asks the process to exit gracefully but can be delayed, ignored, or blocked. Your safe next step is to confirm that PID 5678 still belongs to the same Python command with `ps -p 5678 -o pid,user,stat,cmd`. If it is still the target and business risk favors stopping it, escalate with `kill -9 5678`. The confirmation protects you from PID reuse between the first signal and the escalation.

</details>

<details><summary>Question 3: A database migration was started with `./migrate-db.sh &` over SSH, then failed when the laptop disconnected. Why did backgrounding not protect it?</summary>

The ampersand moved the command to the background of the current shell, but it did not detach the command from the SSH session. When the terminal disconnected, the session could send SIGHUP to child processes, and the migration was still part of that process tree. For work that must survive disconnects, use `nohup`, a terminal multiplexer, a systemd unit, or a job runner. Backgrounding is a prompt-management tool, not a reliability boundary.

</details>

<details><summary>Question 4: An alert says a Kubernetes node has disk pressure, `df -h` shows `/var` at 95 percent, and `top` shows high I/O wait. How do you implement the investigation?</summary>

Start with the full filesystem because `df` has already identified `/var` as the pressured mount. Run `du -sh /var/* 2>/dev/null | sort -rh | head -10`, then repeat the same pattern inside the largest directory until you isolate the path or file. Check whether the culprit is logs, container runtime data, or another service before deleting anything. This preserves the link between node disk pressure and the Linux path that is actually consuming space.

</details>

<details><summary>Question 5: You compare `free -h` and see low `free` memory but high `available` memory with no swap usage. Should you diagnose memory pressure?</summary>

Not yet. Low `free` memory alone is normal on Linux because the kernel uses spare RAM for filesystem cache. High `available` memory means the kernel expects it can give memory to applications without heavy swapping. You should continue watching if the workload is changing, but this output by itself does not prove memory pressure. Real pressure would show low available memory, growing swap, OOM events, or application-level allocation failures.

</details>

<details><summary>Question 6: You need to compare Kubernetes pod behavior with Linux processes during a rollout. The app ignores SIGTERM as PID 1, then pods die after the grace period. What should change?</summary>

The application or its entrypoint needs to handle SIGTERM correctly and exit within the configured Kubernetes grace period. If a shell wrapper is PID 1 and does not forward signals, replace it with an exec form entrypoint or a small init process that forwards signals and reaps children. Tune `terminationGracePeriodSeconds` to match real shutdown time, but do not use a long grace period to hide broken signal handling. The Linux signal model explains why Kubernetes eventually uses SIGKILL when graceful termination fails.

</details>

<details><summary>Question 7: `top` shows load far above CPU count, but `%Cpu` is mostly idle and `wa` is high. Which resource should you diagnose before killing application processes?</summary>

High I/O wait means tasks are waiting on storage, so disk or storage-backed network I/O should be investigated first. Killing application processes may reduce pressure temporarily, but it does not explain why reads or writes are blocked. Check `df -h`, use `du` on pressured mounts, inspect logs, and consider storage health or remote volume latency. The load average is high because tasks are queued or blocked, not necessarily because CPU is saturated.

</details>

## Hands-On Exercise

### Process & Resource Scavenger Hunt

The exercise uses harmless `sleep` processes so you can practice process inspection, job control, and signals without risking real services. Treat the steps like an incident drill: create a known process, identify it by multiple methods, observe it, stop it gracefully, and then inspect disk layout. If you are on a shared machine, avoid killing processes you did not start.

**Objective**: Practice finding, monitoring, and killing processes, then connect that process evidence to system-wide disk usage. The exercise is deliberately small, but the sequence mirrors the way you should approach a real host under pressure.

**Environment**: Use any Linux system, including a VM, WSL instance, or native installation where starting disposable `sleep` processes is acceptable. Avoid running the destructive cleanup ideas from the teaching sections unless you are on a throwaway lab machine.

#### Part 1: Start a Background Process

```bash
# Start a sleep process in the background
sleep 600 &

# The shell tells you the job number and PID:
# [1] 12345

# Save the PID for later (your number will be different)
MY_PID=$!
echo "My background process PID is: $MY_PID"
```

You are deliberately saving `$!` because it contains the PID of the most recent background command. That is more reliable than copying a number by hand, and it gives you a variable you can reuse in later commands. If `echo "$MY_PID"` is empty, start over in the same shell session.

<details><summary>Solution note for Part 1</summary>

You should see a job number in brackets and a PID printed by the shell. The exact PID will differ on every system. The important result is that `MY_PID` contains a number and the prompt returned immediately because the process is running in the background.

</details>

#### Part 2: Find It with `ps`

```bash
# Find your sleep process using ps
ps aux | grep "sleep 600"

# Cleaner: use ps to show just that PID
ps -p $MY_PID -o pid,user,stat,cmd

# See it in the process tree
ps auxf | grep sleep
```

Verify that you can see the PID, that the STAT shows `S` for sleeping, and that the COMMAND is `sleep 600`. The process tree view should make the shell relationship visible, which connects this lab to the parent-child process model from the lesson.

<details><summary>Solution note for Part 2</summary>

`ps -p $MY_PID -o pid,user,stat,cmd` should print one row for the sleep process. If it prints only a header, the process already exited or the variable was not set in the current shell. Restart Part 1 and keep all commands in the same terminal session.

</details>

#### Part 3: Watch It in `top`

```bash
# Launch top
top

# While top is running:
# 1. Press 'P' to sort by CPU
# 2. Press 'M' to sort by memory
# 3. Look for your sleep process (it will have near-zero CPU/MEM)
# 4. Press 'q' to quit
```

If you have `htop` installed, try that too and press `/` to search for `sleep`. A sleeping process should not consume meaningful CPU, which is the point of observing it live: not every process you can see is a process causing pressure.

<details><summary>Solution note for Part 3</summary>

The `sleep` process may be hard to spot if the list is sorted by CPU because it uses almost none. Search in `htop` or use the PID from `$MY_PID` to recognize it. Quit with `q` so you can continue the lab from the shell.

</details>

#### Part 4: Kill It

```bash
# First, confirm the process is still running
ps -p $MY_PID -o pid,cmd

# Send SIGTERM (the polite way)
kill $MY_PID

# Verify it is gone
ps -p $MY_PID -o pid,cmd 2>/dev/null || echo "Process $MY_PID has been terminated."
```

If it were a stubborn process that did not respond to SIGTERM, you would follow up with `kill -9 $MY_PID`. In this lab, `sleep` should respond to SIGTERM cleanly, which lets you practice the normal path before learning the escalation path.

<details><summary>Solution note for Part 4</summary>

The final command should print the termination message because `ps` should no longer find the PID. If the process still appears, confirm it is the same command and then repeat the signal step. Do not use broad commands such as `killall sleep` until the bonus section, where you intentionally create several lab sleeps.

</details>

#### Part 5: Check Disk Space

```bash
# Get the big picture
df -h

# Find the largest directories at the root level
du -sh /* 2>/dev/null | sort -rh | head -10

# Drill into the largest directory (adjust path based on your output)
du -sh /var/* 2>/dev/null | sort -rh | head -5

# Check what physical disks and partitions exist
lsblk
```

Record which filesystem has the highest `Use%` and which directory is largest under the path you inspected. You are not deleting anything in this exercise. The goal is to build the habit of separating filesystem capacity from directory size before taking cleanup action.

<details><summary>Solution note for Part 5</summary>

Your largest directories will depend on the system. On many servers, `/var`, `/usr`, or `/home` will be near the top. If `/var/*` prints permission errors despite the redirect, rerun with `sudo` only if you are on a machine where that is appropriate.

</details>

#### Part 6: Bonus -- Job Control

```bash
# Start three background sleeps
sleep 100 &
sleep 200 &
sleep 300 &

# List all jobs
jobs

# Bring the second one to the foreground
fg %2

# Pause it with Ctrl+Z
# Then resume it in the background
bg %2

# Kill all of them
killall sleep

# Verify they are all gone
jobs
```

This bonus step intentionally uses `killall sleep` because you created only disposable `sleep` processes for the lab. The same command would be a poor production default because it affects every process with that name. The lesson is not that broad matching is forbidden; it is that broad matching requires confidence about scope.

<details><summary>Solution note for Part 6</summary>

After `killall sleep`, `jobs` may show terminated jobs until the shell refreshes their status. Press Enter or run `jobs` again if needed. The expected endpoint is that no running sleep jobs remain in the current shell.

</details>

### Success Criteria

- [ ] Started a background `sleep` process and noted its PID
- [ ] Found the process using `ps aux | grep` and confirmed its STAT code
- [ ] Opened `top` or `htop` and located the process in the list
- [ ] Killed the process with `kill` and verified it was gone with `ps`
- [ ] Ran `df -h` and identified which filesystem has the most usage
- [ ] Used `du -sh` to find the largest directory on the system
- [ ] Compared Linux process behavior with Kubernetes 1.35+ pod shutdown and the `k` alias examples
- [ ] Used `jobs`, `fg`, `bg`, and `killall` to manage multiple background jobs

## Sources

- [Linux `ps(1)` manual page](https://man7.org/linux/man-pages/man1/ps.1.html)
- [Linux `top(1)` manual page](https://man7.org/linux/man-pages/man1/top.1.html)
- [Linux `free(1)` manual page](https://man7.org/linux/man-pages/man1/free.1.html)
- [Linux `kill(1)` manual page](https://man7.org/linux/man-pages/man1/kill.1.html)
- [Linux `pgrep(1)` and `pkill(1)` manual page](https://man7.org/linux/man-pages/man1/pgrep.1.html)
- [Linux `df(1)` manual page](https://man7.org/linux/man-pages/man1/df.1.html)
- [Linux `du(1)` manual page](https://man7.org/linux/man-pages/man1/du.1.html)
- [Linux `lsblk(8)` manual page](https://man7.org/linux/man-pages/man8/lsblk.8.html)
- [Linux kernel memory management concepts](https://www.kernel.org/doc/html/latest/admin-guide/mm/concepts.html)
- [Linux kernel cgroup v2 documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html)
- [Kubernetes pod lifecycle documentation](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- [Kubernetes resource management for pods and containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)

## Next Module

You can now find and evaluate processes, diagnose CPU, memory, and disk pressure, and connect Linux process behavior to Kubernetes node operations. The next module moves from individual processes to the service manager that starts important background programs at boot, restarts them after crashes, and records their logs.

Continue with **Next**: [Module 0.4: Services & Logs Demystified](../module-0.4-services-logs/), where the focus shifts from individual processes to systemd services, startup behavior, restart policy, and logs that explain why long-running background programs succeed or fail.
