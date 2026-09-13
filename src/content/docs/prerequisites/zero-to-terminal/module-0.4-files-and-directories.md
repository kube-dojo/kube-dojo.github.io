---
title: "Module 0.4: Files and Directories"
slug: prerequisites/zero-to-terminal/module-0.4-files-and-directories
revision_pending: false
sidebar:
  order: 5
lab:
  id: "prereq-0.4-files-directories"
  url: "https://killercoda.com/kubedojo/scenario/prereq-0.4-files-directories"
  duration: "20 min"
  difficulty: "beginner"
  environment: "ubuntu"
---
> **Complexity**: `[QUICK]` - Absolute beginner
>
> **Time to Complete**: 90–120 minutes (long-form beginner read + practice)
>
> **Prerequisites**: [Module 0.2: What is a Terminal?](../module-0.2-what-is-a-terminal/) — You should be able to open a terminal and type commands.

---

## What You'll Be Able to Do

After this module, you will be able to:

- **Navigate** absolute and relative paths and choose the safer form for a command, script, or troubleshooting session.
- **Read** files with `cat`, `head`, and `tail`, then select the command that fits the size and purpose of the file.
- **Interpret** file permissions from `ls -l` output and diagnose who can read, write, or enter a file or directory.
- **Find** hidden dotfiles and evaluate why configuration files are hidden by default.

## Why This Module Matters

Hypothetical scenario: you are helping diagnose a Kubernetes node where a Pod keeps restarting, and a teammate tells you, "Check the kubelet logs, then compare the manifest under `/etc/kubernetes/manifests/` with the kubeconfig under `~/.kube/config`." Nothing in that sentence is advanced Kubernetes yet. The hard part, for a beginner, is that every useful clue is described as a path, and every path assumes you can move through the filesystem without a graphical file browser.

The terminal treats the filesystem as the map of the machine. Configuration lives in files, logs are written as files, scripts are stored as files, and directories organize all of it into predictable places. When you can read paths confidently, a command like `tail -n 20 /var/log/syslog` stops looking like punctuation and starts reading like plain instructions: show me the newest twenty lines from this log file.

This module gives you that map-reading skill. You will learn what files and directories are, how Linux arranges them in a tree, how to move with `pwd`, `ls`, and `cd`, how to decide between absolute and relative paths, how to inspect file contents, how to spot hidden dotfiles, and how to read the first permission characters that appear in `ls -l`. The goal is not memorizing commands in isolation. The goal is being able to look at a path during a real troubleshooting task and know what to try next.

## Files, Directories, and the Tree Under Every Command

A **file** is a named container for information stored on your computer. It can hold a grocery list, a shell script, a Kubernetes manifest, a photo, a database page, or a log entry written by a running service. The important beginner idea is that the name is not the whole identity of the file; a file also has contents, a location, ownership, permissions, and timestamps that tell the operating system how the file may be used.

Think of a file like a recipe card in a working kitchen. The card has a name, such as `grocery-list.txt`; it has contents, such as "eggs, milk, bread"; and it sits in a location, such as a drawer or recipe box. If two drawers both contain a card named `sauce.txt`, the name alone is not enough. You need the location as well, which is why paths matter so much in terminal work.

Files can contain many kinds of data, and the terminal does not judge a file by its icon the way a desktop environment often does. A text file might contain notes, source code, a YAML manifest, or shell commands. A binary file might contain an image, a compiled program, compressed data, or a database. The filename extension is a useful convention, but the filesystem itself mostly cares about bytes, metadata, and permissions.

In Linux, the file idea goes deeper than documents. Your actual notes are files, but the operating system also exposes devices, kernel information, and running process details through file-like interfaces. For example, Red Hat documentation describes how device entries appear under paths such as `/dev`, and process or kernel state is exposed through `/proc`. You do not need to manage device files today, but you should remember the pattern: Linux tools are powerful because many different things can be read, listed, redirected, or inspected through a file-shaped interface.

```text
/                          <-- The "root" — the very top, the ground floor
├── home/                  <-- Where user accounts live
│   └── yourname/          <-- YOUR home directory
│       ├── Documents/
│       ├── Downloads/
│       ├── Desktop/
│       └── projects/
├── etc/                   <-- System configuration files
├── var/                   <-- Variable data (logs, databases)
├── tmp/                   <-- Temporary files
└── usr/                   <-- User programs and utilities
```

A **directory** is a container for files and other directories. Desktop users usually say "folder" because the visual metaphor is a paper folder; terminal users usually say "directory" because that is the technical term. The concepts are the same, but the terminal version is more precise because it makes parent and child relationships visible in every path.

The tree starts at `/`, called the root directory. Every absolute path begins there, even if the directory you use every day is much lower in the tree. Your personal work usually lives under `/home/yourname/` on Linux and under `/Users/yourname/` on macOS, while system configuration often lives under `/etc/`, logs often live under `/var/log/`, and temporary files often live under `/tmp/`. Kubernetes follows these conventions: kubeadm writes static Pod manifests under `/etc/kubernetes/manifests/`, kubelet and container logs are commonly found below `/var/log/`, and `kubectl` configuration is commonly read from `~/.kube/config`.

| Path | What It Is | Kitchen Analogy |
|------|-----------|-----------------|
| `/` | **Root directory** — the very top of the tree | The building itself — everything is inside it |
| `/home/yourname/` | **Your home directory** — your personal space | Your personal workstation in the kitchen |
| `~` | **Shorthand for your home directory** | A nickname for your workstation |
| `/etc/` | System configuration files | The restaurant's policy manual and recipe standards |
| `/tmp/` | Temporary files that may be cleaned automatically depending on system policy | The prep table — used during cooking, sometimes cleaned up automatically |
| `/var/log/` | Log files, or records of what happened | The order history book |

