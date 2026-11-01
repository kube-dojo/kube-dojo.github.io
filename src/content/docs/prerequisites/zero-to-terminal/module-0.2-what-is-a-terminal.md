---
title: "Module 0.2: What is a Terminal?"
slug: prerequisites/zero-to-terminal/module-0.2-what-is-a-terminal
sidebar:
  order: 3
revision_pending: false
---
> **Complexity**: `[MEDIUM]` - Long-form foundational read for absolute beginners
>
> **Time to Complete**: 90–120 minutes (long-form beginner read + hands-on prompts)
>
> **Prerequisites**: None.

---

## What You'll Be Able to Do

After this module, you will be able to perform these beginner terminal tasks and explain the reasoning behind each one:

- **Compare** graphical interfaces and terminal interfaces, then choose the better tool for a beginner engineering task.
- **Open** a terminal on macOS, Windows, or Linux and **diagnose** what the visible prompt is telling you.
- **Run** simple commands such as `echo`, a shell-appropriate date/time command (`date` or `Get-Date`), `whoami`, and `hostname`, then **interpret** the output without guessing.
- **Debug** common beginner terminal problems, including copied prompt symbols, command typos, incomplete quotes, and long-running commands.

---

## Why This Module Matters

Hypothetical scenario: you are following a Kubernetes setup guide for version 1.35, and the first instruction says to open a terminal and run a command. If the terminal feels mysterious, the guide stops being a guide and becomes a wall. You might not know whether to type the `$` symbol, whether the command has already run, why the cursor moved to a new line, or how to cancel something that is printing too much output.

Tools you will meet later, such as Git and `kubectl`, can be used through commands. This module introduces how to read a prompt, enter a command, and connect its output to the machine you are using.

This module compares a GUI with a terminal. You will open a terminal, read a prompt, try commands that print information, and practice recovering from an unfinished line.

## GUI and Terminal: Two Interfaces, Different Strengths

A GUI, or Graphical User Interface, gives you icons, windows, buttons, menus, file pickers, and visual feedback. Clicking a browser icon or moving a photo into a folder uses these visible controls to communicate with the computer.

A GUI can show a chart, colors, photos, or a diagram directly. Menus, toolbars, and dialogs can also show available choices without requiring you to remember command names. These features can be useful for visual work and exploring an unfamiliar application.

A terminal is also an interface, but it is text based. Instead of clicking visible controls, you type an instruction and press Enter. The computer prints a response, changes something, or starts a program. It may look plain because the terminal is not trying to show every possible action at once; it is waiting for you to describe exactly what you want in a small command language.

Here is the smallest possible picture of a prompt waiting for input, shown by itself so you can focus on the signal:

```text
$
```

That single symbol is easy to underestimate. It means the shell is ready for a command, much like a blank search box means a browser is ready for a query. The terminal does not remove the computer's graphical abilities; it gives you another way to operate the same machine, one that is especially good for precise, repeated, text-heavy work.

Choose according to the task. A GUI can help with visual inspection and discovery; a terminal can help you write down and repeat commands, work remotely, or automate a sequence. You can use both in the same workflow.

A command is text that can be saved in a note or script, reviewed, and run again. Before repeating it, check that its effects and target are still appropriate.

Later, you can use `kubectl` to ask questions about Kubernetes resources. Here you will practice the same input-and-output pattern with commands that print information.

| Interface | Strong At | Weak At | Beginner Signal |
|---|---|---|---|
| GUI | Visual inspection, discovery, drag-and-drop work, dashboards | Repeating many exact steps, documenting every click, remote text-only servers | You mostly click visible controls |
| Terminal | Precise commands, automation, remote access, repeatable troubleshooting | Visual editing, first-time exploration, tasks where pictures carry the meaning | You type a command and read text output |

Pause and predict: if you had to rename hundreds of files the same way, which interface would you choose, and why?

<details>
<summary>Check your prediction</summary>

A typed instruction can be tested, reviewed, saved, and rerun for a uniform change. A GUI may be useful when the pattern is irregular or needs visual inspection. Either approach needs a check of the intended changes before altering files.

</details>

For example, renaming files one at a time in a GUI involves repeating the rename steps for each file. A shell loop can express a uniform pattern once and apply it repeatedly. Either way, check the intended names and any existing files before changing them.

> **Illustration only — do not run this yet**
>
> Here is what a file-renaming loop *looks like* in a shell. You have not learned file operations or loops yet; running it would rename real `.txt` files on your machine and can overwrite existing `backup_*.txt` names. Read it for the idea; you will run commands like this in a later module.

```text
for f in *.txt; do mv "$f" "backup_$f"; done
```

The loop is an illustration of how text can describe a repeated action. You will learn the commands needed to understand and check file operations later.

## Opening the Terminal and Reading the Prompt

