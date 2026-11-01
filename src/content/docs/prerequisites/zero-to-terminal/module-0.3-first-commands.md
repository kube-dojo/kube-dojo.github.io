---
title: "Module 0.3: First Terminal Commands"
slug: prerequisites/zero-to-terminal/module-0.3-first-commands
revision_pending: false
sidebar:
  order: 4
lab:
  id: "prereq-0.3-first-commands"
  url: "https://killercoda.com/kubedojo/scenario/prereq-0.3-first-commands"
  duration: "20 min"
  difficulty: "beginner"
  environment: "ubuntu"
---
> **Complexity**: `[MEDIUM]` - Long-form practice module: follow along and type what you see
>
> **Time to Complete**: 80–100 minutes (read + Killercoda lab)
>
> **Prerequisites**: [Module 0.2: What is a Terminal?](../module-0.2-what-is-a-terminal/) — You should be able to open a terminal and type commands.

---

## What You'll Be Able to Do

After this module, you will be able to practice the following skills in a real terminal session and explain why each command is useful before you rely on it in later labs:

- **Navigate** directory paths with `pwd`, `ls`, and `cd`, then diagnose when a command ran in the wrong place
- **Create** folders and files with `mkdir`, `touch`, `cp`, and `mv`, then compare copy versus move behavior
- **Delete** files safely with `rm` by evaluating risk, confirming targets, and cleaning up only intended paths
- **Combine** command output with pipes and filters to inspect files without opening a graphical app

## Why This Module Matters

Hypothetical scenario: you are following a setup guide for a Kubernetes practice lab, and the guide tells you to create a configuration folder, copy a sample file, rename it, and remove the old version. Those relative paths depend on your current location. If you are in the wrong directory, a command may still succeed, but the file lands somewhere surprising, the copy is not where the next step expects it, or the cleanup command removes a path you meant to keep.

These commands help you navigate project folders and prepare files for later work. A relative path depends on the current directory, so check your location and the target before changing anything.

You will practice `pwd`, `ls`, `cd`, `mkdir`, `touch`, `cp`, `mv`, `rm`, and `clear`, then use pipes to connect commands. Check your location before acting, and inspect deletion targets before removing them.

If a result differs from the guide, check where you are, what is there, and what changed. The exercises ask you to explain a command's target and verify its result.

## Opening Your Terminal and Reading the Prompt

Before we run commands, open a terminal in the environment you are using for this course. On macOS, press `Cmd + Space`, type "Terminal", and press Enter, or open Terminal from Applications > Utilities. On Ubuntu Desktop, `Ctrl + Alt + T` opens a terminal. Other Linux desktops may use different shortcuts. On Windows, use the linked Ubuntu lab or a Linux shell such as Windows Subsystem for Linux for this lesson.

The commands and options in this lesson use a Unix-style shell and utilities, as in the Ubuntu lab. On Windows, use an appropriate Linux environment such as WSL for these examples; native PowerShell has different commands and option conventions. Do not assume that a similar-looking command has the same behavior in another shell.

**In the linked Ubuntu lab:** its task checks look for files in the `ubuntu` account's home when that account exists. If the terminal prompt starts with `root@`, run the following command before starting the lab tasks. It switches to the existing Ubuntu account; your prompt should then start with `ubuntu@`, and `pwd` should show `/home/ubuntu`. This setup step is specific to the linked lab; do not run it in your own local terminal.

```bash
su - ubuntu
pwd
```