The `~` character is a shell shortcut for your home directory, not a directory named tilde that you normally see in `ls`. That distinction matters when you read documentation. A command that points to `~/.kube/config` means "inside the current user's home directory, find a hidden `.kube` directory, then read the `config` file." It does not matter whether the user's actual home path is `/home/amina`, `/home/yourname`, or `/Users/amina` on macOS.

Pause and predict: if two users on the same Linux machine both run a command that reads `~/.kube/config`, do they read the same file or different files? The answer is usually different files, because `~` expands separately for each user's shell session. That is why documentation uses `~` for personal configuration but uses absolute system paths, such as `/etc/kubernetes/manifests/`, for machine-wide configuration.

| Concept | Beginner Meaning | Operational Consequence |
|---------|------------------|--------------------------|
| File | Named data stored by the system | Logs, manifests, scripts, and notes can all be inspected with terminal tools |
| Directory | Container for files or directories | Paths work because every item has a parent location |
| Root `/` | Start of the whole filesystem tree | Absolute paths can locate a file from anywhere |
| Home `~` | Current user's personal directory | Personal config such as shell settings and kubeconfig stays user-specific |
| Dotfile | Hidden file or directory whose name starts with `.` | Important configuration may not appear in plain `ls` output |

## Navigating Without Getting Lost

When you open a terminal, you are always "standing" in one directory, called your **working directory**. The terminal does not show a full map by default because a full map would be noisy on every command. Instead, you ask specific questions: where am I, what is here, and where do I want to go next?

The first question is answered by `pwd`, which stands for **print working directory**. It gives you the full absolute path to your current location. In the kitchen analogy, `pwd` is the answer to "which room am I standing in right now?", and that answer determines whether relative directions such as `Documents/report.txt` make sense.

```bash
pwd
```

```text
/home/yourname
```

The second question is answered by `ls`, which lists the contents of a directory. With no path, it lists the current directory. With a path, it lists that location instead. Beginners often treat `ls` as a command to run after getting confused, but it is better to treat it as a normal navigation habit: look before moving, especially when you are near system directories or production logs.

```bash
ls
```

```text
Desktop    Documents    Downloads    Music    Pictures
```

The `-l` option asks for long format, which includes file type, permissions, owner, group, size, timestamp, and name. You do not need to understand every column immediately, but the first column is worth recognizing early because it tells you whether an entry is a file or directory and who can use it. Later in this module, you will decode strings such as `drwxr-xr-x` and `-rw-r--r--`.

```bash
ls -l
```

```text
drwxr-xr-x  2 yourname yourname 4096 Mar 23 10:00 Desktop
drwxr-xr-x  3 yourname yourname 4096 Mar 23 09:45 Documents
-rw-r--r--  1 yourname yourname  220 Mar 23 08:30 notes.txt
```

The third navigation command is `cd`, which changes your working directory. You give it a destination, and the shell moves your session there if the destination exists and you have permission to enter it. Unlike opening a folder in a graphical interface, `cd` does not print a success message by default. That silence is normal, which is why many learners pair `cd` with `pwd` while building confidence.

From your home directory (when a `Documents` folder exists there):

```bash
cd Documents
pwd
```

```text
/home/yourname/Documents
```

| Command | Where It Takes You | Analogy |
|---------|-------------------|---------|
| `cd ~` or just `cd` | Your home directory | "Go back to my workstation" |
| `cd ..` | One level up, the parent directory | "Go to the room that contains this room" |
| `cd -` | The last directory you were in | "Go back to where I just was" |
| `cd /` | The root directory | "Go to the ground floor" |

These shortcuts are small, but they remove a lot of friction. `cd ..` is especially useful because it moves to the parent directory without requiring you to type the whole parent path. `cd -` is useful during troubleshooting because you often jump between a project directory and a log directory; it lets you bounce back to the previous location without remembering the exact spelling.

```bash
cd ~
pwd
```

```bash
cd ..
pwd
```

```bash
cd -
pwd
```

```bash
cd /
pwd
```

Before running this, what output do you expect from the last `pwd` if the previous command was `cd /`? Make the prediction first, then run it. This habit matters because terminal work is mostly hypothesis testing: you form a mental model of where you are, run a command, and compare the output with what you expected.

## Absolute and Relative Paths

A **path** is a written route to a file or directory. There are two kinds you will use constantly: absolute paths and relative paths. The difference is not academic; it decides whether a command works from anywhere or only from a particular starting directory.

An **absolute path** starts at the root directory `/` and gives the complete location. It is like a full street address: the address works no matter where you are standing when you read it. If a troubleshooting guide says to inspect `/var/log/syslog`, you can run that command from your home directory, from `/tmp`, or from a project directory, and the path still points to the same file.

```text
/home/yourname/Documents/report.txt
```

A **relative path** starts from your current working directory. It is like saying "two rooms down, then left"; the directions are shorter, but they depend on where you begin. Relative paths are excellent inside a project because they keep commands concise, but they are risky in scripts when the script might be launched from different places.

```text
Documents/report.txt
```

Here is the same destination reached in two different ways. The absolute path names the whole route from `/`, while the relative path works only because the shell is already in `/home/yourname`. If your current working directory were `/tmp`, `cd Documents` would look for `/tmp/Documents`, not `/home/yourname/Documents`.

```bash
pwd
```

```text
/home/yourname
```

Example paths — adjust `yourname` and directory names to match your machine:

```text
cd /home/yourname/Documents
cd Documents
```

| Symbol | Meaning | Example |
|--------|---------|---------|
| `/` | Root directory at the start, or path separator between names | `/home/yourname` |
| `~` | Your home directory | `~/Documents` means `/home/yourname/Documents` on many Linux systems |
| `.` | Current directory, or "here" | `./script.sh` means `script.sh` in this directory |
| `..` | Parent directory, or "up one level" | `../Downloads` means go up, then into `Downloads` |