Opening the terminal is slightly different on each operating system, but the first goal is the same everywhere: get to a window that shows a prompt and a blinking cursor. On macOS, press Cmd + Space, type Terminal, and press Enter. On many Linux desktops, Ctrl + Alt + T opens a terminal, and the applications menu usually has a Terminal entry if the shortcut is disabled.

Windows has several valid options, and they serve different purposes. Windows Terminal is Microsoft's modern terminal application and is a good day-to-day container for shells. WSL, the Windows Subsystem for Linux, gives you a Linux-style shell on Windows; use a WSL tab for the Unix command names in this module (`date`, `date -u`, and bash-style examples such as `$(date)`). PowerShell is a separate shell with its own command names and subexpression syntax. Profiles can define aliases or functions, so availability depends on the host; for a predictable PowerShell path in this module, use the native `Get-Date` and `Write-Output` examples below. WSL is recommended for the rest of this curriculum when later modules expect Unix command names.

If you choose WSL later, the official installation path starts from PowerShell and uses Microsoft's installer command. You do not need to run it for this module, but seeing the shape of the command helps you recognize that terminal instructions can install real tools. This curriculum will return to WSL when the operating system details matter more.

```powershell
wsl --install
```

When a terminal opens on macOS, you might see an informational login message before the prompt, similar to this example:

```text
Last login: Mon Mar 23 10:15:00 on ttys000
yourname@your-mac ~ %
```

In this example, "Last login" is informational and the line ending with `%` is the prompt. A Linux or WSL prompt may end with `$` instead. Prompt content is customizable: it may show a user, machine, or directory, but these details are not guaranteed.

It helps to separate three words that people often mix together. The terminal application is the window that displays text and accepts keyboard input. The shell is the program inside that window that reads your command line and starts commands. The prompt is the small piece of text printed by the shell to show that it is ready for another instruction.

Different systems may use different shells. macOS Terminal defaults to zsh unless configured otherwise; Linux systems can use Bash, and Windows PowerShell has its own language and conventions. Follow the branch for your shell while comparing the shared pattern of commands, output, and prompts.

```text
yourname@yourcomputer ~ $
```

Here is the same prompt broken into parts. Treat it like a map label printed at the edge of your working area. Before you run a command, the prompt helps you check whether you are the expected user, on the expected machine, in the expected location, and looking at a shell that is waiting for input.

| Part | Meaning in this example |
|------|-------------------------|
| `yourname` | Your username on this computer |
| `@` | "at" |
| `yourcomputer` | The name of your computer |
| `~` | Your home directory |
| `$` or `%` | The shell is ready for your command |

PowerShell commonly shows a normal prompt such as `PS C:\Users\Learner>`. Its final `>` is part of that prompt, not automatically an unfinished command. Compare it with the different continuation prompt after an incomplete line: often `>` in Bash, `dquote>` in zsh for an open double quote, or `>>` in PowerShell. Prompt text is customizable, so compare the change with your own starting prompt rather than trusting one symbol alone.

This curriculum sometimes shows a prompt symbol at the start of an example line to distinguish the prompt from the command:

```text
$ echo "Hello"
```

In that example, `$` is a prompt cue, not part of the command. Type only `echo "Hello"`; copying the prompt symbol can produce an error.

Watch for your usual command prompt to return before typing the next command. If it has not returned, a program may still be running or waiting, or the shell may need more input to finish your line. A continuation prompt is different from the usual prompt: read the preceding command and compare the display before deciding what to do next.

Some commands print a result, some print errors, and some successful commands print nothing. Watch for the normal prompt to return, then use the command's documentation and output to decide what happened.

## Your First Information Commands

The examples in this section ask standard commands to print information without changing files: `echo` prints text, `date` or `Get-Date` reports date and time, `whoami` reports the account, and `hostname` reports the machine name. Shell functions, aliases, or local configuration can change which command runs, so use the expected shell and check unfamiliar environments. Type an instruction, press Enter, read the output, and wait for the prompt.

Before running this, what output do you expect from `echo` when the argument is `Hello, World!`? Write your prediction in plain language, then compare it with the output.

```bash
echo 'Hello, World!'
```

<details>
<summary>Check your prediction</summary>

You should see this output, which confirms that `echo` received the text argument and printed it back:

```text
Hello, World!
```

</details>

The command name is `echo`, and its text argument is `Hello, World!`; the single quotes group that text without becoming part of the output. An argument is information you give to a command. Here we use single quotes for literal text because interactive zsh can treat `!` specially inside double quotes. Later, double quotes let us insert command output into a sentence.

Now ask the computer for the date and time. The exact output depends on your operating system, timezone, locale, and shell, so do not worry if yours is formatted differently from the example. What matters is that the command returns a timestamp and then gives you the prompt again. Use the branch that matches the shell you opened:

**Bash, zsh, or WSL:**

