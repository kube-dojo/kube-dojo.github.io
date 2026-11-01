---
title: "Module 0.5: Editing Files"
slug: prerequisites/zero-to-terminal/module-0.5-editing-files
revision_pending: false
sidebar:
  order: 6
---
> **Complexity**: `[MEDIUM]` - Long-form practice: type what you see, save, verify, and run a tiny script
>
> **Time to Complete**: Estimate 80–100 minutes for reading and practice; individual times vary.
>
> **Prerequisites**: [Module 0.4 - Files and Directories](../module-0.4-files-and-directories/), which builds on [Module 0.3 - First Terminal Commands](../module-0.3-first-commands/)

---

## What You'll Be Able to Do

By the end of this module you will have practiced the full editing loop that appears in everyday terminal work: open a file, change it deliberately, save it, verify it, and use it as input to another command. These outcomes are written as practical skills because editing files is not a trivia topic; it is a coordination skill between your keyboard, the shell, the filesystem, and the programs that later read what you wrote.

- **Create and edit** plain text files using `nano` from the terminal without depending on a graphical editor.
- **Implement and verify** a simple Bash script that combines multiple commands into one repeatable file.
- **Diagnose and fix** execute-permission problems with `chmod +x` when a script cannot run directly.
- **Compare and choose** between `nano`, `vim`, `cat`, and other file-viewing approaches for a specific editing situation.

## Why This Module Matters

Hypothetical scenario: you are connected to a training Linux host over a terminal, and a practice service refuses to start because its configuration file has one misspelled setting. There is no desktop editor on that host, and copying the file back to your laptop would add several chances to edit the wrong copy. The practical question is not whether you are a "terminal person"; the question is whether you can open the right file, make the smallest safe change, save it, and prove that the file now contains what you intended.

In the previous terminal modules, you created empty files with `touch` and inspected directories with commands such as `ls` and `pwd`. Empty files are like blank order tickets in a restaurant kitchen: they reserve a place, but they do not tell anyone what to cook. Real systems use text files for shell scripts, package lists, service configuration, environment files, documentation notes, and eventually Kubernetes manifests. Once text becomes the instruction layer for a system, editing it safely becomes an operations skill rather than a typing exercise.

This lesson starts with `nano`: you can type into a buffer and use the displayed commands to save and exit. You will also compare it with `vim` and file viewers.

## Why Terminal Editing Exists

Graphical editors are excellent when you are working on your own laptop, especially for large projects with many files, search panels, and language-aware helpers. Servers and cloud environments are different. They often run without a graphical interface, and remote access normally gives you a shell prompt rather than a desktop. When the only available interface is text, a terminal editor is the small reliable tool that lets you repair a configuration file, create a script, or inspect a note without installing an entire desktop stack.

The key mental model is that a file is just bytes stored under a name, while an editor is a temporary workspace for changing those bytes. When you run `nano hello.txt`, the shell starts the `nano` program and tells it which file you want to edit. `nano` loads the file contents into a buffer, lets you change that buffer on screen, and writes the buffer back to disk only when you save. Until you save, the file on disk and the text on screen are not the same thing.

That distinction matters because terminal work is often remote, shared, or automated. If you edit the wrong copy of a file, the program reading the real copy will not care how carefully you typed. If you close the editor without saving, the shell returns politely and nothing useful changed. If you save a broken configuration file and then restart a service, the service reads exactly what you wrote. The editor does not judge intent; it writes bytes, so your workflow must include verification.

The same file can also be seen by more than one program at different moments, which is why saving is an explicit boundary. While `nano` has the buffer open, another command such as `cat` reads the last saved version from disk, not the words currently visible in your editor. After you save, the next reader sees the new version. This boundary sounds obvious in a calm training module, but it explains many real beginner confusions: the terminal is not ignoring your work, it is reading the durable copy you have or have not written yet.

Terminal editing also teaches you to be precise about names. A filename is not a vague document title; it is a path that points to one object in one directory on one machine. `hello.txt` in your home directory, `hello.txt` in `/tmp`, and `hello.txt` on a remote training host are different files even if they contain the same words. Before editing, the useful question is "which path am I about to change?" After editing, the useful question is "does that exact path contain the text I meant to save?"

Here is the basic editing loop you will practice throughout this module. The loop is intentionally small because a small loop is easier to trust under pressure, and it scales from a three-line training note to a production configuration review. The same structure also appears later when you edit Kubernetes YAML: open, change, save, validate, and only then apply the result to the system.

```text
+--------------------+      +--------------------+      +--------------------+
|  Open the file      | ---> |  Edit the buffer    | ---> |  Save to disk      |
|  nano hello.txt     |      |  type, move, cut    |      |  Ctrl+O, Enter     |
+--------------------+      +--------------------+      +--------------------+
           ^                                                       |
           |                                                       v
+--------------------+      +--------------------+      +--------------------+
|  Adjust if needed   | <--- |  Verify the file    | <--- |  Exit the editor   |
|  reopen with nano   |      |  cat hello.txt      |      |  Ctrl+X            |
+--------------------+      +--------------------+      +--------------------+
```