The `.` symbol often appears when running scripts from the current directory, as in `./script.sh`. The shell uses it because many systems do not automatically search the current directory for commands. That behavior prevents accidental execution of a program just because it happens to have the same name as a common tool and lives in the folder where you are standing.

The `..` symbol is the cleanest way to move to a sibling location. If you are in `/home/user/projects/app/src` and need `/home/user/projects/app/README.md`, the relative path `../README.md` says "go to the parent directory, then read README." That is shorter than the absolute path and still precise because you know your current location.

Example relative path (run only when your current directory is a child of the folder that contains `README.md`):

```text
cat ../README.md
```

Which approach would you choose here and why: an absolute path to `/home/user/projects/app/README.md`, or the relative path `../README.md`? In an interactive project session, the relative path is usually faster and clearer. In an automation script that might run from several directories, the absolute path or a path derived from the script's own location is usually safer.

| Situation | Prefer | Why |
|-----------|--------|-----|
| Reading a known system log | Absolute path | The file has a stable machine-wide location |
| Moving inside one project tree | Relative path | Shorter commands reduce noise while context is clear |
| Writing a script for other users | Absolute or derived path | The script should not depend on the caller's current directory |
| Referring to personal configuration | `~` path | The path adapts to each user's home directory |
| Explaining a filesystem concept | Both forms | Comparing them builds the learner's mental map |

## Reading Files Without Flooding Your Terminal

Once you can point to a file, the next skill is choosing how to read it. The beginner temptation is to use one command for everything, but file-reading tools are shaped by file size and purpose. A short note, a long generated report, and a constantly growing log file deserve different commands.

`cat` displays the whole file. Its name comes from "concatenate" because it can join files together, but learners usually meet it first as a way to print a file to the terminal. It is excellent for small files where seeing the entire content is useful, such as a short note, a one-screen configuration snippet, or a tiny example manifest.

Example (create `notes.txt` first, or use any small file you already have):

```text
cat notes.txt
```

```text
This is my first note.
I wrote it in the terminal!
```

The tradeoff is that `cat` does not protect you from enormous output. If a log file has hundreds of thousands of lines, printing all of it can make your terminal hard to use and hide the recent lines you wanted. That is why experienced engineers ask a second question before reading: do I need the whole file, the beginning, or the end?

`head` shows the beginning of a file, ten lines by default. It is useful when the top of a file contains headers, metadata, comments, or the first entries in a report. You can change the number of lines with `-n`, which makes the command predictable and gentle even when the file is large.

```text
head long-file.txt
head -n 5 long-file.txt
```

`tail` shows the end of a file, also ten lines by default. This is one of the most important log-reading habits because many logs append new entries at the bottom. If a service crashed recently, the newest error is more likely near the end than near the top.

```text
tail log-file.txt
tail -n 20 log-file.txt
```

Think about it: you need to check the last few lines of a log file that is 10,000 lines long. Would you use a command that shows the whole file, or one that shows just the end? `tail` is designed for this situation because it lets you focus on the newest events without scrolling through everything that happened earlier.

| Tool | Best For | Avoid When | Example Use |
|------|----------|------------|-------------|
| `cat` | Small files where the whole content matters | Large logs or generated output | Read a short note or tiny config file |
| `head` | File headers, first records, initial comments | Recent log errors near the bottom | Check the first lines of a CSV or report |
| `tail` | Recent log events and appended files | Understanding the full structure of a file | Inspect the newest system log lines |

The same choice appears in Kubernetes work. When checking cluster access, reading a short kubeconfig snippet might be reasonable with `cat`, although you should be careful not to expose secrets on a shared screen. When reading node or container logs under `/var/log/`, `tail` is usually safer because the newest entries carry the strongest troubleshooting signal. The command is simple, but the decision behind it is operational judgment.

```bash
tail -n 20 /var/log/syslog
```

```bash
ls -l ~/.kube/config
```

The second command checks that the file exists and shows its permissions without printing tokens or certificates. Many configuration files contain tokens, certificates, usernames, or cluster endpoints. When the file may include secrets, prefer reading only the part you need, avoid pasting output into chat systems, and consider whether a safer inspection command exists.

## Creating Directories, Files, and Hidden Configuration

Navigation becomes more useful when you can create a small structure of your own. `mkdir` creates directories, and `touch` creates an empty file if it does not already exist. These commands are simple, but the distinction matters: applications that expect a directory cannot write logs into a regular file, and scripts that expect a file cannot read useful content from an empty directory.

```bash
mkdir recipes
```

The `mkdir` command creates one directory at the path you provide. If the parent directory exists and you have permission to write there, the command succeeds silently. If the parent path does not exist, plain `mkdir` fails because it does not invent the missing middle of the tree unless you ask it to.

```bash
mkdir -p recipes/italian/pasta
```

The `-p` option means "create parent directories as needed." It is common in setup scripts and labs because it makes the command safe to run even when part of the structure already exists. Without `-p`, creating `recipes/italian/pasta` would fail if `recipes/` or `recipes/italian/` had not been created first.

```bash
touch shopping-list.txt
```

`touch` creates a new empty file, but it also updates the timestamp when the file already exists. That dual behavior is useful, but it can surprise beginners. If you expected `touch` to add content, nothing will appear inside the file; it is more like placing a blank recipe card on the counter than writing the recipe.

Hidden files are files or directories whose names start with a dot, such as `.bashrc`, `.zshrc`, `.config/`, `.ssh/`, `.gitconfig`, and `.kube/`. They are hidden from plain `ls` output because configuration files are important but usually not part of everyday browsing. Hiding them reduces clutter and lowers the chance that a beginner deletes a shell or SSH configuration while cleaning up normal documents.

```bash
ls
```

```text
Documents    Downloads    Music
```

```bash
ls -a
```

```text
.   ..   .bashrc   .config   Documents   Downloads   Music
```