```bash
date
```

**PowerShell:**

```powershell
Get-Date
```

The PowerShell [`Get-Date` cmdlet](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/get-date?view=powershell-7.5) is the native date/time example used in this module. A different shell or profile may expose additional aliases, but follow the branch that matches the command language you are using.

One possible output looks like this, but your local timezone and formatting may produce a different line:

```text
Mon Mar 23 14:30:00 UTC 2026
```

You can include a timestamp in notes or a script to record what the machine's clock reported. Record the timezone too, and check clock accuracy when the timing matters.

Next, ask which user account is running the shell, because identity affects permissions and ownership:

```bash
whoami
```

You should see a username, such as the account name your operating system uses internally:

```text
yourname
```

On a shared or remote system, checking the account helps you determine whether you are working as the intended user. The account can affect permissions and file ownership.

Finally, ask the machine for its name so you can connect the current terminal window to a specific computer:

```bash
hostname
```

You might see output like this, although managed laptops, virtual machines, and WSL environments often use different naming patterns:

```text
your-mac.local
```

Machine names matter when you have more than one terminal window open. Imagine one tab is connected to a practice machine and another is connected to a production server. A visible hostname gives you a chance to stop before running the right command in the wrong place, which is one reason many engineers customize prompts to make important environments stand out.

Exercise scenario: you have two terminal windows open during a practice lab. One prompt says `alex@laptop ~ $`, and the other says `alex@training-vm /tmp $`. Which would you use for a command intended only for the training machine, and what part of the prompt supports your decision?

<details>
<summary>Check your prediction</summary>

In this exercise, choose the window labeled `alex@training-vm /tmp $`; the hostname label distinguishes it from the laptop window. In a real session, prompts can be customized or outdated. Use them as orientation clues, confirm which local or remote session you opened, and compare the read-only `whoami` and `hostname` output before changing anything. A prompt label alone does not establish machine identity or permissions.

</details>

Output can be different without being wrong. Your `date` format may include a timezone name instead of `UTC`, your username may be shorter than the name you use in a graphical login screen, and your hostname may look automatically generated. The terminal is reporting how the system identifies itself internally, so treat differences as clues about the environment rather than as failures to match a screenshot.

Before running a command, state what you expect it to do. For `whoami`, expect the current account; for `hostname`, expect the machine name. Then compare the output with that expectation.

You can keep a command journal with the command, a short sample of its output, and why you ran it. Avoid sharing private output when you share your notes.

## Command Structure and Quoting

For the simple commands in this lesson, read the command name first. Options modify its behavior, and arguments supply text or other data, such as a file, directory, server name, or URL.

```text
command [options] [arguments]
```

Square brackets in a teaching diagram mean "optional," not something you literally type. A command may have no options, one option, many options, no arguments, or several arguments. The shell splits the line into pieces, identifies the command name, and passes the remaining pieces to that command according to the program's own rules.

Whitespace is part of that structure. The shell normally uses spaces to separate the command name, options, and arguments, which is why quotes matter when one argument contains spaces.

| Part | What It Is |
|------|------------|
| Command | The action to perform |
| Options | Modifiers, often starting with `-` |
| Arguments | Data to act on, such as text or a file |

The following example has one command and one argument. Quotes group text into one argument; without quotes, an unquoted space can separate arguments. Special characters can also have shell-specific meanings.

```bash
echo "Hello"
```

The command is `echo`, and the argument is `"Hello"`. The shell removes the quotes as syntax and gives the command the text inside them. That distinction is subtle at first: quotes are not decorations for humans, they are instructions to the shell about how to group words before the command receives them.

Options change behavior. The `date` command normally prints the local time, but the `-u` option asks for UTC. UTC is a standard time reference used heavily in distributed systems because it avoids confusion when people, servers, or logs are spread across time zones. This option is for Unix-style shells (macOS, Linux, WSL); PowerShell uses `Get-Date` with UTC-oriented formatting instead.

```bash
date -u
```

This command has a command name, `date`, and an option, `-u`. There is no extra argument because the command already knows the thing it is supposed to print. Other commands will need arguments, such as a filename, a directory path, or a Kubernetes resource name, but the structure stays familiar.

Options often have short and long forms, although the exact names depend on each command. A short option may look like `-u`, while a long option may look like `--help` or `--version`. Check the command's help or manual for the options it accepts.

The diagram shows the roles in three examples. The shell processes spaces, quotes, and special syntax into pieces for the command.

```text
+----------------------+----------------------+----------------------+
| Command              | Option               | Argument             |
+----------------------+----------------------+----------------------+
| date                 | -u                   |                      |
| echo                 |                      | Hello, World!        |
| hostname             |                      |                      |
+----------------------+----------------------+----------------------+
```

An opening quote without its closing partner leaves this command unfinished. Instead of running it, the shell may show a continuation prompt such as `>` and wait for the rest of the text.