Pause and predict: if you type three lines in `nano` but close the terminal window before saving, which copy of the file does a later `cat hello.txt` command read: the unsaved editor buffer or the file already stored on disk? Commit to an answer before revealing the explanation.

<details>
<summary>Check your prediction</summary>

The correct answer is the file on disk, because the shell and `cat` know nothing about the editor's unsaved memory. Thinking this through before the first exercise prevents a common surprise when a terminal editor behaves more literally than a modern graphical editor with autosave.

</details>

## Meet nano Before You Need It

Both `nano` and `vim` run in a terminal. In `nano`, you can open a file and type into its buffer. `vim` uses modes: a key may insert text in one mode and issue a command in another. This lesson uses `nano` for the editing loop.

| nano | vim |
|------|-----|
| Typing enters text into the buffer | Insert mode accepts text ([Vim introduction](https://raw.githubusercontent.com/vim/vim/master/runtime/doc/intro.txt)) |
| Menu shows common shortcuts | Modes distinguish editing from commands |

Choose a tool that fits the task and the environment. This module introduces `nano`; it does not require you to learn Vim's commands.

You will see the same idea when choosing between `nano` and `cat`. `nano` is for changing a file, while `cat` is for printing a file to the terminal. Opening an editor just to look at a file creates unnecessary risk because a stray keystroke can modify the buffer. Printing a file with `cat` when you meant to edit it is harmless but ineffective. The workflow is easier when each command has a clear job in your mind.

Before running this, what output do you expect from `cat hello.txt` if `hello.txt` does not exist yet? Commit to an answer before revealing the explanation.

<details>
<summary>Check your prediction</summary>

Most systems will show "No such file or directory," and that is useful feedback rather than a failure of the lesson. Editors such as `nano` can create a new file when you save, while viewers such as `cat` normally expect the file to already exist. That difference explains why the same filename can be acceptable to one command and an error to another.

</details>

## Opening, Editing, Saving, and Exiting

You can use the [plain Ubuntu playground](https://killercoda.com/playgrounds/scenario/ubuntu) for this self-checked practice. If it opens as root, `su - ubuntu` switches to its existing unprivileged account. Create a fresh disposable workspace before opening any practice filename. Existing files under your home directory are not automatically safe to edit or remove. Keep this workspace under your exclusive control and use it for every example, script, hands-on task, and cleanup command in this lesson.

Run these commands **one line at a time**. If `mkdir` or `cd` reports any error, stop before the next command. If the workspace name already exists as a file, directory, or symbolic link, leave it untouched and choose an unused name such as `kubedojo-editing-2`; substitute that name in later paths. Use plain `mkdir` for this root, not `mkdir -p`, which would accept an existing directory.

```bash
cd ~
mkdir kubedojo-editing
cd kubedojo-editing
pwd
ls -a
```

Continue only when `pwd` identifies the directory you just created and `ls -a` shows only `.` and `..`. If ownership or contents become uncertain, stop and begin in another fresh workspace. On a repeat run, create a new workspace rather than reopening or removing files from an earlier run.

This lesson assumes **GNU nano**. Check the editor's title banner when it opens: a command named `nano` can launch a different editor, such as Pico, on some machines. If the banner does not identify GNU nano, stop and use a training environment with GNU nano or ask your instructor which command launches it. Do not assume the displayed shortcuts match merely because the command name matches.

Now open `nano` with a filename that does not exist yet. This command does not immediately create permanent content on disk; it opens an editor buffer associated with the name `hello.txt`. The file becomes real in the useful sense when you write the buffer out with the save command.

```bash
nano hello.txt
```

Your screen will change completely because the terminal is now controlled by `nano` instead of your shell prompt. This simplified GNU nano screen is illustrative; versions, terminal width, and configuration can change the menu. Confirm the GNU nano banner, the filename at the top, the editing area, and the shortcuts at the bottom before typing.

```text
  GNU nano 7.2                    hello.txt







^G Help  ^O Write Out  ^W Where Is  ^K Cut    ^T Execute  ^C Location
^X Exit  ^R Read File  ^\ Replace   ^U Paste  ^J Justify  ^/ Go To Line
```

The bottom menu is the reason `nano` is a friendly first editor. It does not expect you to memorize everything before you can leave. The word "Write Out" means save the buffer to a file, and "Exit" means leave the editor and return to the shell. The old-fashioned wording is common in Unix tools, so it is better to learn the phrase once than to be surprised by it later.

The tested Ubuntu playground displayed Ctrl+W for search. Read your actual menu when a key behaves differently; versions and configuration can change the displayed bindings.

The `^` symbol in that menu means "hold the Ctrl key," not "type a caret character." When `nano` shows `^O`, press Ctrl and O at the same time. When it shows `^X`, press Ctrl and X at the same time. This notation appears in many terminal programs, logs, and manuals, so learning it here pays off outside `nano` as well.

| What You See | What You Press | What It Does |
|-------------|---------------|-------------|
| `^O` | Ctrl + O | Save the file |
| `^X` | Ctrl + X | Exit nano |
| `^K` | Ctrl + K | Cut the current line |
| `^U` | Ctrl + U | Paste a cut line |
| `^W` | Ctrl + W | Search for text |
| `^G` | Ctrl + G | Show help |

With `nano` open, type the following three lines. Do not worry if the screen wraps differently on your terminal; the file content is determined by the characters and line breaks you type, not by the exact visual width of the terminal window. Press Enter at the end of each line so the text becomes three separate lines in the file.

```text
Welcome to the Kitchen!
Today's special: Learning to edit files.
Chef says: You're doing great.
```

Your screen should now show the text and a modified-buffer indicator near the top. The tested GNU nano 7.2 screen shows `*`; its appearance may differ in another version. It warns that the buffer has changes not yet saved.

```text
  GNU nano 7.2                    hello.txt *

Welcome to the Kitchen!
Today's special: Learning to edit files.
Chef says: You're doing great.


^G Help  ^O Write Out  ^W Where Is  ^K Cut    ^T Execute  ^C Location
^X Exit  ^R Read File  ^\ Replace   ^U Paste  ^J Justify  ^/ Go To Line
```

To save, press Ctrl+O. `nano` will ask you to confirm the destination filename. In this exercise the suggested filename is already correct, so press Enter. The important habit is to read that filename before confirming, especially when you later edit files from different directories or remote machines.

```text
Ctrl + O
```

```text
File Name to Write: hello.txt
```

After you press Enter, the modified indicator disappears. You are still inside `nano`, so saving and exiting are separate steps. Verify the saved file after exiting.

To leave `nano`, press Ctrl+X. If the buffer has no unsaved changes, `nano` exits immediately. If you changed something after the last save, it asks whether to save the modified buffer, and you must choose deliberately. On the tested browser terminal, F2 also returned to the shell after saving.

```text
Ctrl + X
```

```text
Save modified buffer?  Y Yes  N No  ^C Cancel
```

Read the prompt before answering: `Y` continues the save path, `N` discards unsaved changes, and Ctrl+C cancels the exit attempt so you can return to editing. Confirm the destination if Nano asks for a filename.

## Verify and Reopen Files Deliberately

Returning to the shell prompt is not the end of an edit. Verification is the habit that turns "I think I saved it" into "the file contains what I intended." The simplest verification command is `cat`, which prints a file's contents to the terminal. The name comes from "concatenate" because the command can join files, but in daily work it is also a fast way to read a short text file.

```bash
cat hello.txt
```

Expected output:

```text
Welcome to the Kitchen!
Today's special: Learning to edit files.
Chef says: You're doing great.
```

The verification step also trains you to distinguish "editing" from "viewing." If the file is short and you only need to confirm its contents, `cat` is safer and faster than opening an editor. If the file is long, later modules will introduce viewers such as `less`, which let you scroll without editing. When the task is to change text, use an editor; when the task is to inspect text, prefer a viewer.

To edit an existing file, open it with the same command. `nano` reads the saved content into a new buffer, and you can move around with the arrow keys. Add a new line at the bottom, save, exit, and verify again with `cat`. This repeat-open-save-verify rhythm is more important than the specific kitchen text in the example.

```bash
nano hello.txt
```

Add this line at the bottom of the file:

```text
PS: The pantry is fully stocked.
```

Save with Ctrl+O, press Enter to confirm the filename, and exit with Ctrl+X. Then verify the file again. The result should now include the original three lines and the new fourth line, which proves that you edited the existing file rather than creating a separate note somewhere else.

```bash
cat hello.txt
```

When you work on remote systems, this habit protects you from a subtle class of mistakes: editing the wrong host, the wrong directory, or a temporary copy. A quick `pwd` before editing tells you where you are, and a quick `cat` after editing tells you what landed on disk. If you are connected to a remote host, `hostname` can also confirm which machine you are changing before you touch a sensitive file.

Exercise scenario: imagine you intended to edit a practice file in your owned `~/kubedojo-editing` workspace, but your prompt shows that you are in `/tmp`. Pause and predict: what is the focused fix, and why is typing faster not part of it? Commit to an answer before revealing the explanation.

<details>
<summary>Check your prediction</summary>

The edit might still succeed, yet the file would be in the wrong place for the next command. In that situation, the fix is not to type faster; the fix is to stop, run `pwd`, move to the intended directory, and repeat the edit in the correct location. Rushing only produces the same mistake in less time.

</details>

Verification also helps you catch spelling, punctuation and line-order mistakes before another program reads the file.

## Move Around, Search, Cut, and Paste

Small files can be edited by simply typing at the end, but real configuration files and scripts eventually require movement. In `nano`, the arrow keys move the cursor, Backspace and Delete remove characters, and Enter creates a new line. These controls are intentionally ordinary, which lets you concentrate on file meaning rather than editor mechanics during the first few modules.

`nano` also has simple line-oriented cut and paste commands. Move the cursor to a line you want to move, press Ctrl+K to cut that entire line, move to the destination, and press Ctrl+U to paste it. If you press Ctrl+K multiple times in a row, `nano` stacks the cut lines and pastes them together when you press Ctrl+U. This is useful when reorganizing a small script or moving related configuration lines together.

Press Ctrl+W, type the text you want to find, and press Enter. In your `hello.txt` file, searching for `special` should move the cursor to the matching word. The GNU nano 7.2 shortcut reference lists Alt+W to find the next occurrence.

```text
Ctrl + W
```

`nano` will prompt for the search text:

```text
Search:
```

Type `special` and press Enter. The cursor should jump to the matching word in the file. If there is no match, `nano` reports that the text was not found, which is still useful information because it tells you the file does not contain the exact spelling you searched for.

Pause and predict: which approach would you choose here and why — manually scanning a two-line note, or using Ctrl+W to find a setting in a file with several hundred lines? Commit to an answer before revealing the explanation.

<details>
<summary>Check your prediction</summary>

Manual scanning is fine when the file fits on one screen, but search becomes the safer choice once your eyes can miss a repeated word, a similar setting name, or a comment that looks like an active configuration line. The skill is choosing the approach by file size and risk, not by habit.

</details>

The tradeoff with cut and paste is that it is easy to move the wrong line if you do not verify the final arrangement. After rearranging lines, read the surrounding text before saving, then save and verify with `cat` or another viewer. In later modules, this same caution applies to YAML indentation, where moving a line to the wrong level can change the meaning of an entire Kubernetes manifest.

## Write Your First Script

A script is a text file that contains commands for the computer to run in sequence. You can think of it as a recipe card for the terminal: instead of typing the same commands one at a time, you write them once, save the file, and run the recipe whenever you need it. The first script in this module is intentionally friendly, but it introduces the same mechanics used by serious automation.

Open a new script file with `nano`. The `.sh` suffix is a convention that tells humans this is a shell script; it is not the part that makes the file executable. The operating system relies on permissions and, for direct execution, usually a shebang line at the top of the file.

```bash
nano my-first-script.sh
```

The first line of the script will be `#!/bin/bash`. That line is called a shebang, and it tells the system which interpreter should read the file when you execute it directly with `./my-first-script.sh`. If you instead run `bash my-first-script.sh`, you have already chosen Bash explicitly, so the shebang is less important for that invocation. Including it is still a good habit because it makes the script's intended interpreter visible to both humans and the operating system.

Type the following exactly **inside nano**, not at the shell prompt:

```bash
#!/bin/bash

echo "Welcome to the kitchen!"
echo "Today's date is: $(date)"
echo "You are logged in as: $(whoami)"
echo "Your current directory is: $(pwd)"
echo ""
echo "Great job, chef! Your first script works!"
```

Each line teaches a small piece of shell behavior. `echo` prints text, which makes it useful for status messages and simple reports. `$(date)` runs the `date` command and inserts its output into the line. `$(whoami)` inserts your current username, while `$(pwd)` inserts your current directory. The empty `echo ""` line prints a blank line so the output is easier to read.

The script also shows why editing text files is more powerful than typing individual commands at a prompt. A command typed at the prompt runs once and then disappears into shell history. A command saved in a script becomes a repeatable artifact that you can inspect, modify, share, review, and run again. That repeatability is one of the bridges from casual terminal use to automation.

A script file is also easier to reason about than a remembered sequence of commands because it gives you a fixed object to inspect. You can read the first line and ask which interpreter will run it. You can read each `echo` line and predict the output before execution. You can notice that `./my-first-script.sh` depends on the file being in your current directory and on execute permission before the shell will run it directly. This habit of reading a script before running it becomes essential when scripts later install packages, change permissions, or call cluster tooling.

Save with Ctrl+O, press Enter to confirm the filename, and exit with Ctrl+X. At this point the file exists and contains valid shell commands, but it is not necessarily a program the operating system is allowed to execute directly. New files are often created as readable and writable data, not as runnable programs, and that default is a security feature.

Before running `chmod`, run the script directly and predict the result. This is a useful experiment because it separates "the file contains commands" from "the file has execute permission." Commit to an answer before revealing the explanation.

```bash
./my-first-script.sh
```

<details>
<summary>Check your prediction</summary>

For a fresh script saved by GNU nano, expect no execute bit. If direct execution reports "Permission denied," inspect `ls -l my-first-script.sh` and confirm the owner's permission group lacks `x` before applying the focused fix below. The error alone does not prove a missing execute bit; other access restrictions can also block execution.

</details>

Inspect the mode of your owned practice script. If the owner execute bit is missing, add execute permission with `chmod +x`. `chmod` stands for change mode, and `+x` adds execute permission; it does not diagnose every possible access failure.

```bash
ls -l my-first-script.sh
chmod +x my-first-script.sh
```

Run the script again from the current directory. The `./` prefix matters because it says "run the file named `my-first-script.sh` from this directory." Without that prefix, the shell searches directories listed in your `PATH`, and your current working directory is usually not searched automatically.

```bash
./my-first-script.sh
```

Expected output:

```text
Welcome to the kitchen!
Today's date is: Mon Mar 23 14:30:00 UTC 2026
You are logged in as: yourname
Your current directory is: /home/yourname/kubedojo-editing

Great job, chef! Your first script works!
```

The exact date, username, and workspace path will vary. If execute permission is present but "Permission denied" persists, stop and ask your instructor or administrator to check path access or a filesystem mounted with execution disabled (`noexec`); repeating `chmod` does not fix those causes. The [Linux execve error list](https://man7.org/linux/man-pages/man2/execve.2.html) distinguishes these access failures. If Bash reports a syntax error, reopen the file with `nano` and inspect the reported line. That is a different layer from permission to start the script.

This small debugging sequence is the beginning of a useful diagnostic habit. First ask whether the file can be executed at all. Then ask whether the selected interpreter can parse it. Then ask whether the commands inside do what you intended. Those are different layers, and separating them prevents the frustrating habit of changing random lines without knowing which layer failed.

You can run many shell scripts in two different ways, and knowing the difference prevents confusion. `bash my-first-script.sh` asks Bash to read the file, so execute permission is not required for that specific command. `./my-first-script.sh` asks the operating system to execute the file directly, so execute permission and the interpreter selection path matter. In this course we practice the direct form because it exposes the real filesystem permission model that you will meet again when running helper scripts from repositories.

## Use Editing Judgment, Not Editor Folklore

You will encounter `vim` eventually, and it is worth learning when you are ready. It is powerful because it treats editing as a language of motions and operations, which lets practiced users change text quickly without reaching for a mouse. The tradeoff is that `vim` starts in normal mode, so a beginner who expects typed letters to appear may accidentally issue commands instead. That is why `nano` is a better first terminal editor for this module's goal.

The practical question is always "what is the safest tool for the current job?" Use `cat` when the file is short and you only need to view it. Use `nano` when you need a simple edit and want visible prompts for saving and exiting. Use `vim` when you already know its modes or when you need powerful navigation and editing on a terminal-only system. Use a graphical editor on your laptop when you are doing larger project work and the file is local.

There is one more judgment call: avoid editing binary files with a text editor. Images, compiled programs, archives, and many database files are not plain text. Opening one in `nano` may show strange characters, and saving it can corrupt the file. When you are unsure, run `file filename` before editing. Plain text, shell scripts, Markdown, YAML, JSON, and many configuration files are appropriate targets for a terminal text editor.

Configuration files deserve extra caution because programs read them literally. A stray quote, missing colon, or wrong indentation level can change behavior. Later Kubernetes modules will ask you to edit YAML manifests, where YAML structure determines how the configuration is read. The habits from this module transfer directly: open the right file, make a focused edit, save, validate, and then let the system read it.

This is why "quick edit" should not mean "careless edit." A quick edit is small, focused, and verified; a careless edit is rushed, unverified, and often performed in the wrong place. The terminal rewards precision because it gives you compact tools with very little ceremony. It also exposes mistakes quickly because those tools do exactly what you ask. Your goal is to become calm with that literalness rather than intimidated by it.

Exercise scenario: you are about to change a remote service configuration, and you notice your terminal prompt includes a hostname you do not recognize. Pause and predict: what is the safest next step, and why is "edit and hope" dangerous here? Commit to an answer before revealing the explanation.

<details>
<summary>Check your prediction</summary>

The safest next step is not to edit and hope; it is to run `hostname` and `pwd`, confirm the machine and directory, and only then open the file. Terminal editing is precise, but precision cuts both ways when you are connected to the wrong place.

</details>

## Patterns & Anti-Patterns

Make one meaningful change, save it, exit, and verify the saved file before moving on. This gives you a checkpoint when something goes wrong.

The matching anti-pattern is treating successful editing as proof of correct behavior. Saving a file proves only that bytes were written to disk. It does not prove that a service can parse the file, that a script has permission to run, or that the commands inside the script are correct. That is why every edit should be followed by the smallest verification command that checks the next layer of meaning.

| Situation | Use This Pattern | Avoid This Anti-Pattern |
|-----------|------------------|--------------------------|
| You need to inspect a short file | Run `cat filename` first, then edit only if needed | Opening `nano` just to read and accidentally changing text |
| You need to make a small edit | Open with `nano`, save with Ctrl+O, exit with Ctrl+X, verify with `cat` | Assuming the file saved because the editor was open |
| You need to run a script directly | Check the shebang and `ls -l script.sh`; add a missing owner execute bit before `./script.sh` | Believing the `.sh` suffix or an unchecked chmod retry proves the cause |
| You are on a remote host | Confirm `hostname` and `pwd` before editing sensitive files | Editing quickly without checking which machine you are on |

## When You'd Use This vs Alternatives

For this module, the decision framework is intentionally simple. Choose the tool that matches the amount of change and the amount of risk. If there is no change to make, use a viewer. If the change is small and the environment is terminal-only, use `nano`. If the edit is complex and you are comfortable with modal editing, use `vim`. If you are working on a local project with many files, a graphical code editor may be the better environment.

| Need | Better Choice | Why |
|------|---------------|-----|
| See a short file exactly once | `cat filename` | It cannot accidentally edit the file |
| Make a beginner-friendly terminal edit | `nano filename` | Visible shortcuts reduce memory burden |
| Make repeated advanced terminal edits | `vim filename` | Motions and commands scale after practice |
| Run saved commands repeatedly | Inspect `ls -l script.sh`, add a missing owner execute bit to your owned training script, then `./script.sh` | Direct execution needs the appropriate access; persistent errors need diagnosis |
| Confirm where you are before editing | `pwd` and `hostname` | Location mistakes are easier to prevent than repair |

You can also think in terms of reversibility. Viewing is easy to back out of because it changes nothing. Editing is reversible only if you know what changed or have a backup. Running a script can affect many files or commands at once, so scripts deserve both content verification and permission awareness. This ladder of risk helps you slow down at the right moments without becoming afraid of the terminal.

The best choice is often the one that leaves the most evidence. A `cat` command leaves visible output in your terminal scrollback. A saved script leaves a file you can reopen and inspect. A `chmod +x` command changes a permission bit that can be checked later with tools you will learn in the next terminal lessons. When you choose tools this way, you build a trail that helps you and other engineers understand what happened.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Confusing suspension with exit | A suspended editor has not exited | If the shell reports a stopped editor, run `fg` to resume it, then use the displayed exit command |
| Forgetting to save before exiting | Beginners expect autosave, but `nano` writes only when told to write out | Press Ctrl+O and Enter before Ctrl+X, or answer `Y` carefully when prompted |
| Typing `^O` literally into the file | The caret notation looks like two printable characters if you have not seen terminal shortcuts before | Hold Ctrl and press O; do not type the caret character |
| Using `nano` when you meant to use `cat` | You wanted to inspect a file but opened an editor capable of changing it | Use `cat filename` for short read-only checks and reserve `nano` for edits |
| Editing a file on a remote server thinking it is local | Terminal prompts can look similar, especially when several sessions are open | Run `hostname` and `pwd` before changing important files |
| Opening and saving a binary file in `nano` | The editor treats bytes as text and can corrupt non-text formats | Run `file filename` when unsure, and edit only plain text files |
| Assuming `.sh` makes a script executable | File extensions are human conventions, while execute permission is a filesystem mode | Check the shebang and `ls -l`; add a missing owner execute bit and investigate access errors that persist |

## Quiz

<details>
<summary>Your teammate says they saved `hello.txt`, but `cat hello.txt` still shows the old version. What should you check first, and why?</summary>

Start by checking whether they actually used Ctrl+O and confirmed the filename before exiting. `nano` can hold unsaved changes in its buffer, and closing or discarding that buffer leaves the file on disk unchanged. If they did save, check `pwd` to confirm they edited and viewed the same directory. The key diagnosis is to separate editor memory, saved file content, and current working directory.

</details>

<details>
<summary>You are editing a crucial configuration file and the nano menu says `^O Write Out`. You type the characters `^O` into the file. What went wrong?</summary>

The caret notation represents the Ctrl key, not text that should be typed literally. The correct action is to hold Ctrl and press O at the same time, then press Enter to confirm the filename. Terminal programs often use this notation because it is compact and works in text interfaces. Typing the characters added content to the buffer, so you should remove those characters before saving.

</details>

<details>
<summary>You wrote `backup.sh`, ran `./backup.sh`, and received `Permission denied`. What layer failed, and what is the focused fix?</summary>

The message identifies an access failure, but does not establish its exact cause. Inspect `ls -l backup.sh`; if this is your practice script and the owner's execute bit is missing, add it with `chmod +x backup.sh` and retry. If permission is already present or the failure persists, stop and ask for help checking path access or execution restrictions. A subsequent Bash syntax error belongs to the interpreter-parsing layer and requires inspecting the reported line instead.

</details>

<details>
<summary>A script starts with `echo "Starting backup"` and no shebang. It runs with `bash backup.sh` but behaves unpredictably with `./backup.sh`. What should you change?</summary>

Add a shebang such as `#!/bin/bash` as the first line when the script is intended to run directly. Running `bash backup.sh` chooses Bash explicitly, so the script can work in that form even without a shebang. Direct execution asks the operating system to choose an interpreter, and a shebang states that choice on this Linux training host. After editing, save, verify the first line, and make sure execute permission is present.

</details>

<details>
<summary>You need to confirm whether a short file contains one setting, but you do not intend to change anything. Should you use `cat` or `nano`, and why?</summary>

Use `cat` for a short read-only check because it prints the file without opening an edit buffer. That reduces the chance of accidental changes and keeps the command focused on inspection. If the file is too long for comfortable printing, a pager is better than an editor, but that appears in a later module. Use `nano` only when you have decided to make a change.

</details>

<details>
<summary>You moved lines around with Ctrl+K and Ctrl+U, saved, and now a script prints messages in the wrong order. How should you debug it?</summary>

Reopen the script with `nano` and read the surrounding lines in order, not just the line you remember moving. Cut-and-paste operations can move more than one line if you pressed Ctrl+K repeatedly, so the final arrangement matters. After correcting the order, save and run the script again. This is a content problem rather than a permission problem if the script already starts and prints output.

</details>

<details>
<summary>You are connected to a remote host and about to edit a file that controls a practice service. What two commands help prevent an edit in the wrong place?</summary>

Run `hostname` to confirm which machine you are connected to, and run `pwd` to confirm the current directory. Those checks are quick and prevent a common remote-work mistake: changing a file successfully, but on the wrong host or in the wrong directory. After editing, verify the saved file with a viewer such as `cat` when the file is short. Safe terminal work depends on confirming context before and after the edit.

</details>

## Hands-On Exercise: Kitchen Memo Board

In this exercise you will create a small memo file, edit it, write a script that reads it, grant execute permission, and run the script. The scenario is intentionally ordinary because the mechanics are the lesson. If you can do this calmly with a training memo, you can later apply the same loop to shell helpers, Markdown notes, YAML manifests, and service configuration files.

Continue in the exclusive workspace created under **Opening, Editing, Saving, and Exiting**. If you skipped that section, complete its setup first; never open these fixed filenames in an unfamiliar directory. Confirm the workspace with `pwd` and inspect its entries before editing. Username, date, and workspace path may differ; unexpected files or failed navigation mean stop before editing or cleanup. Diagnose other errors by layer: directory, save, access, or script content.

As you work, say the loop out loud if it helps: open, edit, save, exit, verify. For the script portion, add two more words: permit and run. That may sound overly deliberate for a beginner exercise, but deliberate sequencing is how terminal work becomes predictable. The shell will not remind you that a file is unsaved after you leave the editor, and it will not guess that a text file should be executable because it ends in `.sh`.

### Part 1: Create and edit a memo

```bash
pwd
ls -a
nano kitchen-memo.txt
```

Type the following five lines:

```text
=== KITCHEN MEMO BOARD ===
1. Morning prep starts at 6 AM
2. New menu items arriving Thursday
3. Remember: clean as you go
4. Staff meeting at 3 PM Friday
```

Save with Ctrl+O, press Enter, and exit with Ctrl+X. Then verify your saved work with `cat`. Verification is part of the exercise, not an optional extra, because it proves the file on disk contains the memo rather than merely proving that you typed text into an editor buffer.

```bash
cat kitchen-memo.txt
```

You should see all five lines printed exactly as you typed them:

```text
=== KITCHEN MEMO BOARD ===
1. Morning prep starts at 6 AM
2. New menu items arriving Thursday
3. Remember: clean as you go
4. Staff meeting at 3 PM Friday
```

### Part 2: Edit the memo

Open the memo again and add a sixth line at the bottom. This step confirms that reopening an existing file is the same basic workflow as creating a new file, except that `nano` loads the previous contents into the buffer first. Move with the arrow keys if needed, type the new line, save, exit, and verify again.

```bash
nano kitchen-memo.txt
```

Add this line:

```text
5. Chef says: great work today, team!
```

Save and exit with Ctrl+O, Enter, and Ctrl+X. Then verify that all six lines are present:

```bash
cat kitchen-memo.txt
```

### Part 3: Write a report script

Now create a script that prints a short status report and includes the memo contents. This script combines fixed text, command substitution, and a file-reading command. It is still small, but it demonstrates the reason scripts matter: they preserve a repeatable sequence of terminal actions in a text file.

```bash
nano kitchen-report.sh
```

Type this script **inside nano**, not at the shell prompt:

```bash
#!/bin/bash

echo "=== Kitchen Status Report ==="
echo "Date: $(date)"
echo "Chef on duty: $(whoami)"
echo ""
echo "--- Memo Board Contents ---"
cat kitchen-memo.txt
echo ""
echo "--- Files in current directory ---"
ls
echo ""
echo "Report complete. Kitchen is running smoothly!"
```

Save and exit, then inspect the saved script and its permissions before granting execute permission and running it from the workspace. If "Permission denied" persists despite an owner execute bit, stop and ask for help with path access or execution restrictions rather than repeating `chmod`.

```bash
cat kitchen-report.sh
ls -l kitchen-report.sh
chmod +x kitchen-report.sh
./kitchen-report.sh
```

Expected output will vary in the date, username, and file listing:

```text
=== Kitchen Status Report ===
Date: Mon Mar 23 14:45:00 UTC 2026
Chef on duty: yourname

--- Memo Board Contents ---
=== KITCHEN MEMO BOARD ===
1. Morning prep starts at 6 AM
2. New menu items arriving Thursday
3. Remember: clean as you go
4. Staff meeting at 3 PM Friday
5. Chef says: great work today, team!

--- Files in current directory ---
hello.txt    kitchen-memo.txt    kitchen-report.sh    my-first-script.sh
...

Report complete. Kitchen is running smoothly!
```

### Part 4: Diagnose and fix a broken script (unguided)

Parts 1 through 3 told you every command to run. This part removes the scaffolding and tests whether you can diagnose a failure on your own. Use GNU nano in your workspace to create `broken-report.sh`; type this content inside the editor, including the intentional mistakes, rather than pasting it at the shell prompt:

```bash
#!/bin/bash

echo "=== Broken Kitchen Report ===
echo "Date: $(date)"
echo "Memo follows:"
cat kitchen-memo.txt
```

Save the file, then run it directly with `./broken-report.sh`. Something is wrong at more than one layer, and this time nobody tells you which layer fails first. Work the diagnostic sequence from this module: read the exact error message, decide whether the failure is permission, interpreter parsing, or script logic, fix only that layer, and run the script again. Repeat until the script prints the heading, the date, and the memo contents. Before you call it fixed, verify the final file contents with `cat broken-report.sh` so you can see exactly what changed.

<details>
<summary>Check your diagnosis</summary>

In this fresh workspace, inspect `ls -l broken-report.sh` after an access error. If the owner's execute bit is missing, add it with `chmod +x broken-report.sh` and retry. If it is already set or access still fails, stop and ask for help checking path access or execution restrictions. Once Bash starts, the first `echo` line's missing closing quotation mark causes an unterminated-string error. Correct it to `echo "=== Broken Kitchen Report ==="` with `nano`, save, and run `./broken-report.sh` again. A correct run prints the heading, current date, "Memo follows:", and six memo lines. These are separate access and parsing layers; the error message and mode check determine which one to address. Running `bash broken-report.sh` selects Bash explicitly and can reveal the content error before adding execute permission.

</details>

### Part 5: Clean up

Cleanup is optional. Remove only the training files you created in this run's exclusive workspace. First run `pwd` and `ls -l`, then stop and check that the path and every named file belong to this lesson. If you changed directories, lost track of ownership, or see unexpected entries, do not run `rm`. Read its filenames carefully: it removes files without sending them to a graphical trash folder. Omit any file you did not create; never substitute a wildcard or a recursive removal command.

```bash
pwd
ls -l
```

Only after that check, remove the known disposable files; leave the workspace directory itself in place:

```bash
rm hello.txt kitchen-memo.txt kitchen-report.sh my-first-script.sh broken-report.sh
```

Success criteria:

- [ ] You created `hello.txt` and verified it with `cat`.
- [ ] You edited `hello.txt` after reopening it with `nano`.
- [ ] You created `kitchen-memo.txt` and verified the memo contents.
- [ ] You wrote `kitchen-report.sh` with a valid `#!/bin/bash` shebang.
- [ ] You used `chmod +x kitchen-report.sh` before running it directly.
- [ ] You diagnosed any error by separating directory, save, permission, and script-content problems.
- [ ] You diagnosed `broken-report.sh` without step-by-step guidance, identifying the permission failure and the missing-quote failure as separate layers.
- [ ] You fixed `broken-report.sh` with `chmod +x` and a `nano` edit, then verified the corrected output by direct execution.

## Sources

- [GNU nano 7.2 manual](https://www.nano-editor.org/dist/v7/nano.html)
- [GNU nano 7.2 shortcut reference](https://www.nano-editor.org/dist/v7/cheatsheet.html)
- [GNU nano homepage](https://www.nano-editor.org/)
- [Vim Reference Manual: Introduction](https://raw.githubusercontent.com/vim/vim/master/runtime/doc/intro.txt)
- [Bash Reference Manual: Shell Scripts](https://www.gnu.org/software/bash/manual/bash.html#Shell-Scripts)
- [Bash Reference Manual: Command Substitution](https://www.gnu.org/software/bash/manual/bash.html#Command-Substitution)
- [GNU Coreutils manual: cat invocation](https://www.gnu.org/software/coreutils/manual/html_node/cat-invocation.html)
- [GNU Coreutils manual: chmod invocation](https://www.gnu.org/software/coreutils/manual/html_node/chmod-invocation.html)
- [The Open Group: chmod](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/chmod.html)
- [Linux man-pages: execve](https://man7.org/linux/man-pages/man2/execve.2.html)

## Next Module

[Module 0.6: Git Basics](../module-0.6-git-basics/) teaches you to track edits over time with version control, which is the next step after you can create, change, and verify files from the terminal.