| File | What It Does |
|------|-------------|
| `.bashrc` | Settings for your bash terminal |
| `.zshrc` | Settings for your zsh terminal, often the default shell on macOS |
| `.config/` | Directory containing application configurations |
| `.ssh/` | SSH keys and secure connection configuration |
| `.gitconfig` | Git identity and behavior settings |
| `.kube/` | Common directory for Kubernetes client configuration |

Hidden does not mean secret. A dotfile is hidden from default directory listings, but any user with enough filesystem permission can still read it. This distinction matters for files such as `.env`, `.ssh/config`, or `~/.kube/config`, because naming a file with a leading dot does not protect credentials. Protection comes from permissions, careful sharing, and not printing sensitive content where it does not belong.

```bash
ls -a ~
```

```bash
ls -l ~/.kube
```

Pause and predict: if plain `ls ~` does not show `.bashrc`, will `cat ~/.bashrc` still work when the file exists and you have permission? Yes, because hidden status affects listing behavior, not path resolution. A hidden file can still be addressed directly by its full or relative path.

## Reading Permission Strings from `ls -l`

File permissions are how Unix-like systems express who can do what. At this stage, you only need to read the permission string, not change it. That skill is enough to diagnose many beginner errors: "permission denied" when entering a directory, a script that cannot run, or a sensitive file that is readable by more people than intended.

```text
drwxr-xr-x  2 yourname yourname 4096 Mar 23 10:00 Desktop
-rw-r--r--  1 yourname yourname  220 Mar 23 08:30 notes.txt
```

The first character tells you the type of entry. A `d` means directory, while `-` means a regular file. The next nine characters come in three groups of three: permissions for the owner, permissions for the group, and permissions for everyone else. Each group uses `r` for read, `w` for write, `x` for execute or directory entry, and `-` when that permission is absent.

```text
-  rw-  r--  r--
|  |    |    |
|  |    |    └── Others (everyone else) permissions
|  |    └── Group permissions
|  └── Owner (you) permissions
└── File type (- = file, d = directory)
```

| Letter | Permission | For Files | For Directories |
|--------|-----------|-----------|-----------------|
| `r` | Read | Can see the contents | Can list what's inside |
| `w` | Write | Can change the contents | Can add or remove files |
| `x` | Execute | Can run it as a program | Can enter the directory with `cd` |
| `-` | No permission | Cannot do that action | Cannot do that action |

The directory behavior is the part many beginners miss. Execute on a file means "can run it as a program," but execute on a directory means "can enter or traverse it." A directory may be readable but not enterable, or enterable but not listable, depending on the exact bits. You do not need all edge cases today, but you should know that `x` on a directory is not about running the directory.

```text
-rw-r--r--  notes.txt
```

In this example, the first `-` says `notes.txt` is a regular file. The owner segment `rw-` means the owner can read and write but not execute it as a program. The group segment `r--` means group members can read but not write. The others segment `r--` means everyone else with access to the path can also read it.

```text
drwxr-xr-x  Desktop
```

In this directory example, `d` says the entry is a directory. The owner has `rwx`, so the owner can list it, add or remove entries, and enter it. Group and others have `r-x`, so they can list and enter it but cannot add or remove files there. This is a common shape for directories that should be visible but not writable by everyone.

| Permission String | Plain-English Reading | Common Interpretation |
|-------------------|-----------------------|-----------------------|
| `-rw-r--r--` | Owner can read and write; group and others can read | Normal non-secret text file |
| `-rw-------` | Owner can read and write; nobody else has access | Sensitive personal file |
| `drwxr-xr-x` | Owner controls directory; others can list and enter | Common user-visible directory |
| `drwx------` | Owner alone can list, write, and enter | Private directory such as some key stores |
| `-rwxr-xr-x` | Owner can run and edit; others can run and read | Executable script or program |

Permissions are like keys in the kitchen. The head chef may have the key to open, edit, and reorganize every drawer. A sous-chef may be allowed to read the recipe cards but not replace them. Visitors may be allowed to see a posted menu but not enter the storage room. The permission string compresses that policy into a short form you can read quickly during troubleshooting.

```bash
ls -l recipes/appetizers/
```

```bash
ls -ld recipes
```

The `-d` option in the second command is worth noticing. Without it, `ls -l recipes` lists the contents of the `recipes` directory. With `-d`, it lists the directory entry itself, including permissions on the directory. When diagnosing why you cannot enter or write to a directory, `ls -ld` is often the clearer command.

## Worked Example: Trace the Path Before You Touch the File

The safest way to use filesystem commands is to slow down for a moment and translate the command into plain language before pressing Enter. This is especially useful when a command creates, overwrites, or depends on a path. Beginners often ask whether memorizing more commands is the fastest way to improve, but the better early skill is learning to narrate what a command will do to the tree.

Exercise scenario: you are inside `~/kubedojo-practice`, and someone asks you to inspect `recipes/appetizers/bruschetta.txt`. The path does not start with `/`, so it is relative to your current working directory. The shell will start where you are standing, look for a directory named `recipes`, then a directory named `appetizers`, then a file named `bruschetta.txt`. If any one of those names is missing or misspelled, the command fails at that step.

```bash
pwd
```

```text
/home/yourname/kubedojo-practice
```

Example relative path (run after creating the practice tree in the hands-on exercise, or when that file already exists):

```text
cat recipes/appetizers/bruschetta.txt
```

That command reads cleanly once you translate it: from the current project directory, open the appetizer recipe file and print its contents. If you instead ran the same command from your home directory, the shell would look for `/home/yourname/recipes/appetizers/bruschetta.txt`, because the relative path would start from a different place. The command did not change, but the starting point changed, which is why `pwd` is not a beginner crutch; it is part of the reasoning process.

Now compare that with the absolute version. An absolute path is longer, but the shell does not need your current working directory to interpret it. The command below points to one concrete location from the root of the filesystem tree, so it can work from your home directory, the project directory, or a log directory, provided the file exists and permissions allow access.