Compare `Hello World` with `"Hello World"`: the first contains two unquoted words; the second groups the text as one argument. A command can interpret those argument lists differently.

```bash
echo "This command is missing its closing quote
```

You can type the missing quote and press Enter, or cancel the unfinished input with Ctrl+C and return to a fresh prompt. In Unix terminals, Ctrl+C normally generates an interrupt signal, SIGINT. PowerShell and terminal hosts also have cancellation behavior, but keyboard bindings and text selection can change what the key does; check that your normal prompt returned.

```text
>
```

Here the prompt changed after an unfinished quote, so the shell is asking for more input. Your shell might show `>`, `dquote>`, or `>>`, depending on its language and configuration. The important evidence is the incomplete command and the change from your normal prompt, rather than the presence of a particular angle bracket.

Try one more safe combination. These examples insert command output into a sentence using shell-specific command names. You do not need to master command substitution or subexpressions yet; just notice that terminal commands can be composed.

**Bash, zsh, or WSL:**

```bash
echo "Today is $(date) and I am $(whoami)"
```

**PowerShell:**

```powershell
Write-Output "Today is $(Get-Date) and I am $(whoami)"
```

PowerShell uses the [`$()` subexpression operator](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_operators?view=powershell-7.5#subexpression-operator--) inside the native `Write-Output` command. In either branch, `whoami` reports the account running that shell; read the output as evidence about the current session.

Composition combines smaller commands into a larger instruction. Here, the inner commands supply values for the message.

There is a safety lesson inside composition too. When a command contains smaller commands, the shell has to evaluate some parts before the final command runs. That is powerful, but it also means you should read composed commands more carefully than single-word commands. In this module the composed command only prints text, so it is a good place to see the mechanism without risking files or system settings.

Longer commands can also include subcommands, resource names, and options. Identify each part's role and consult the command's documentation when you are unsure.

## Recovering When the Terminal Feels Stuck

Before correcting a mistake, identify the shell's state and whether a command is still running. The exercises below use information commands and an intentionally unfinished line; inspect unfamiliar commands before running them because their effects vary.

The first recovery habit is to compare the display with the normal prompt you saw when you opened this shell. If that prompt has returned, you can enter another command. If output keeps arriving without it, a command may still be running. If an unfinished quote changes the prompt, the shell is waiting for more input. PowerShell's normal prompt can already end in `>`, so that character alone is not a diagnosis.

Ctrl+C is a useful first cancellation attempt when a command runs too long or waits unexpectedly. In Unix terminals it normally sends SIGINT to the foreground process group. In PowerShell with common PSReadLine bindings, Ctrl+C can copy selected text instead of canceling input; deselect the text before trying to cancel. Host applications and key bindings vary, so watch for the normal prompt rather than assuming the key always stopped the command.

```text
Ctrl+C
```

Ctrl+C is not universal, so keep the boundary clear. If the terminal application itself is frozen, closing and reopening the window may be more practical. If you are inside a full-screen program such as `less`, `top`, or `vim`, that program may have its own quit key. If a program deliberately ignores SIGINT, you may need a stronger tool later, but that is beyond today's beginner scope.

Another common recovery move is reading errors literally. If the shell says `command not found`, it usually means the first word did not match an installed command or program. That can happen because of a typo, wrong capitalization, copying the prompt symbol, or trying to run a tool before installing it. The error sounds severe, but it is often just the shell saying it cannot find a program by that name.

```text
echoo: command not found
```

Before running a copied command, check for a leading prompt symbol, balanced quotes, and the capitalization shown in the example. Does the command change something or only print information? Check its documented effects when you are unsure.

Later Kubernetes examples use full commands such as `kubectl get pods`; aliases do not reliably expand in non-interactive scripts. Check the current context, namespace, and output when working with a cluster.

Recovery also includes preserving useful evidence. If a command prints an error, resist the urge to clear the screen immediately. Read the first line, look for the command name, and notice whether the message is about spelling, permissions, missing files, or incomplete input. Even when you cannot fix the problem yet, keeping the message visible gives you something specific to search, ask about, or compare with documentation.

For this practice, change one thing between attempts. Changing the command name, quotes, and current directory together leaves several possible explanations for a different result. Make one correction, run once, and read the output before choosing the next correction.

Another rule is to prefer a reversible next step when you are uncertain. If you are unsure where you are, ask a question first instead of running an action. If you are unsure what a command printed, copy the message into your notes before clearing it. If you are unsure whether a command is still running, wait briefly and look for the prompt before pressing more keys.

## Patterns & Anti-Patterns

Try the pattern "predict, run, compare": before pressing Enter, state what you expect the command to do; afterward, compare the output with your prediction.

| Pattern | When To Use It | Why It Works |
|---|---|---|
| Predict before pressing Enter | Any new command, even a tiny one | It turns output into feedback instead of noise |
| Use information-only commands first | When learning a new shell or machine | They let you inspect the environment before making changes |
| Keep examples copy-paste runnable | When writing notes or teaching someone else | It provides complete commands without tutorial prompt cues |
| Read the prompt before acting | When multiple terminals or remote systems are open | It offers clues to check against the intended session |

Record the command and relevant output alongside your explanation. For example, note that `whoami` reported the current account. A teammate may need to match your shell and tools before repeating the command; the output records what your machine reported at that moment.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|---|---|---|
| Copying the `$` prompt symbol | The shell may treat `$` as unexpected input or produce confusing errors | Copy only the command text after the prompt |
| Memorizing commands without meaning | Command, option, and argument roles remain unclear | Learn those roles in the worked examples |
| Using aliases in shared scripts | The script fails where the alias is not defined | Write full command names in examples and scripts |
| Closing the terminal for every mistake | You can discard error messages before inspecting them | Use Ctrl+C or complete the unfinished input when appropriate |

## When You'd Use This vs Alternatives

For this introductory module, the decision framework is deliberately simple. Choose the terminal when the task is textual, repeatable, remote, scriptable, or easier to document as commands. Choose a GUI when the task is visual, one-off, exploratory, or better understood by direct manipulation. Choose both when the GUI helps you inspect the state and the terminal helps you perform or record the action precisely.

| Situation | Better Starting Tool | Reason |
|---|---|---|
| Checking which user you are on a server | Terminal | `whoami` gives direct text output that can be copied into notes |
| Drawing an architecture diagram | GUI | Shape, spacing, and visual layout are the actual work |
| Installing command-line tooling on WSL | Terminal | Official setup guides usually provide commands |
| Watching a dashboard for traffic spikes | GUI | A chart shows changes over time |
| Repeating the same file operation many times | Terminal | A command or script avoids repetitive clicking |
| Exploring an unfamiliar desktop app | GUI | Menus and buttons reveal available actions |

Which approach would you choose here and why: you need to document a setup process so a teammate can reproduce it tomorrow. Commit to an answer before opening the reveal.

<details>
<summary>Check your prediction</summary>

A GUI may help with initial exploration. Where commands suit the task, include exact commands and explain their effects; screenshots or described controls can help document visual steps. Check that a teammate can follow the instructions in their environment.

</details>

The same decision applies inside a single workflow. You might use a GUI dashboard to notice that an application is unhealthy, then use terminal commands to collect logs, check the current user, record timestamps, and run the exact diagnostic sequence again after a fix. Thinking this way keeps the terminal grounded in practical work instead of treating it as a separate world from the rest of the computer.

## Did You Know?

1. **Input could be recorded before the computer read it.** IBM's [punched-card history](https://www.ibm.com/history/punched-card) describes characters encoded as holes in cards and a separate reader that loads their data. A prepared card could hold input until it was read. In the interactive session practiced here, you type a command and read its output in the terminal.

2. **A terminal could be a physical keyboard and screen.** The [DEC VT100 User Guide](https://vt100.net/docs/vt100-ug/chapter1.html) describes a keyboard that sends information to a computer and a video screen that displays data sent back by that computer. This division helps explain a modern terminal emulator: it provides the input/output interface, while the shell is the program that interprets your commands.

3. **SSH has been standardized for decades as a secure remote-login protocol family.** RFC 4251 describes the Secure Shell architecture. OpenSSH provides SSH tools, including a client and a server.

4. **Windows Terminal was announced in 2019; version 1.0 was released in May 2020.** Microsoft's [announcement](https://devblogs.microsoft.com/commandline/introducing-windows-terminal/) and [1.0 release post](https://devblogs.microsoft.com/commandline/windows-terminal-1-0/) distinguish preview history from the stable release. It can host PowerShell, Command Prompt and WSL profiles; the terminal application and the shell are separate programs.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Typing the `$` symbol from an example | In this lesson's prompt-prefixed example, `$` is a cue rather than command text | Type only the command after the prompt; if you copied it, delete the leading `$` and any following space |
| Forgetting to press Enter | A terminal does not run a command while you are still editing the line | Press Enter once when the command is complete, then wait for output or the prompt to return |
| Misspelling the command name as `echoo` | The shell treats the first word as an exact program name, so near misses do not count | Check the spelling of the first word and rerun the corrected command |
| Changing capitalization, such as `Echo` instead of `echo` | Many shells and filesystems treat uppercase and lowercase as different characters | Match the command's capitalization exactly, especially on Linux and WSL |
| Forgetting a closing quote | The shell waits for more input, often showing `>` in Bash, `dquote>` in zsh, or `>>` in PowerShell | Compare with your normal prompt; finish the quote or cancel with Ctrl+C and no text selected |
| Panicking when output keeps printing | A running foreground process can temporarily prevent you from typing a new command | Press Ctrl+C once, then wait to see whether the normal prompt returns |
| Assuming every terminal window is the same machine | Multiple tabs can connect to different local or remote systems | Confirm which session you opened; compare prompt clues with read-only user and hostname checks |
| Using a short alias in notes meant for someone else | Aliases only exist if that shell session defines them, so examples can fail on another machine | Write full command names in shared instructions and scripts |

## Quiz

Test your understanding by answering each scenario before opening the explanation, then compare your reasoning with the detailed answer.

<details>
<summary>Question 1: You accidentally start a command that is printing endless lines of text, and you cannot type a new command. What is your immediate next step, and why?</summary>

Press Ctrl+C once, with no text selected, and watch for the normal prompt to return. In Unix terminals this normally sends SIGINT to the foreground process group; other hosts may handle cancellation differently. The command may still control the foreground until it responds. Full-screen programs can have their own quit keys, so consult the program's help if the normal prompt does not return.

</details>

<details>
<summary>Question 2: You try to echo a paragraph of text, but after pressing Enter the terminal shows `>` on a new line instead of your normal prompt. What likely happened, and how do you recover?</summary>

Because the prompt changed immediately after your echo command, check for an opening quote without a closing partner. The shell may be waiting for the rest of the text. Finish the quote and press Enter, or press Ctrl+C with no text selected to cancel. Compare the result with your normal prompt; PowerShell's normal prompt can itself end in `>`.

</details>

<details>
<summary>Question 3: You are switching between terminal windows and one prompt says `alice@db-primary-main /etc/config $`. What can you infer before running anything?</summary>

In this illustration, the labels suggest user `alice`, host `db-primary-main` and directory `/etc/config`. They are reasons to pause before changing anything, not independent proof of location or privilege: the prompt, including `$`, can be customized. Confirm which session you opened and compare its user and hostname checks with your intended training environment before proceeding.

</details>

<details>
<summary>Question 4: You need to record when you performed a server update. How could a shell-appropriate date/time command help, and what else would you check?</summary>

Use `date` in Bash or zsh, or `Get-Date` in PowerShell, to record what that machine's clock reports. Include the timezone and when the command was run relative to the update. Check clock accuracy and the timezone used by the logs before comparing them; a printed timestamp alone does not guarantee either an exact update time or aligned clocks.

</details>

<details>
<summary>Question 5: You need to apply the same configuration change on many training servers. What could a terminal workflow offer, and what would you check before repeating it?</summary>

A command or script can be saved, reviewed, and repeated. First check its effects and targets, test it in an appropriate training environment, and verify the result on each server. A repeated command can also repeat a mistake; a GUI may help inspect the resulting state.

</details>

<details>
<summary>Question 6: A colleague says GUIs are always better because they are more intuitive. How would you compare GUI and terminal choices without dismissing either one?</summary>

A GUI can make visual controls, diagrams, or charts useful to inspect. A terminal can provide commands to save, repeat, or use on a text-only remote session. Choose based on the task, available tools, and feedback you need; a workflow can use both.

</details>

<details>
<summary>Question 7: You paste a lesson command and receive a confusing error that mentions `$`. What should you inspect first?</summary>

Check whether you copied this lesson's `$` prompt cue along with the command. Remove that cue and its prompt-only spacing, then check the command's quotes and spelling before trying again.

</details>

<details>
<summary>Question 8: Your lesson notes use `date`, but your teammate on Windows opened PowerShell. What command should they run instead, and what continuation prompt will PowerShell show if they leave a quote unclosed?</summary>

Use `Get-Date`, the native PowerShell date/time command. With its default PSReadLine configuration, unfinished input produces `>>`; Bash often shows `>`, while zsh can show `dquote>` for an open double quote. These markers are configurable. Finish the quoted text or cancel with Ctrl+C and no text selected, then compare the result with the normal prompt you saw when the shell opened.

</details>

## Hands-On Exercise: Your First Terminal Session

### Objective

Open a terminal, run safe information commands, practice one recovery move, and finish by diagnosing frozen terminal snapshots without typing anything. This exercise is intentionally small because the goal is not speed. The goal is to build a reliable loop: predict the output, run the command, read the result, and confirm that the prompt returned.

### Setup

Use any terminal you can open today, then follow the branch for that shell. macOS Terminal and Linux terminals commonly use zsh or Bash; **Windows Terminal with a WSL Ubuntu profile** uses the Unix-style `date` and Bash composition shown below. PowerShell has its own branch using native `Get-Date`, `Write-Output`, and the PowerShell subexpression form `$()`; open a WSL tab only if you want to follow the Unix-style branch. If one command prints a slightly different format on your system, treat that as useful evidence rather than a failure.

### Tasks

1. Open your terminal using the instructions from this module, then pause long enough to identify the visible prompt. Write down the username, hostname if present, and prompt symbol in your own notes.

<details>
<summary>Solution guidance</summary>

On macOS, the prompt may end with `%`; on Linux and WSL, it often ends with `$`. Your prompt may include your username, machine name, current directory, Git branch, or other decorations depending on configuration. The success criterion is not matching the examples exactly. The success criterion is being able to explain what your own prompt is showing.

</details>

2. Run your first `echo` command and compare the output with your prediction.

```bash
echo 'Hello, World!'
```

The expected output is the text inside the quotes, printed without the quote marks because the shell used them only for grouping:

```text
Hello, World!
```

<details>
<summary>Solution guidance</summary>

If you typed only `echo 'Hello, World!'`, the terminal should print `Hello, World!` and return to the prompt. If you copied `$ echo 'Hello, World!'` and received an error, remove the leading prompt symbol and run the command again. That correction is part of the learning objective, not a sign that you failed.

</details>

3. Ask the computer for the current date and time. Use the command for the shell you opened.

**Bash, zsh, or WSL:**

```bash
date
```

**PowerShell:**

```powershell
Get-Date
```

The expected output is a timestamp from your own machine, so the following line is only one valid example:

```text
Mon Mar 23 14:30:00 UTC 2026
```

<details>
<summary>Solution guidance</summary>

Your exact timestamp will differ from the example because your machine has its own current time, timezone, and formatting rules. The important result is that the shell-appropriate command prints a timestamp and then the prompt returns. In Bash, zsh, or WSL, that command is `date`; in PowerShell, use the native `Get-Date` cmdlet shown above. The [`Get-Date` documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/get-date?view=powershell-7.5) describes the PowerShell form.

</details>

4. Check the current user and the current machine name.

```bash
whoami
hostname
```

Possible outputs are shown separately because your username and hostname come from different system settings and answer different questions:

```text
yourname
```

```text
your-mac.local
```

<details>
<summary>Solution guidance</summary>

`whoami` should print the account running the shell, and `hostname` should print the machine name. These values may be plain, corporate-managed, or automatically generated by your operating system. The point is to connect the output back to the prompt and to notice that commands can answer practical questions about the current session.

</details>

5. Print a literal message, then try one composed command. Copy the fixed message as written; inserting arbitrary text requires choosing quotes that protect its special characters, which is beyond this first exercise.

**Bash, zsh, or WSL:**

```bash
echo 'I just used the terminal!'
echo "Today is $(date) and I am $(whoami)"
```

**PowerShell:**

```powershell
Write-Output 'I just used the terminal!'
Write-Output "Today is $(Get-Date) and I am $(whoami)"
```

<details>
<summary>Solution guidance</summary>

The first command prints the literal message without needing any replacement text. In the Bash/zsh/WSL branch, the composed command runs `date` and `whoami` first; in PowerShell, it evaluates `Get-Date` and `whoami` inside `Write-Output`. Both branches show composition while only printing information. See Microsoft's [subexpression operator documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_operators?view=powershell-7.5#subexpression-operator--) for the PowerShell form.

</details>

6. Practice recovering from an unfinished quote by intentionally creating a safe mistake.

```bash
echo "practice recovery
```

When you see a continuation prompt, press Ctrl+C instead of closing the terminal window, then confirm that your normal prompt returns.

<details>
<summary>Solution guidance</summary>

The shell should show a continuation prompt because the quote was not closed. Pressing Ctrl+C should cancel the unfinished command and return you to the normal prompt. This is a valuable practice repetition because it makes the recovery move familiar before you need it during a more stressful command.

</details>

7. Diagnose frozen terminals. This final task is unguided: there are no commands to run and no steps to follow, only evidence to read. Each transcript below is a simulated snapshot of a terminal window frozen at one moment. For each transcript, write down two things in your notes before opening the answer key: what state the shell is in (ready, running, waiting for more input, or returned to the prompt after an error), and what your next move would be.

Transcript A shows a window where someone tried to echo a sentence about release notes and then pressed Enter:

```text
yourname@your-mac ~ % echo "release notes for today
dquote>
```

Transcript B shows simulated output from a network check that keeps reporting new lines without printing a fresh prompt:

```text
yourname@your-mac ~ % ping example.com
64 bytes from 192.0.2.1: icmp_seq=1 ttl=56 time=12.3 ms
64 bytes from 192.0.2.1: icmp_seq=2 ttl=56 time=11.8 ms
64 bytes from 192.0.2.1: icmp_seq=3 ttl=56 time=12.1 ms
```

Transcript C shows what happened after a lesson command was pasted with its prompt symbol included, along with the shell's reply:

```text
yourname@your-mac ~ % $ echo 'Hello, World!'
zsh: command not found: $
yourname@your-mac ~ %
```

Transcript D: two windows from the same practice lab, both waiting for input. You need to run a practice command that should affect only the training machine, so decide which window to use and which part of the prompt told you.

```text
alex@laptop ~ $
```

```text
alex@training-vm /tmp $
```

<details>
<summary>Check your diagnosis</summary>

Transcript A shows unfinished quoted input; finish the quote or cancel and compare with the normal prompt. Transcript B shows continuing output without a returned prompt; try Ctrl+C once and check the result. Transcript C shows a copied `$` prompt symbol being treated as a command; retype `echo 'Hello, World!'` without it. In the synthetic Transcript D, choose the window labeled `alex@training-vm /tmp $`. In real sessions, confirm the connection you opened and read the user/hostname checks before changing anything; customized labels alone are not proof.

</details>

### Success Criteria

You've completed this exercise when you can demonstrate each item below without needing to close and reopen the terminal:

- [ ] Open a terminal window on your operating system.
- [ ] Identify at least one part of your prompt, such as username, hostname, directory, `$`, or `%`.
- [ ] Run `echo 'Hello, World!'` and see the output.
- [ ] Run the date/time command for your shell (`date` in Bash/zsh/WSL or `Get-Date` in PowerShell) and explain why your output differs from the example.
- [ ] Run `whoami` and `hostname` and connect the output to your current session.
- [ ] Run the combined shell-appropriate example: `echo "Today is $(date) and I am $(whoami)"` in Bash/zsh/WSL, or `Write-Output "Today is $(Get-Date) and I am $(whoami)"` in PowerShell.
- [ ] Cancel an unfinished quoted command with Ctrl+C and return to a normal prompt.
- [ ] Diagnose the shell state and next move in each frozen transcript without running any new commands.

## Sources

- [Apple termios manual: INTR and SIGINT](https://github.com/apple-oss-distributions/xnu/blob/14e3d835ecf9736db9bf15b7bc859981275e1fc0/bsd/man/man4/termios.4#L466-L478)
- [PowerShell 7.5: Normal and customized prompts](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_prompts?view=powershell-7.5)
- [PSReadLine: AcceptLine and CopyOrCancelLine](https://learn.microsoft.com/en-us/powershell/module/psreadline/about/about_psreadline_functions?view=powershell-7.5)
- [PSReadLine: Configurable continuation prompt and its default](https://learn.microsoft.com/en-us/powershell/module/psreadline/set-psreadlineoption?view=powershell-7.5#-continuationprompt)
- [zsh: Prompt expansion and parser-state markers](https://zsh.sourceforge.io/Doc/Release/Prompt-Expansion.html)
- [zsh: Interactive history expansion, including `!` inside double quotes](https://zsh.sourceforge.io/Doc/Release/Expansion.html#History-Expansion)
- [PowerShell 7.5: Single- and double-quoted strings](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_quoting_rules?view=powershell-7.5)
- [RFC 4251: The Secure Shell (SSH) Protocol Architecture](https://www.rfc-editor.org/info/rfc4251)
- [OpenSSH manual pages](https://www.openssh.org/manual.html)
- [Windows Terminal documentation](https://learn.microsoft.com/en-us/windows/terminal/)
- [Install WSL](https://learn.microsoft.com/en-us/windows/wsl/install)
- [GNU Coreutils manual: date invocation](https://www.gnu.org/software/coreutils/manual/html_node/date-invocation.html)
- [GNU Coreutils manual: whoami invocation](https://www.gnu.org/software/coreutils/manual/html_node/whoami-invocation.html)
- [GNU Coreutils manual: hostname invocation](https://www.gnu.org/software/inetutils/manual/html_node/hostname-invocation.html)
- [Bash Reference Manual: Quoting](https://www.gnu.org/software/bash/manual/html_node/Quoting.html)
- [Bash Reference Manual: Command Substitution](https://www.gnu.org/software/bash/manual/html_node/Command-Substitution.html)
- [PowerShell Get-Date cmdlet](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/get-date?view=powershell-7.5)
- [PowerShell about_Operators: Subexpression operator](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_operators?view=powershell-7.5#subexpression-operator--)
- [Kubernetes kubectl quick reference](https://kubernetes.io/docs/reference/kubectl/quick-reference/)
- [IBM History: The punched card](https://www.ibm.com/history/punched-card)
- [Graphical user interface](https://en.wikipedia.org/wiki/Graphical_user_interface)
- [DEC VT100 User Guide: Operating Information](https://vt100.net/docs/vt100-ug/chapter1.html)
- [Command line crash course](https://developer.mozilla.org/en-US/docs/Learn/Tools_and_testing/Understanding_client-side_tools/Command_line)

## Next Module

**Next Module**: [Module 0.3: First Terminal Commands](../module-0.3-first-commands/) - Learn how to move from recognizing the terminal into confident command practice.