The [lab's verifier](https://github.com/kube-dojo/kubedojo-labs/blob/fe6f47c3888ec1b7bc079781242d44e7f99e25ce/prereq-0.3-first-commands/step1/verify.sh) checks the account's home directory. A file created under `/root` will not satisfy that check when it expects `/home/ubuntu`, even if the file contains the right answer. Stay in the Ubuntu account for all three lab tasks.

When the shell is ready, it displays a prompt, often ending in `$` or `%`; the root account in the linked lab may use `#`. The prompt's contents depend on the shell and its configuration. Read it as an invitation to enter a command, rather than text that must exactly match the example below.

```
username@computername ~ $
```

A prompt may include a user name, computer name, or current directory, but its contents are configurable. In many Unix-style shells, `~` is shorthand for your home directory. Use the prompt as a clue and `pwd` to check the working directory before acting.

Notice that a terminal command is just text followed by Enter. Some commands have flags, which are small options such as `-l` or `-a` that change behavior, and some commands have arguments, which are the files or directories the command should act on. The pattern is not universal, but a useful beginner model is "command, options, target." When a command surprises you later, ask which part of that pattern you may have misread.

## Navigate Directory Paths with `pwd`, `ls`, and `cd`

Your computer organizes files in a tree structure, which means every file and folder has a location relative to a top-level root. A graphical file manager hides much of that structure behind windows and icons, but the terminal asks you to name locations directly. That may feel strict at first, yet the strictness is useful: once you can describe a location as a path, you can automate it, copy it into documentation, and run the same operation on a remote server where no graphical desktop exists.

This macOS-style example shows the relationship between root, home and a user's folders. Linux uses different top-level directory names; the path relationships are the part to follow here.

```
/ (the root -- the building itself)
├── Users/
│   └── yourname/          ← This is your "home directory"
│       ├── Desktop/
│       ├── Documents/
│       ├── Downloads/
│       └── Pictures/
├── Applications/
└── System/
```

In this restaurant-floor-plan analogy, the root directory is the building, your home directory is your private office, and folders such as Desktop or Documents are rooms inside that office. The terminal always has a current working directory, which is the room where relative paths begin. If you say `Documents`, the shell interprets that relative to where you are now; if you say `/Users/yourname/Documents`, you are giving a full path from the building entrance.

The first command is `pwd`, which stands for print working directory. It answers "Where am I?" before you create, copy, move, or delete anything. For example, a wrong checkout can lead you to edit a different manifest from the one you intended.

```bash
pwd
```

The expected output is a full path to your current directory, and yours will differ because your user name and operating system are specific to your machine:

```
/Users/yourname
```

On Linux, the same idea often appears as `/home/yourname`, while a Windows PowerShell prompt may show a path like `C:\Users\yourname`. The exact spelling is less important than the habit: read the output as a location, not as decoration. If you expected to be inside a project folder and `pwd` says you are still in your home directory, stop and navigate before you create files.

The second command is `ls`, which lists what is in the current directory. It is the terminal equivalent of opening a drawer and looking inside. Plain `ls` gives you names, which is often enough when you are checking whether a folder or file exists. Because it acts on your current directory by default, it pairs naturally with `pwd`: first ask where you are, then ask what is there.

```bash
ls
```

Expected output will show the visible entries in your own home directory, so treat this as a shape example rather than text that must match exactly:

```
Desktop    Documents    Downloads    Music    Pictures
```

The long form, `ls -l`, shows more context, including permissions, ownership, size, and modification time. You do not need to understand every column yet, but you should notice that flags change the amount of information a command returns. The rightmost column is the name, and the date tells you when the item was last changed. During real troubleshooting, that date can be the clue that a configuration file changed shortly before a failure.

```bash
ls -l
```

The long-format output below is only a sample, but it shows the kind of metadata `ls -l` adds beside each name:

```
drwx------   4 yourname  staff   128 Mar 15 10:30 Desktop
drwx------   5 yourname  staff   160 Mar 20 09:15 Documents
drwx------  12 yourname  staff   384 Mar 22 14:45 Downloads
```

Pause and predict: if plain `ls` shows only names and `ls -l` shows more detail, what do you expect a command named `ls -la` to add? Think about what kinds of files a graphical file manager might hide by default. Then run it in your own home directory and compare the output to plain `ls`, paying attention to names that start with a dot.

```bash
ls -la
```

<details>
<summary>Check your prediction</summary>

The `-a` flag stands for "all", including hidden files and directories whose names begin with a dot (`.`). Hidden does not mean secret or malicious; it usually means a configuration file or directory that would clutter normal directory browsing. Shell startup files (`.bashrc`, `.zshrc`), editor settings, and tool caches often live this way. Beginners sometimes delete dotfiles because they look unfamiliar, but many of them control how your shell and developer tools behave.
</details>

The third command is `cd`, which stands for change directory. It changes your current working directory, so every relative path after that begins from the new place. Nothing has been created or deleted by `cd`; only your location has changed. The example below uses a macOS-style `Documents` directory. In the Ubuntu lab, use the existing lowercase `documents` directory instead: names are case-sensitive there. If neither name appears in `ls`, choose an existing directory from that listing and substitute its name in this navigation example.

```bash
cd Documents
```

After changing directories, immediately check where you are so you connect the `cd` action with the path change it produced:

```bash
pwd
```

The output should now include the Documents directory at the end of the path, showing that your current working directory changed:

```
/Users/yourname/Documents
```

Use `cd` to move, `pwd` to verify, and `ls` to inspect. A relative file argument such as `deployment.yaml` is resolved from the current directory; check the path before using it in a later command.

### Going back up: `cd ..`

The special path `..` means "the parent directory", or the room that contains the current room. If `Documents` is inside your home directory, then `cd ..` moves you from Documents back to home. This is not a command-specific trick; `..` is a standard path component used across Unix-style systems. You will see it in terminal work, scripts, and documentation.

```bash
cd ..
```

```bash
pwd
```

The output should now be back at your home directory because `..` moved one level up from Documents rather than jumping somewhere unrelated:

```
/Users/yourname
```

### Going home: `cd ~`

The `~` symbol is a shortcut for your home directory in many Unix-style shells. No matter how deep you are in a project, `cd ~` returns you to the personal base directory for your account. This is useful when you feel lost, but it is also useful when instructions intentionally start from a known safe place. Many beginner labs begin with `cd ~` because it removes ambiguity before creating practice folders.

```bash
cd ~
```

### Going to a specific place: `cd /path/to/place`

An absolute path lets you navigate from the root of the file system without starting from your current directory. In the Ubuntu lab, `/tmp` provides an existing absolute path to try. On another system, choose an existing directory instead if this path is unavailable. Do not store important work in this practice location; follow your system's storage policy.

```bash
cd /tmp
```

```bash
pwd
```

The output should show the temporary directory, proving that an absolute path can jump directly to a location:

```
/tmp
```

Now return home so the next practice commands start from a familiar and relatively safe location that you can verify again:

```bash
cd ~
```

Before running this, predict what `pwd` will show after `cd ~`, then compare your prediction with the output.

```bash
pwd
```

<details>
<summary>Check your prediction</summary>

Running `pwd` outputs your home directory path, such as `/Users/yourname` on macOS or `/home/yourname` on Linux. The `~` symbol is shorthand for your personal home directory, so `cd ~` returned you to the base of your user workspace regardless of which folder you visited previously.
</details>

## Create Folders and Files with `mkdir`, `touch`, `cp`, and `mv`

Navigation tells you where commands will act, but useful work begins when you create and rearrange files. These commands are intentionally small. `mkdir` creates directories, `touch` creates an empty file when the file does not exist, `cp` creates another copy, and `mv` changes a file's name or location. The power comes from combining those small actions with precise paths.

The safest way to learn creation commands is to run them in a new practice area. Names with dashes are convenient because they avoid the quoting problems that spaces introduce. Spaces are allowed in file names, but they require care because the shell uses spaces to separate words.

### Create your disposable workspace

Return home, then create a dedicated directory for all file-changing practice below:

```bash
cd ~
```

```bash
mkdir kubedojo-first-commands
```

**Continue only if `mkdir` succeeds.** If it reports that the name already exists, or any other error, stop here. Do not reuse or delete that existing path, and do not add `-p` to bypass the error. Choose a different unused workspace name and substitute it consistently below. [The `mkdir` manual](https://manpages.ubuntu.com/manpages/noble/man1/mkdir.1.html) explains why ordinary creation reports a collision while `-p` accepts existing directories.

Run this walkthrough only in the fresh workspace created in this session. Run commands one at a time, including those shown in the same block. Before each file-changing command, confirm the current directory, source and destination; if a destination already exists unexpectedly, a path is a symbolic link, or a command reports an error, stop and investigate. The diagnostic exercise below deliberately produces one specified error; continue there only if that is the error you observe. Do not overwrite an existing item or clean up a path you cannot identify as your own disposable practice data. These examples are not for personal or shared project files.

After successful creation, enter that new directory and verify the location:

```bash
cd ~/kubedojo-first-commands
pwd
```

Continue only if `cd` succeeds and `pwd` ends in your new workspace name. All following `menu.txt`, `restaurant` and copy/move/delete examples belong inside this workspace, including the hands-on exercise. An existing folder elsewhere with the same name is not part of this practice.

`mkdir` stands for make directory. A directory is a folder, and creating one does not move you into it automatically. This is a common beginner assumption: after `mkdir my-first-folder`, your current directory is still wherever it was before. Use `ls` to verify that the folder exists, and use `cd my-first-folder` only when you intentionally want to enter it.

```bash
mkdir my-first-folder
```

Check that the directory was created by listing the current directory and looking for the new name among the existing entries:

```bash
ls
```

You should see `my-first-folder` in the list. If you do not, check `pwd` and investigate. If `mkdir` reports that the name already exists, stop; do not reuse or remove the existing item. Choose a different unused name and substitute it consistently for this practice.

The `-p` flag makes `mkdir` create missing parent directories along a path. Without `-p`, `mkdir restaurant/kitchen/prep-area` fails if `restaurant` or `restaurant/kitchen` does not already exist. With `-p`, the command creates the whole chain as needed. The flag is popular in scripts because it makes setup commands repeatable: running the same command again does not fail simply because the directory already exists.

```bash
mkdir -p restaurant/kitchen/prep-area
```

This creates three folders nested inside each other, even though `restaurant` and `kitchen` did not exist yet. The word "parents" is a helpful memory aid: a child directory cannot exist unless its parent directories exist first. In project work, this pattern appears when you create paths such as `app/frontend/components` or `manifests/base/deployments` before adding files inside them.

`touch` creates an empty file if the named file does not exist. It also updates timestamps: if the file already exists, ordinary `touch` updates its access and modification times without replacing its contents. Here, use a new name so you have an empty file to copy, move, or delete without needing a text editor yet.

```bash
touch menu.txt
```

Check the current directory so you can see the empty file name appear beside the folders you already created:

```bash
ls
```

If `touch` succeeded on a new name, `menu.txt` appears in the listing as an empty file. If the name already existed, `touch` can update its timestamp; check your location and target before running it.

`cp` stands for copy, and it creates a duplicate while leaving the original in place. Before copying, check the destination: an existing file may be overwritten. A copy can provide a fallback, but only if you choose and verify a separate destination.

```bash
cp menu.txt menu-backup.txt
```

Now you have two files: the original and the copy, which is exactly the behavior you want when you need a fallback before experimenting.

```bash
ls
```

The output should include both file names, which proves that `cp` duplicated the original file rather than moving or renaming it:

```
menu-backup.txt    menu.txt    my-first-folder    restaurant
```

To copy a file into a folder, provide the source file and the destination directory. The trailing slash in `restaurant/` is not always required, but it communicates your intent clearly: the destination is a directory, not a new file name. If the directory does not exist, the command will fail rather than create the directory for you. That separation is useful because `mkdir` owns directory creation, while `cp` owns copying.

```bash
cp menu.txt restaurant/
```

To copy an entire folder and its contents, use `-r`, which means recursive. Recursive operations can affect many entries. Before this example, verify that `restaurant-copy` does not already exist; stop on a collision or unexpected contents.

```bash
cp -r restaurant restaurant-copy
```

`mv` stands for move, but it also renames. This seems odd until you realize that a file's name is part of its path. Moving `menu-backup.txt` into `restaurant/` changes its path from `./menu-backup.txt` to `./restaurant/menu-backup.txt`. Renaming `menu.txt` to `daily-specials.txt` changes only the final path component, but the underlying operation is still "change where this file is known."

When moving a file to another folder, read the source and destination before pressing Enter. Check that the destination directory contains no `menu-backup.txt`; an existing destination can be overwritten. Stop if it is present.

```bash
mv menu-backup.txt restaurant/
```

The file is no longer in the current directory because it has been moved into the `restaurant` folder. Unlike `cp`, the original does not stay behind. This is exactly what you want when reorganizing a project, but it is wrong when another tool still expects the original location to exist. When in doubt, copy first, inspect the result, and move only when you are sure there should be one file rather than two.

When renaming a file, the same source-then-destination pattern applies. First confirm that `daily-specials.txt` is absent; stop if that name already exists.

```bash
mv menu.txt daily-specials.txt
```

The file `menu.txt` is gone under that name, and `daily-specials.txt` appears in its place. It is the exact same file under a new name rather than a duplicate. Pause and predict: which approach would you choose when handling a new service configuration, copying a sample file first or moving it immediately, and why?

<details>
<summary>Check your prediction</summary>

Copying a sample leaves the original in place, provided you choose a separate destination and check it first. Moving changes the location instead. Choose based on whether the original should remain, and inspect the destination before either action.
</details>

## Delete and Clean Up Safely with `rm` and `clear`

Deletion is where terminal precision becomes most important. A graphical desktop usually gives you a trash or recycle bin, and it may ask for confirmation before permanent removal. The terminal's `rm` command is more direct. It removes file names immediately and usually has no built-in undo path for ordinary users. That does not mean you should fear it; it means you should build a confirmation routine before using it.

Consider how everyday graphical file deletion contrasts with an automated terminal command. Pause and predict: when you drag a file to the desktop Trash, where does that item go? What safety net does that graphical workflow provide compared to running a command designed for headless automation?

<details>
<summary>Check your prediction</summary>

A desktop's Trash or Recycle Bin may provide a holding place for deleted files, but behavior depends on the application and location. Ordinary `rm` removes the named file without sending it to the desktop Trash; do not rely on an Undo button or confirmation prompt. Check the target before running it.
</details>

`rm` stands for remove. It deletes a file at the path you provide, or in the current directory if you provide only a file name. Before you run it, use `pwd` to confirm where you are and `ls` to confirm the target name. If there is any doubt, stop. A few seconds of checking is cheaper than rebuilding work you removed from the wrong directory.

```bash
rm daily-specials.txt
```

After successful removal, that directory entry is gone. Ordinary `rm` provides no desktop Trash recovery workflow; check that you have a usable backup, copy or version-control record before removing something you may need again. A failed removal is different: read any error and verify the target rather than assuming it disappeared.

A practice file may be replaceable, while a report, certificate, or hand-edited configuration may not be. Choose a narrow target and verify it before a destructive operation.

One practical safety technique is to separate cleanup into two phases. First, inspect or move the target into a clearly named holding place, such as a temporary cleanup folder. Second, delete only after you are sure the contents are disposable. You will not always need that extra step, especially in small practice labs, but the pattern teaches a useful instinct: when the cost of being wrong is high, make the operation more reversible before you make it final.

To delete a folder and everything inside it, add `-r` for recursive behavior. This tells `rm` to walk the directory tree below the target and remove contained files and directories. The command is useful for cleaning up a practice folder, build output, or a temporary workspace. It is also one of the places where a typo can hurt, so inspect the target before pressing Enter.

```bash
rm -r restaurant-copy
```

The `-r` flag means "recursive", which is the same idea you saw with `cp -r`, but now the action is removal rather than copying. Be especially careful with commands copied from the internet that include `rm -rf`, where `-f` asks for forceful removal and suppresses many prompts. You do not need `-f` for this module. The safer beginner habit is to remove known practice directories by explicit name after listing their contents.

A dangerous example is shown below only so you recognize it. Do not run it. GNU `rm`, as used in the Ubuntu lab, normally refuses recursive removal of `/` because `--preserve-root` is the default. [Its manual](https://manpages.ubuntu.com/manpages/noble/man1/rm.1.html) documents this protection. It does not protect every other directory you might accidentally name, so it does not make careless deletion safe.

```text
rm -rf /
```

`clear` changes the terminal display rather than removing your files. Save any output you need before running it: the ncurses implementation can clear the scrollback buffer as well as the visible screen, depending on terminal capabilities. [Its manual](https://invisible-island.net/ncurses/man/clear.1.html) explains this behavior; scrolling back is not a reliable way to recover cleared output.

```bash
clear
```

After a successful `clear`, the screen is cleared and your practice files remain on disk. Screen output and shell command history are different things: history can recall commands, but it does not preserve all their output. In Bash's default Readline key bindings, `Ctrl + L` also clears the screen. Use display clearing for visual focus and file removal only for deliberate cleanup.

## Combine Commands with Pipes and Filters

Once single commands feel comfortable, pipes introduce the main reason terminal work scales so well. A pipe, written as `|`, sends the output of the command on the left into the command on the right. Instead of making one command do everything, Unix-style tools encourage small commands that do one job and pass text along. This is the assembly-line model: one station lists files, the next station trims the list, and another station searches for a pattern.

This section introduces output becoming input. You can use filters with listings, logs, or command history; the examples below show the connection before you work with more complex output.

The first pipeline shows the first five lines of a directory listing:

```bash
ls | head -n 5
```

`ls` lists entries, but `head -n 5` keeps only the first five lines. This is useful when a directory has hundreds of files and you want a quick sample without flooding the screen. The left command does not need to know that `head` exists, and `head` does not need to know how `ls` found the names. The pipe connects them by text.

The second pipeline searches for a word inside a file. Earlier you removed `daily-specials.txt`; first list the workspace and confirm that this name is absent. Stop if it exists or if the earlier removal failed: the redirection below can overwrite an existing file. Only then create the sample:

```bash
echo "Wednesday: pasta with marinara" > daily-specials.txt
```

```bash
cat daily-specials.txt | grep "pasta"
```

`cat` displays file contents, and `grep "pasta"` selects lines containing `pasta`. You can also use `grep` directly on a file; this example shows how one command's output becomes another's input.

The third pipeline finds a past command you typed, which is a practical way to recover a path or option from recent shell history:

```bash
history | grep "mkdir"
```

`history` shows shell history, and `grep "mkdir"` selects lines containing `mkdir`. This can help locate a command when you remember part of it; the entries available depend on the shell and its history settings.

Before running your own pipeline, pause and predict: must the left command finish before the right command starts, and what text moves between them? Then change the search word in `history | grep "mkdir"` to `cd` or `rm`. If a filter prints nothing, inspect the unfiltered input before drawing a conclusion; it may simply have found no matching lines.

<details>
<summary>Check your prediction</summary>

The commands can run concurrently: the left command does not have to finish before the right starts reading. The pipe connects the left command's standard output to the right command's standard input. Here, `history` supplies the entries available to that shell; `grep` selects matching lines as it reads them.
</details>

## Quick Reference Card

Use this table as a reference while you practice. The kitchen analogy connects each command to an everyday action; the examples above explain the actual behavior and its limits.

| Command | What It Does | Kitchen Analogy |
|---------|-------------|-----------------|
| `pwd` | Shows where you are | "What room am I in?" |
| `ls` | Lists what's here | "What's on this shelf?" |
| `cd` | Moves to another place | "Walk to another room" |
| `mkdir` | Creates a new folder | "Build a new room" |
| `touch` | Creates an empty file | "Put a blank paper on the counter" |
| `cp` | Copies a file | "Photocopy this recipe" |
| `mv` | Moves or renames | "Move this to another shelf" or "relabel it" |
| `rm` | Removes the named file entry | "Remove this paper" (no desktop Trash) |
| `clear` | Cleans the screen | "Wipe the whiteboard" |

## When This Doesn't Apply

A graphical file manager can help when you need thumbnails, previews, or drag-and-drop interaction. Terminal commands can be useful when you can name paths, document a sequence, or work through a remote shell. Choose according to the task and inspect the result in either interface.

For example, a command can describe a directory structure or filter a listing; a graphical dashboard can help display a system's state. You can use both within a workflow.

## When You'd Use This vs Alternatives

Use `pwd`, `ls`, and `cd` when your problem is orientation. They are the right tools when you need to confirm location, inspect a directory, or move to the correct workspace before acting. Use a graphical file manager instead when you need thumbnails, previews, or visual comparison. The tradeoff is speed versus visibility: terminal navigation is precise and scriptable, while a graphical browser shows context that may not fit neatly in text.

Use `mkdir`, `touch`, `cp`, and `mv` when your problem is controlled file organization. They are good when you can name the exact directory or file and want a repeatable action. Use an editor, integrated development environment, or file manager when you need to author content, compare documents visually, or drag files between applications. The tradeoff is that terminal commands are efficient after you know the target, but they are unforgiving when the target is vague.

Use `rm` only when your problem is deliberate cleanup and you have confirmed the target. If you are unsure whether a file matters, prefer moving it into a temporary holding directory, making a copy, or leaving it alone until you can inspect it. Use `clear` when your problem is visual clutter, not disk clutter. These two commands are often confused emotionally because both make things disappear from view, but only one removes files.

Use pipes when your problem is too much output rather than too little output. A graphical search box can be comfortable for a single document, but a command pipeline can search command history, file listings, and tool output without opening separate windows. The tradeoff is that pipes require you to think about text flow: left command produces, right command filters. Once that model clicks, the terminal becomes less like a set of isolated commands and more like a small inspection language.

## Did You Know?

- **An empty-looking directory may contain dotfiles.** Plain `ls` normally omits names starting with `.`, while `ls -a` includes them. Use the latter before assuming that a practice directory has no contents; [the `ls` standard](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/ls.html) defines the difference.
- **`touch` can change an existing file without changing its contents.** Its normal job is updating access and modification timestamps. Creating an empty file happens when the target does not exist, as explained in [the `touch` standard](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/touch.html).
- **`mkdir -p` can succeed without creating anything.** If the directory path already exists, it accepts that state; ordinary `mkdir` reports an existing-path error. [The manual](https://manpages.ubuntu.com/manpages/noble/man1/mkdir.1.html) describes behavior useful for repeatable setup, but unsuitable for proving that your practice workspace is new.
- **A pipe does not wait for a complete output file.** Commands can process a stream while an upstream command is still producing it. [Bash's pipeline documentation](https://manpages.ubuntu.com/manpages/noble/man1/bash.1.html#Pipelines) describes how standard output becomes standard input, allowing small tools to work together.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Using `rm` without checking first | The command is short, and beginners expect desktop-style Trash behavior | Run `pwd` and `ls` first, then remove only the exact target you meant to remove |
| Forgetting `-r` when copying or removing folders | Directories contain other entries, so the command needs permission to recurse | Use `cp -r folder newname` for directory copies and `rm -r folder` only after inspecting the folder |
| Creating names with unquoted spaces by accident | The shell treats spaces as separators between arguments | Use quotes such as `mkdir "my folder"` or prefer dashed names such as `mkdir my-folder` |
| Getting lost in the file system | `cd` changes context silently when it succeeds | Type `pwd` frequently, use `cd ~` to return home, and inspect with `ls` before acting |
| Confusing `cp` and `mv` during cleanup | Both commands take a source and a destination, but only one leaves the original behind | Use `cp` when you need a duplicate or fallback, and `mv` when there should be one final location |
| Assuming `mkdir` moves you into the new folder | Graphical tools often open a folder after creation, but `mkdir` only creates it | Run `cd folder-name` after `mkdir` if you want to enter the new directory |
| Treating empty output as always bad | Filters such as `grep` may return nothing when no lines match | Recheck the question you asked, try a broader pattern, or inspect the unfiltered command output |
| Typing commands wrong and getting frustrated | Everyone mistypes paths, flags, and file names, especially at speed | Use the up arrow to recall the previous command, edit carefully, and rerun only after reading it |

## Quiz

<details>
<summary>1. Your team runs `mkdir projects`, but the folder appears in a completely unexpected location. What should you have checked before creating it, and how do you diagnose the mistake afterward?</summary>

You should have run `pwd` before `mkdir` to confirm your current working directory. `mkdir projects` creates the folder relative to where the shell is standing, so a successful command can still create the folder in the wrong place. Afterward, run `pwd` to see where you are, then use `ls` in that location to confirm whether `projects` was created there. The fix is not to guess harder; it is to restore the navigation loop of `pwd`, `ls`, and `cd`.
</details>

<details>
<summary>2. You need a logo file to remain in `assets/` while another copy goes into `public/`, and later you need a config file relocated without leaving a duplicate. Which command fits each task, and why?</summary>

Use `cp` for the logo because the requirement explicitly needs two files: the original in `assets/` and a duplicate in `public/`. Use `mv` for the config file because the requirement says it should be relocated without leaving a duplicate behind. The important comparison is copy versus move behavior, not the spelling of the commands. If you choose `mv` for the logo, you break the original location; if you choose `cp` for the config, you may leave stale configuration behind.
</details>

<details>
<summary>3. You are cleaning old logs and accidentally type `rm production-db.sql` instead of `rm production.log`. What happens next, and what habit would have reduced the risk?</summary>

The terminal does not give you a normal desktop Undo button or Trash recovery path for `rm`. The file name is removed immediately, and ordinary users should assume recovery is unreliable unless a backup or version-control copy exists. The safer habit is to run `pwd` and `ls` first, read the target name slowly, and remove only the exact file you intended. For higher-risk cleanup, move files into a temporary holding directory first, then delete after verification.
</details>

<details>
<summary>4. You need to create `app/frontend/components/buttons/`, but none of the parent folders exist yet. You try plain `mkdir app/frontend/components/buttons/` and it fails. What command should you use, and why?</summary>

Use `mkdir -p app/frontend/components/buttons/`. Plain `mkdir` can create one directory only when its parent already exists, so it fails when `app`, `frontend`, or `components` is missing. The `-p` flag tells `mkdir` to create missing parent directories along the path. This is useful for repeatable setup because the same command can succeed even when part of the structure already exists.
</details>

<details>
<summary>5. You have been navigating through server logs and no longer know where you are, but you need to return to your main user folder before running a script. Which two commands restore your context?</summary>

First run `pwd` to print the current working directory and diagnose where the shell is standing. Then run `cd ~` to return to your home directory, which is a known base location for your user account. This pair works because it separates diagnosis from action: `pwd` tells you the current state, while `cd ~` changes it deliberately. After returning home, use `ls` if you need to confirm the script or project folder is present.
</details>

<details>
<summary>6. You run `history | grep "mkdir"` and nothing appears, even though the command itself did not show an error. How should you interpret that result?</summary>

Empty output from a pipeline often means the filter found no matching lines, not that the shell failed. In this case, `history` produced text, and `grep "mkdir"` kept only lines containing the word `mkdir`; if no such lines exist in the visible history, the final output is empty. To diagnose, run `history` by itself or search for a broader term such as `mk`. This question tests command output filtering, because pipes answer exactly the pattern you ask for.
</details>

<details>
<summary>7. You copied a practice directory with `cp -r restaurant restaurant-copy`, experimented in the copy, and now want to clean up only the duplicate. What should you inspect, and what removal command fits?</summary>

Run `ls` to confirm that both `restaurant` and `restaurant-copy` exist, and use `ls restaurant-copy` if you want to inspect the duplicate before deleting it. The correct cleanup command is `rm -r restaurant-copy`, because you are removing a directory tree rather than a single file. Do not remove `restaurant` unless that original folder is also disposable. The reasoning is the same as all safe deletion: confirm location, confirm target, then run the narrowest command that matches your intent.
</details>

## Hands-On Exercise: Build a Restaurant File Structure

Exercise scenario: you are preparing a small file layout for an imaginary restaurant. Use only the fresh workspace created above. Before each mutation, check the relevant source and destination; stop on an error, an unexpected existing name or a symbolic link. Inspect paths with `pwd` and `ls` rather than changing or deleting unfamiliar data.

### Step 1: Return to your disposable workspace

Use the new workspace you successfully created above. If you skipped the walkthrough, complete its workspace setup first; an existing directory alone does not prove that its contents are disposable.

```bash
cd ~/kubedojo-first-commands
pwd
```

<details>
<summary>Solution notes</summary>

Starting inside your own new workspace keeps practice separate from existing home-directory files. Stop unless the workspace's plain `mkdir` succeeded in this session. Also stop if `cd` fails or `pwd` shows another location. Those location checks alone do not establish ownership of an existing directory.
</details>

### Step 2: Create the restaurant structure

```bash
mkdir -p restaurant/kitchen/prep-area
mkdir -p restaurant/kitchen/cooking-stations
mkdir -p restaurant/dining-room
mkdir -p restaurant/storage/pantry
mkdir -p restaurant/storage/freezer
```

<details>
<summary>Solution notes</summary>

Each command uses `mkdir -p` because some parent directories do not exist before the command runs. Running these lines more than once should not hurt the practice layout, which is one reason `-p` is useful in setup instructions.
</details>

### Step 3: Create some files

```bash
touch restaurant/kitchen/prep-area/chopping-board.txt
touch restaurant/kitchen/cooking-stations/grill.txt
touch restaurant/kitchen/cooking-stations/oven.txt
touch restaurant/dining-room/table-1.txt
touch restaurant/dining-room/table-2.txt
touch restaurant/storage/pantry/flour.txt
touch restaurant/storage/pantry/sugar.txt
touch restaurant/storage/freezer/ice-cream.txt
```

<details>
<summary>Solution notes</summary>

These files are empty placeholders, but their paths prove that the directory structure exists. If one command fails, inspect the spelling of the parent directories with `ls restaurant` and `ls restaurant/kitchen` before rerunning the failed line.
</details>

### Step 4: Look at what you built

Run directory listings across the newly created folders to inspect your restaurant file layout at progressively increasing depth:

```bash
ls restaurant/
ls restaurant/kitchen/
ls restaurant/kitchen/cooking-stations/
```

Before inspecting that third command, pause and predict what files should appear inside `restaurant/kitchen/cooking-stations/`. The expected output confirms that both files were placed correctly in the nested directory:

```
grill.txt    oven.txt
```

<details>
<summary>Solution notes</summary>

The three `ls` commands inspect the layout at increasing depth. If the final output does not include both files, read the earlier `touch` commands and check whether a path was misspelled.
</details>

### Step 5: Move some things around

In this exercise scenario, move the ice cream file from the freezer path to the prep-area path. First confirm the source exists and that the destination has no `ice-cream.txt`; stop if it does.

```bash
mv restaurant/storage/freezer/ice-cream.txt restaurant/kitchen/prep-area/
```

Before verifying the move, pause and predict what entries should now appear when you list `restaurant/kitchen/prep-area/`. Then run the listing to confirm that the destination directory contains both items:

```bash
ls restaurant/kitchen/prep-area/
```

The expected output should include both the original prep-area file and the moved file, confirming that the destination now contains both items:

```
chopping-board.txt    ice-cream.txt
```

<details>
<summary>Solution notes</summary>

The `mv` command changes the file's location, so `ice-cream.txt` should no longer be in `restaurant/storage/freezer/`. If you want to prove that, run `ls restaurant/storage/freezer/` and expect no output for that file.
</details>

### Step 6: Make a backup of the menu

First check that neither `restaurant/practice-menu.txt` nor `restaurant/practice-menu-backup.txt` exists. Stop if either name is present; do not overwrite or update an unexpected file. These names are distinct from the menu used in the walkthrough.

```bash
touch restaurant/practice-menu.txt
cp restaurant/practice-menu.txt restaurant/practice-menu-backup.txt
ls restaurant/
```

<details>
<summary>Solution notes</summary>

This step uses `cp` because a backup should leave the original in place. The final `ls` should show both `practice-menu.txt` and `practice-menu-backup.txt` in the restaurant directory.
</details>

### Step 7: Diagnostic challenge: locate and relocate a misplaced file

Hypothetical scenario: a teammate needs to add `olive-oil.txt` to `restaurant/storage/pantry/`. Confirm that this name is absent from both `restaurant/kitchen/` and `restaurant/storage/pantry/` before recreating the scenario. Stop on a collision. From `restaurant/kitchen/`, they try the following invalid relative path:

```bash
cd ~/kubedojo-first-commands/restaurant/kitchen
touch storage/pantry/olive-oil.txt
```

Expect an error saying the path does not exist, such as `No such file or directory`; the full wording varies by utility and locale. The relative path looks for `storage` inside `kitchen`. If the command succeeds or reports a different problem, stop and inspect the workspace. After the expected missing-path error, confirm that `olive-oil.txt` is absent in the current directory before creating it:

```bash
touch olive-oil.txt
```

Your troubleshooting challenge is to diagnose and repair this misplaced file using only the commands taught in this module: `pwd`, `ls`, `cd`, and `mv`. You must not delete and recreate the file; locate the existing item and relocate it to its intended destination in the pantry.

Work through this unguided diagnostic sequence in your terminal before inspecting the solution details below. First, run `pwd` and `ls` to discover where the shell is currently standing and identify where `olive-oil.txt` landed. Second, inspect the directory hierarchy to explain why `storage/pantry/` could not be reached from `kitchen`. Third, use `cd` and `mv` to relocate `olive-oil.txt` into its intended destination at `restaurant/storage/pantry/`. Finally, run `ls` on both folders to confirm the file reached the pantry and no longer clutters the kitchen.

<details>
<summary>Solution & Diagnostic Walkthrough</summary>

Start by diagnosing where your shell is standing and listing what items exist in your current working directory:

```bash
pwd
ls
```

`pwd` reports `/home/yourname/kubedojo-first-commands/restaurant/kitchen` (or your platform equivalent), and `ls` displays `cooking-stations`, `olive-oil.txt`, and `prep-area`. This reveals that `touch olive-oil.txt` created the file inside the kitchen, because relative paths always execute against the active directory printed by `pwd`.

Next, examine why the teammate's relative command failed. Inside the workspace's `restaurant/kitchen/`, the relative path `storage/pantry/` fails because `kitchen` and `storage` are sibling folders inside `restaurant`. The shell searched below `kitchen` instead of beside it.

To fix the structure, navigate up to the restaurant root directory and inspect the pantry:

```bash
cd ..
pwd
ls storage/pantry/
```

Now relocate the misplaced file from the kitchen into the pantry using accurate relative paths from the restaurant root:

```bash
mv kitchen/olive-oil.txt storage/pantry/
```

Alternatively, you could have executed the move directly from inside the kitchen directory by using the parent directory reference: `mv olive-oil.txt ../storage/pantry/`. Both commands achieve the exact same relocation.

Finally, verify that `olive-oil.txt` arrived in the pantry and was removed from the kitchen:

```bash
ls storage/pantry/
ls kitchen/
```

The output for `storage/pantry/` now displays `flour.txt`, `olive-oil.txt`, and `sugar.txt`. The output for `kitchen/` displays only `cooking-stations` and `prep-area`. You successfully diagnosed a location-dependent error and corrected the file placement without destroying data.
</details>

### Step 8: Clean up

When you are done, return to your workspace and inspect its practice tree before removing it. Stop if the directory change fails, the location is wrong, a path is a symbolic link, or the tree contains anything you cannot identify as disposable practice data. Remove only the `restaurant` inside the fresh workspace:

```bash
cd ~/kubedojo-first-commands
pwd
ls -laR restaurant
```

```bash
rm -r restaurant
```

Verify that the practice directory is gone by filtering the current directory listing for the restaurant name and interpreting empty output carefully:

```bash
ls | grep restaurant
```

If the listing succeeds without errors and the filter prints nothing, it found no remaining visible name containing `restaurant`. If you see an error, investigate it rather than treating missing output as proof of successful cleanup.

<details>
<summary>Solution notes</summary>

The earlier exclusive workspace creation is what separates this practice tree from a pre-existing `~/restaurant`. Inspecting a directory helps you recognize its contents; it does not establish that you created it or may delete it.
</details>

Use this success criteria checklist to confirm that you practiced every aligned skill rather than only copying commands:

- [ ] You created an unused practice workspace and verified its location before changing files.
- [ ] You created the nested `restaurant` directory structure with `mkdir -p`.
- [ ] You created empty practice files with `touch` in the correct subdirectories.
- [ ] You inspected the structure with `ls` at multiple levels.
- [ ] You moved `ice-cream.txt` with `mv` and verified the new location.
- [ ] You copied `practice-menu.txt` with `cp` so the original and backup both existed.
- [ ] You used `pwd` and `ls` to diagnose a command that ran in the wrong directory, then navigated with `cd` and moved the file with `mv` to restore the correct structure.
- [ ] You removed only the disposable `restaurant` practice directory with `rm -r`.
- [ ] You used a pipe with `grep` to verify that cleanup produced no remaining restaurant entry.

The walkthrough's other files still live inside `kubedojo-first-commands`. Keep them for more practice, or inspect the workspace from home and remove it only if it is the new directory you created for this session and contains nothing you want to keep:

```bash
cd ~
ls -laR kubedojo-first-commands
```

```bash
rm -r kubedojo-first-commands
```

## Sources

- [Ubuntu Bash manual](https://manpages.ubuntu.com/manpages/noble/man1/bash.1.html) — Shell paths, expansion, prompts, pipelines, history and Readline bindings.
- [ncurses `clear`](https://invisible-island.net/ncurses/man/clear.1.html) — Screen clearing and terminal-dependent scrollback behavior.
- [KubeDojo lab verifier](https://github.com/kube-dojo/kubedojo-labs/blob/fe6f47c3888ec1b7bc079781242d44e7f99e25ce/prereq-0.3-first-commands/step1/verify.sh) — Account home selection for the linked lab's task checks.
- [POSIX `pwd`](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/pwd.html) — Standard behavior for printing the working directory.
- [POSIX `ls`](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/ls.html) — Standard listing utility behavior and options.
- [POSIX `mkdir`](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/mkdir.html) — Standard directory creation utility behavior.
- [Ubuntu `mkdir`](https://manpages.ubuntu.com/manpages/noble/man1/mkdir.1.html) — Existing-path errors and the different behavior of `-p`.
- [Ubuntu `rm`](https://manpages.ubuntu.com/manpages/noble/man1/rm.1.html) — GNU recursive-removal options and the root guard.
- [POSIX `touch`](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/touch.html) — Standard timestamp update and file creation utility behavior.
- [POSIX `cp`](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/cp.html) — Standard copy utility behavior, including recursive copying.
- [POSIX `mv`](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/mv.html) — Standard move and rename utility behavior.
- [POSIX `rm`](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/rm.html) — Standard removal utility behavior and recursive deletion options.

## Next Module

In [Module 0.4: Files and Directories](../module-0.4-files-and-directories/), you will go deeper into how computers organize files and folders, then practice navigating paths with more confidence and less guessing.