Example absolute path — adjust `yourname` to match your account:

```text
cat /home/yourname/kubedojo-practice/recipes/appetizers/bruschetta.txt
```

Neither style is universally better. The relative path is easier to type and clearer when everyone is already working inside the same project. The absolute path is safer in documentation, troubleshooting notes, and scripts where the starting location may be unclear. That tradeoff shows up constantly in cloud engineering because a command copied into a runbook should behave the same way for the next engineer who uses it during an incident.

The same trace method works for `mkdir -p`. When you run `mkdir -p kubedojo-practice/recipes/desserts`, the shell starts from the current directory and asks the filesystem to ensure that each named directory exists in order. If `kubedojo-practice` already exists, it keeps going. If `recipes` exists, it keeps going. If `desserts` is missing, it creates that final directory. The option changes the behavior from "create exactly this one directory" to "make this path usable as a directory tree."

```bash
mkdir -p kubedojo-practice/recipes/desserts
```

This is why `mkdir -p` is common in setup instructions. It avoids forcing learners to create every parent directory manually, and it makes repeated practice less fragile. If you run the same command again, it should still leave the directory structure in the desired state. That property, where a command can be repeated without causing unnecessary change, is valuable in automation even though this module is only introducing the beginner version of the idea.

`touch` deserves the same careful reading because it can be misunderstood. In the lab, `touch recipes/desserts/tiramisu.txt` creates a blank file when the file does not exist. If it already exists, the command does not erase the ingredients; it updates the file's timestamp. That makes `touch` a poor command for adding content but a useful command for creating placeholders before another tool writes to them.

```bash
touch recipes/desserts/tiramisu.txt
```

When you redirect output with `>`, the stakes change. The command `echo "Ingredients: coffee, mascarpone, ladyfingers, cocoa" > recipes/desserts/tiramisu.txt` sends the text into the file, replacing the previous contents. That is perfect in a fresh lab file because you control the content. In a real configuration file, the same redirect can destroy existing settings, so you should pause before using it on anything important.

```bash
echo "Ingredients: coffee, mascarpone, ladyfingers, cocoa" > recipes/desserts/tiramisu.txt
```

Pause and predict: if `tiramisu.txt` already contains three lines and you run the redirect command above, how many ingredient lines will remain afterward? The answer is one, because `>` replaces the file content with the command output. Later terminal modules will introduce append redirection and editors, but the safe habit begins here: know whether a command reads, creates, replaces, or only changes metadata.

This "read, create, replace, or move" classification also helps with command fear. `pwd` only reads your current location. `ls` reads directory metadata. `cat`, `head`, and `tail` read file contents. `mkdir` creates directories. `touch` may create a file or update a timestamp. `cd` changes your shell's current location but does not move files on disk. Once you classify a command this way, you can decide how cautious you need to be.

| Command | Main Effect | Risk Level for Beginner Practice |
|---------|-------------|----------------------------------|
| `pwd` | Reads current working directory | Very low because it changes nothing |
| `ls` | Reads directory entries | Very low because it changes nothing |
| `cd` | Changes shell location | Low because it does not edit files |
| `cat` | Prints file contents | Low, but be careful with secrets |
| `head` | Prints the beginning of a file | Low, with the same secret caution |
| `tail` | Prints the end of a file | Low, especially useful for logs |
| `mkdir -p` | Creates missing directories | Moderate because it changes the tree |
| `touch` | Creates an empty file or updates timestamp | Moderate because it changes metadata |

The secret caution in the table is not theoretical. Kubernetes client configuration may include certificate data, tokens, context names, user names, and cluster addresses. A beginner who runs `cat ~/.kube/config` on a shared screen may reveal more than intended. You still need to know where the file lives, but reading the whole thing into the terminal is not always the right inspection method.

When paths include hidden directories, trace them exactly the same way. The path `~/.kube/config` starts by expanding `~` to the user's home directory, then enters the hidden `.kube` directory, then names the `config` file. The dot does not make `.kube` harder for the shell to find. It only hides the directory from a default listing, which is why direct commands can work even when plain `ls` did not show the name.

```bash
ls -a ~
```

```bash
ls -l ~/.kube
```

There is another subtle lesson here: a path can be correct while access still fails. If the path exists but permissions do not allow you to read the file or enter the directory, the shell reports a permission error instead of a missing-file error. That difference matters during diagnosis. "No such file or directory" points toward spelling, starting location, or missing parents. "Permission denied" points toward ownership, permission bits, or a directory on the path that cannot be traversed.

```bash
ls -ld ~/.ssh
```

```bash
ls -l ~/.ssh
```

The first command asks about the `.ssh` directory itself, while the second asks about what is inside it. If you cannot enter a directory, inspecting the directory entry with `ls -ld` is often more useful than trying to list the contents. This pattern carries into system directories as well, although you should be careful and avoid changing files under `/etc` or `/var` unless a lab or administrator explicitly tells you to.

In Kubernetes work, the filesystem often appears during debugging before the Kubernetes-specific command does. A control-plane node may have static Pod manifests under `/etc/kubernetes/manifests/`, and kubelet-managed logs may appear under `/var/log/pods/` or `/var/log/containers/` depending on the environment. Even when you later use `kubectl logs`, the mental model is the same: logs are records written somewhere, and paths are how the machine names those places.

```bash
ls -l /etc/kubernetes/manifests/
```

```bash
tail -n 20 /var/log/syslog
```

Those commands may not work on every personal machine because not every machine is a Kubernetes node, and not every Linux distribution uses the same log filenames. That is fine. The lesson is not that you should memorize every possible production path today. The lesson is that when documentation gives you a path, you can decide whether it is absolute, relative, user-specific, hidden, a file, a directory, or a log-like target.

Before you move on, practice explaining one command out loud: `tail -n 20 /var/log/syslog`. A good translation is "starting from the root directory, go into `var`, then `log`, then read the newest twenty lines from `syslog`." That translation contains the path type, the route, the file target, and the reason `tail` was chosen. If you can make that translation, you are no longer just copying terminal symbols.

There is one more layer to that translation: every path has checkpoints. For `/var/log/syslog`, the shell needs `/` to exist, then `var`, then `log`, then the final file. For `recipes/appetizers/bruschetta.txt`, it needs the current directory to be what you think it is, then `recipes`, then `appetizers`, then the final file. When a command fails, those checkpoints give you a debugging plan instead of leaving you with a vague sense that "the terminal is broken."

The first checkpoint is your starting point, so `pwd` is the first repair command when a relative path fails. If the starting point is wrong, every relative path after it is also wrong. The second checkpoint is each parent directory, which you can inspect with `ls` one level at a time. The final checkpoint is the target itself, where you decide whether it should be a file, a directory, or a hidden name that requires `ls -a` to appear in listings.

```bash
pwd
ls
ls recipes
ls recipes/appetizers
```

Those four commands are deliberately plain. They do not fix anything by themselves, but they turn confusion into evidence. If `ls recipes` fails, the problem is near the project root. If `ls recipes/appetizers` works but `cat recipes/appetizers/bruschetta.txt` fails, the parent directories are probably correct and the final filename or permissions deserve attention. Good terminal troubleshooting is often this kind of narrowing.

The same narrowing helps with permission problems. Suppose a path exists, but reading the final file fails with "Permission denied." You can inspect the file with `ls -l` if you can reach it, and you can inspect parent directories with `ls -ld` if entering the path is the problem. A missing read bit on the file is different from a missing execute bit on a parent directory, even though both can stop you from getting useful content.

```bash
ls -ld recipes
ls -ld recipes/appetizers
ls -l recipes/appetizers/bruschetta.txt
```

Notice that this checkpoint method does not require advanced tools. It uses only the commands you have already learned, but it uses them in a diagnostic order. That is the difference between command memorization and operational skill. A memorized command gives you one attempt; a mental model gives you the next question when the first attempt fails.

You can also use checkpoints to avoid accidental writes. Before creating a file with `touch` or replacing content with `>`, run `pwd` and `ls` to confirm the destination. In a beginner lab, the worst mistake is usually a messy practice directory. In professional work, writing to the wrong path can overwrite a configuration file, create a directory structure in the wrong place, or leave a script writing logs where nobody expects to find them.

This carefulness is not meant to make the terminal feel dangerous. It is meant to make it feel inspectable. A graphical file browser protects you by showing context visually; the terminal protects you by making every command explicit. Once you learn to read those commands as path operations, you gain a form of control that transfers directly to remote servers, build systems, CI logs, and Kubernetes nodes where no graphical interface is available.

## When This Doesn't Apply

These commands are the foundation, but they are not the whole file-management universe. Graphical file browsers are still useful for visual inspection, drag-and-drop work, and previewing media. Integrated development environments are better for editing multi-file projects. Search tools such as `find`, `grep`, and `rg` become more useful once the number of files grows beyond what you can scan with `ls`.

The pattern is to use the terminal when precision, repeatability, remote access, or automation matters. Use `pwd`, `ls`, `cd`, `cat`, `head`, `tail`, `mkdir`, and `touch` when you need a reliable command that you can repeat, paste into notes, or use over SSH on a server. Use a graphical tool when the task is exploratory and the machine has a desktop environment available.

| Use This | When | Why It Works |
|----------|------|--------------|
| Terminal navigation | You need exact paths or remote access | Commands work over SSH and can be repeated |
| GUI file browser | You need visual previews or drag-and-drop | The interface is optimized for browsing human media |
| `cat`, `head`, `tail` | You need quick text inspection | They are lightweight and available on most Unix-like systems |
| Specialized search tools | You need to find content across many files | Listing one directory at a time becomes too slow |

The anti-pattern is pretending one tool fits every job. Printing a massive log with `cat`, manually clicking through a server over a remote desktop, or using relative paths in a script with no control over the starting directory all come from ignoring the task shape. The better habit is to ask: am I locating something, inspecting something, creating structure, or diagnosing access?

## When You'd Use This vs Alternatives

For a quick decision, start with the question you need answered. If you need to know where you are, use `pwd`. If you need to know what is nearby, use `ls` or `ls -la`. If you need to move, use `cd` with a path that fits the context. If you need to read a small file, use `cat`; if you need the beginning, use `head`; if you need the latest log entries, use `tail`.

```text
Need to answer a filesystem question?
|
+-- Where am I? ------------------> pwd
|
+-- What is here? ----------------> ls
|                                  ls -la
|
+-- How do I move? ---------------> cd <path>
|                                  cd ..
|                                  cd ~
|
+-- What is inside this file? ----> cat <small-file>
|                                  head -n <count> <file>
|                                  tail -n <count> <file>
|
+-- Who can access it? -----------> ls -l <file>
                                   ls -ld <directory>
```

| Need | First Command to Try | Safer Follow-Up |
|------|----------------------|-----------------|
| Confirm your location | `pwd` | Compare the path with the command you planned to run |
| Inspect a directory | `ls` | Use `ls -la` when hidden files may matter |
| Enter a known directory | `cd path` | Run `pwd` afterward while learning |
| Read a tiny file | `cat file` | Use `head` if you are unsure about size |
| Inspect recent log lines | `tail -n 20 file` | Increase the line count only if needed |
| Diagnose access | `ls -l file` | Use `ls -ld directory` for the directory itself |

## Did You Know?

- **The `/` root directory is called "root" because the directory tree grows from one starting point.** Unlike a real tree, diagrams often draw the root at the top and branches below it, which is why paths appear to grow downward from `/`.
- **The `~` shortcut expands in shell contexts to a user's home directory.** That is why `~/.kube/config` can describe a different concrete file for each user while still being correct documentation.
- **Linux exposes many non-document things through file-like paths.** Device entries under `/dev` and process information under `/proc` are part of the reason ordinary file tools can inspect so much system state.
- **Kubernetes troubleshooting still depends on ordinary filesystem habits.** Static Pod manifests under `/etc/kubernetes/manifests/`, kubeconfig files under `~/.kube/`, and node logs under `/var/log/` are all easier to investigate once paths feel normal.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Trying to `cd` into a regular file | The path exists, so the beginner assumes it can be entered like a folder | Use `cat`, `head`, or `tail` for files; use `cd` only for directories |
| Forgetting the space between command and path | The command and argument visually blend together while typing quickly | Write commands as verb plus target, such as `cd Documents`, and use Tab completion |
| Using backslashes `\` in Linux or macOS paths | Windows examples use backslashes, so the habit carries over | Use forward slashes, such as `/home/you/Documents`, in Unix-like shells |
| Creating a file when a program expects a directory | `touch` and `mkdir` both create names, but the resulting object type differs | Use `mkdir` for containers and `touch` for empty files, then confirm with `ls -l` |
| Getting lost in nested directories | Relative paths stop matching the learner's mental model | Run `pwd`, list nearby files with `ls`, or return home with `cd ~` before continuing |
| Missing a hidden configuration file | Plain `ls` intentionally hides names that start with a dot | Run `ls -a` or address the file directly, such as `cat ~/.bashrc` |
| Printing a huge log with `cat` | `cat` is remembered as the file-reading command, so it gets used for every file size | Use `tail -n 20` for recent log entries or `head -n 20` for the beginning |
| Misreading directory execute permission | The letter `x` sounds like "run," which is confusing for directories | Remember that `x` on a directory means you can enter or traverse it |

## Quiz

<details>
<summary>Question 1: You are reading documentation that tells you to inspect `~/.kube/config`, but your terminal is currently in `/var/log/pods/`. Where does `~` point, and why is it useful here?</summary>

`~` points to the current user's home directory, such as `/home/yourname` on many Linux systems or `/Users/yourname` on macOS. The current working directory does not change that expansion, so the shell does not look under `/var/log/pods/`. This shortcut is useful because documentation can refer to a user's personal Kubernetes configuration without knowing the user's exact account name. It also keeps the command portable across machines where home directories have different prefixes.

</details>

<details>
<summary>Question 2: A deployment script works only when launched from the project root because it uses `cd config/`. What path problem is the script relying on, and what would make it safer?</summary>

The script relies on a relative path, so `config/` is resolved from whatever directory the caller happens to be in. When the script starts somewhere else, the shell looks for a different `config` directory and the command fails. A safer script would use an absolute path or derive the path from the script's own location before changing directories. The key diagnosis is that relative paths are context-dependent, while absolute paths start from `/`.

</details>

<details>
<summary>Question 3: You downloaded a project that includes `.env`, but plain `ls` does not show it. What should you run, and what security assumption should you avoid?</summary>

Run `ls -a` to include hidden names that start with a dot. The file is hidden from default listings because dotfiles are usually configuration, not because they are protected. You should avoid assuming `.env` is secret merely because it is hidden. If it contains credentials, permissions and careful handling matter more than the leading dot.

</details>

<details>
<summary>Question 4: You are in `/home/user/projects/app/src` and need to read `/home/user/projects/app/README.md`. What relative command would work, and why might it be preferable interactively?</summary>

`cat ../README.md` would work because `..` moves from `src` to its parent directory, `app`, and then names the `README.md` file. In an interactive session, the relative path is shorter and easier to type than the full absolute path. It is also clear because you already know your current location inside the project. In a script, you would be more cautious because the starting directory may not be stable.

</details>

<details>
<summary>Question 5: A sensitive file has permissions `-rw-r-----`, is owned by `admin`, and belongs to group `support`. What can a user in `support` do, and what blocks modification?</summary>

A user in the `support` group can read the file because the group permission segment is `r--`. They cannot write to it because the group segment does not include `w`. The owner segment `rw-` allows `admin` to read and modify the file, but those owner permissions do not automatically apply to group members. This is a useful least-privilege shape when support staff need to inspect information without changing it.

</details>

<details>
<summary>Question 6: A node log has grown very large, and you need the newest errors from the bottom. Which command shape should you choose, and why is `cat` a poor first choice?</summary>

Use a command such as `tail -n 20 /var/log/syslog` so the terminal prints only the newest lines. `cat /var/log/syslog` is a poor first choice because it prints the whole file, which can flood the terminal and bury the recent error you were looking for. `tail` matches the structure of append-style logs, where new entries are written at the end. You can increase the number after `-n` if the first view is too small.

</details>

<details>
<summary>Question 7: You run `ls -l recipes` and see the files inside the directory, but you wanted the permissions on the `recipes` directory itself. What command should you use, and what does it change?</summary>

Use `ls -ld recipes`. The `-l` option asks for long format, while `-d` tells `ls` to show the directory entry itself instead of listing its contents. This matters when diagnosing whether you can enter, list, or write inside the directory. Without `-d`, you may accidentally inspect the children and miss the permission problem on the parent.

</details>

## Hands-On Exercise: Building Your First Directory Structure

In this exercise, you will create a small recipe project, navigate through it, read files, inspect permissions, and reveal hidden configuration files. The scenario is intentionally ordinary because the mechanics are the same when the file is a recipe, a Kubernetes manifest, or a node log. Work slowly enough to predict each command's output before you run it, then compare the terminal response with your prediction.

### Setup

Start from your home directory so the paths in the exercise are predictable. If the practice directory already exists from an earlier run, you can choose a different name or inspect what is already there before continuing. The commands below are safe for a beginner lab because they stay inside your home directory.

```bash
cd ~
pwd
```

### Tasks

1. **Create the project directories.** Use `mkdir -p` so the command creates every parent directory needed for the nested structure.

```bash
mkdir -p kubedojo-practice/recipes/appetizers
mkdir -p kubedojo-practice/recipes/main-courses
mkdir -p kubedojo-practice/recipes/desserts
```

<details>
<summary>Solution notes for task 1</summary>

The `-p` option allows each command to create parent directories that do not exist yet. After these commands, `kubedojo-practice` should contain a `recipes` directory, and `recipes` should contain three category directories. If a command prints no output, that usually means it succeeded.

</details>

2. **Navigate into the project and list its top level.** Confirm that the structure begins where you expected.

```bash
cd kubedojo-practice
ls
```

```text
recipes
```

<details>
<summary>Solution notes for task 2</summary>

The `cd` command changes your working directory to the practice project. Running `ls` afterward should show `recipes` because that is the only top-level item you created. If you see an error, run `pwd` and verify that the practice directory was created under your home directory.

</details>

3. **Create recipe files in each category.** These start as empty files, which is exactly what `touch` creates.

```bash
touch recipes/appetizers/bruschetta.txt
touch recipes/main-courses/pasta-carbonara.txt
touch recipes/desserts/tiramisu.txt
```

<details>
<summary>Solution notes for task 3</summary>

Each path is relative to `kubedojo-practice`, which is why it starts with `recipes/` instead of `/home/...`. If one command fails with "No such file or directory," inspect the directory names with `ls recipes` and check for a spelling mismatch.

</details>

4. **Write simple content into the files.** The `>` character redirects the output of `echo` into the target file.

```bash
echo "Ingredients: bread, tomatoes, basil, olive oil" > recipes/appetizers/bruschetta.txt
echo "Ingredients: pasta, eggs, pancetta, parmesan" > recipes/main-courses/pasta-carbonara.txt
echo "Ingredients: coffee, mascarpone, ladyfingers, cocoa" > recipes/desserts/tiramisu.txt
```

<details>
<summary>Solution notes for task 4</summary>

The `>` redirect replaces the file's contents with the text produced by `echo`. That is useful here because each file is new. In real work, be careful with `>` because it overwrites existing content; later modules will cover safer editing habits.

</details>

5. **Read each file with a different tool.** The files are tiny, but the point is to practice choosing the tool intentionally.

```bash
cat recipes/appetizers/bruschetta.txt
head recipes/main-courses/pasta-carbonara.txt
tail recipes/desserts/tiramisu.txt
```

<details>
<summary>Solution notes for task 5</summary>

All three commands should print one ingredient line because each file has only one line. In larger files, the commands would behave differently: `cat` would print everything, `head` would print the beginning, and `tail` would print the end. This lab keeps the files small so you can focus on paths.

</details>

6. **Inspect permissions on a file and a directory.** Predict the first character before you run each command.

```bash
ls -l recipes/appetizers/
ls -ld recipes
```

<details>
<summary>Solution notes for task 6</summary>

The file entry for `bruschetta.txt` should begin with `-` because it is a regular file. The entry for `recipes` should begin with `d` because it is a directory. The exact read, write, and execute bits may vary by system defaults, but you should be able to split them into owner, group, and others.

</details>

7. **Reveal hidden files in your home directory.** Compare the output with and without `-a`.

```bash
ls ~
ls -a ~
```

<details>
<summary>Solution notes for task 7</summary>

The second command should show names beginning with dots if your home directory contains shell or application configuration. You may see `.bashrc`, `.zshrc`, `.config`, `.ssh`, `.gitconfig`, or different dotfiles depending on your machine. The important lesson is that hidden files are still reachable by path.

</details>

8. **Move around and recover your location.** Use `pwd` after each movement until the mental model feels automatic.

```bash
cd recipes/desserts
pwd
cd ..
pwd
cd ~
pwd
```

<details>
<summary>Solution notes for task 8</summary>

The first `pwd` should end in `kubedojo-practice/recipes/desserts`. After `cd ..`, the path should end in `kubedojo-practice/recipes`. After `cd ~`, the path should be your home directory. If any prediction is wrong, pause and explain which relative path assumption changed.

</details>

### Success Criteria

You've completed this exercise when you can:

- [ ] Navigate to your home directory with `cd ~`.
- [ ] Create nested directories with `mkdir -p`.
- [ ] Create files with `touch`.
- [ ] Write content to files with `echo "text" > file`.
- [ ] Read files with `cat`, `head`, and `tail`.
- [ ] Check file permissions with `ls -l`.
- [ ] Check directory permissions with `ls -ld`.
- [ ] View hidden files with `ls -a`.
- [ ] Navigate with `cd`, `cd ..`, and `cd ~`.

## Sources

- [RHEL Storage Administration Guide: File systems](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/7/html/storage_administration_guide/ch-filesystem)
- [The /proc Virtual Filesystem](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/4/html/reference_guide/ch-proc)
- [A beginner's guide to navigating the Linux filesystem](https://www.redhat.com/en/blog/navigating-linux-filesystem)
- [kubectl config reference](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_config)
- [kubeadm implementation details](https://kubernetes.io/docs/reference/setup-tools/kubeadm/implementation-details/)
- [Running Kubernetes node components standalone](https://kubernetes.io/docs/tutorials/cluster-management/kubelet-standalone/)
- [Home directory](https://en.wikipedia.org/wiki/Home_directory)
- [Managing file system permissions](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/8/html/configuring_basic_system_settings/managing-file-system-permissions_configuring-basic-system-settings)
- [Logging Architecture](https://kubernetes.io/docs/concepts/cluster-administration/logging/)
- [Least Privilege Principle](https://owasp.org/www-community/controls/Least_Privilege_Principle)

## Next Module

**Next Module**: [Module 0.5: Editing Files](../module-0.5-editing-files/) — Learn how to put real content inside files using a terminal text editor.
