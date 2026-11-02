---
title: "Module 0.8: Servers and SSH"
slug: prerequisites/zero-to-terminal/module-0.8-servers-and-ssh
revision_pending: false
sidebar:
  order: 9
lab:
  id: "prereq-0.8-servers-ssh"
  url: "https://killercoda.com/kubedojo/scenario/prereq-0.8-servers-ssh"
  duration: "25 min"
  difficulty: "beginner"
  environment: "ubuntu"
---
> **Complexity**: `[MEDIUM]` - Long-form: concepts plus a hands-on connection
>
> **Time to Complete**: 80–100 minutes (read + Killercoda lab)
>
> **Prerequisites**: [Module 0.5 - Editing Files](../module-0.5-editing-files/), [Module 0.6 - Git Basics](../module-0.6-git-basics/), and [Module 0.7 - What is Networking?](../module-0.7-what-is-networking/)

---

## What You'll Be Able to Do

After this module, you will be able to:

- **Diagnose** whether a command is running locally or on a remote server by checking `hostname`, `whoami`, and `pwd`.
- **Implement** a basic SSH connection using the correct `username@host` syntax, optional port selection, and a deliberate disconnect.
- **Compare** password and SSH key authentication, including their operational tradeoffs.
- **Evaluate** server access risks before running commands that change files, logs, configuration, or service state.

## Why This Module Matters

Hypothetical scenario: you are helping a teammate investigate a service that works on a laptop but fails on the Linux machine where the rest of the team runs it. The teammate sends you a host name, a user account, and a note that says, "SSH in and check the logs." If the words local, remote, server, shell, key, and prompt blur together, the situation becomes stressful before the real troubleshooting even begins.

Servers are ordinary computers doing a particular job for other computers, but the way you operate them changes the moment they are not sitting in front of you. You do not rely on a screen, a mouse pointer, or the visual cues of your laptop desktop. You rely on a terminal session, the identity of the machine, the identity of the user, and the confidence that each command is running where you think it is running.

Later modules apply this context-checking habit to Kubernetes.

You can practice SSH by connecting to `localhost`, your own computer, if you have an authorized SSH server. Verify the host key and authenticate before opening a shell; an internet connection adds network and exposure considerations that localhost practice does not cover.

## Servers Are Computers With a Job

A server provides a service to other computers, such as web pages, files, or API responses. A laptop can provide a service too.

A server can have a CPU, memory, storage, a network interface, an operating system, and files just like your laptop.

```text
Your laptop:
  - Has a screen, keyboard, trackpad
  - Designed for ONE person to sit in front of
  - Runs a graphical interface (windows, icons, mouse)
  - You browse the web, write documents, watch videos

A server:
  - May serve users or other computers
  - May be administered through a terminal
  - It can host websites or run databases
```

When your browser opens a web page, it sends a request over the network to a server and receives a response.

Capacity, operating system, and attached devices depend on the particular machine and its job.

Pause and predict: if a production web server has no physical monitor, keyboard, or display cable attached, how can an operations engineer know whether its storage disk is completely full or its background service has crashed?

<details>
<summary>Check your prediction</summary>

Operators inspect headless servers through network-accessible remote interfaces: secure shell (SSH) sessions, automated monitoring agents, centralized log collectors, cloud management consoles, serial consoles, and infrastructure automation tooling. SSH is the foundational remote interface in this learning path because it provides direct, interactive shell access over an encrypted connection using the terminal commands you already understand.

</details>

## Local and Remote Are About Where Work Runs

Local means the command runs in your current computer's environment. A remote shell runs through a connection to a server, which may be another computer or a localhost service on the same machine. The command's context determines which files and processes it can affect.

```text
Local:  Your kitchen. You're standing in it.
Remote: A kitchen in another city. You call them on the phone to give orders.
```

When you open Terminal and type `ls`, you ask your local shell to list its current directory. After an SSH login, `ls` asks the remote shell to list its current directory. The command may fail, for example if permissions deny access.

Check context before acting. Prompts are customizable and can mislead; `hostname`, `whoami`, and `pwd` provide additional clues about the machine, account, and directory.

```bash
hostname
whoami
pwd
```

The three checks report the hostname, effective account, and current directory. Compare those clues with the expected context; names can be reused and do not replace host-key verification.

Pause and predict: you open a terminal, immediately run `hostname`, and observe your laptop name. Then you run `ssh admin@10.0.0.5`, authenticate successfully, run `hostname` again, and see a different server name. Which machine will receive a `touch practice.txt` command now, and where in the infrastructure will that file reside?

<details>
<summary>Check your prediction</summary>

The command targets the current directory of the remote shell on `10.0.0.5`. Check its exit status and inspect that directory before claiming the file was created. The terminal is local; the shell receiving this command is remote.

</details>

For each operation, ask where the work happens.

<details>
<summary>Quick check: classify these operations as local or remote.</summary>

1. Editing a photo on your laptop's desktop is local because the application and file are on the machine in front of you.
2. Using SSH to check logs on a web server in London is remote because the log command runs on that server.
3. Running `pwd` immediately after opening a terminal is local because no remote session exists yet.
4. Typing `ls` after connecting via `ssh admin@10.0.0.5` is remote because the shell is now on `10.0.0.5`.
5. Your browser requesting a page from Wikipedia is remote from the browser's point of view because a server sends the page data back.

</details>

## SSH Opens a Secure Shell on Another Machine

SSH stands for Secure Shell. It is both a protocol and a family of tools that let one computer open an authenticated, encrypted terminal session on another computer. In everyday terms, SSH is a secure phone line to a remote kitchen: you dial the remote address, prove who you are, receive a shell, and then your typed commands are carried out on the other side.

The secure part matters because server administration can cross networks you do not control. SSH provides confidentiality and integrity protections for the session when appropriate algorithms are negotiated.

SSH has two main sides. The SSH client is the program you run from your terminal, usually named `ssh`. The SSH server is the service listening on the remote machine, commonly provided by OpenSSH on Linux systems. If the remote SSH service is not installed, not running, blocked by a firewall, or listening on a different port, your client will not open the session.

The basic SSH command keeps the important parts visible:

```bash
ssh username@ip-address
```

In that shape, `ssh` is the client program, `username` is the account you want on the remote server, `@` separates the account from the host, and `ip-address` is the network location. A real private-network example might look like this:

```bash
ssh chef@192.168.1.100
```

The host can also be a DNS name instead of a numeric address. DNS names are easier for humans to remember, and they let infrastructure teams change the underlying address without forcing every operator to memorize a new number.

```bash
ssh chef@kitchen.example.com
```

The connection sequence is not complicated, but naming each step makes failures easier to diagnose. First the client contacts the remote host. Then the server presents its host identity and asks you to authenticate. After successful authentication, the server starts a shell for your remote user, and your terminal becomes the input and output window for that remote shell.

```text
1. You type: ssh chef@kitchen.example.com
2. SSH contacts the remote server
3. The server asks: "Who are you? Prove it."
4. You provide proof (password or key -- more on this below)
5. The server says: "Welcome, chef. Here's your terminal."
6. A configured shell may display a different prompt
7. Ordinary shell commands you type now run on the REMOTE server
8. Type "exit" to disconnect and return to your local terminal
```

Your prompt might change from a local-looking prompt to a remote-looking prompt. The following prompts are illustrative. Treat a prompt as a clue, not proof: shell configuration can change it, and different machines can share a hostname.

```text
yourname@your-laptop ~ $
```

```text
chef@remote-server ~ $
```

Environment variables make this easier to observe. An environment variable is a named value available to a process and its children, and shells commonly expose values such as the current user and home directory. You do not need to set these for this module; the point is to see that a remote shell has its own environment.

```bash
echo $USER
echo $HOME
```

Run the same commands locally before any SSH connection so you have a baseline. Then imagine or test the same commands after logging in as a different remote user. The variable names are the same, but their values come from the environment where the shell is actually running.

```bash
echo $USER
echo $HOME
```

Pause and predict: if you open an SSH connection to a remote server using `ssh chef@192.168.1.100` and then run `echo $USER`, what output do you expect to see printed in your terminal window, and why?

<details>
<summary>Check your prediction</summary>

It may print `chef` if the remote environment sets `USER` to that value. Environment variables can be unset or changed, so use `whoami` to check the effective account rather than relying on `USER` alone.

</details>

The default SSH port is usually 22, but real systems sometimes choose a different port because of network policy, lab setup, port forwarding, or a deliberate administrative decision. You specify that port with `-p`, and you specify a particular private key file with `-i`. Verbose mode, `-v`, prints connection details that are useful when authentication or network reachability fails.

| Option | What It Does | Example |
|--------|-------------|---------|
| `-p` | Connect on a different port (default is 22) | `ssh -p 2222 chef@server.com` |
| `-i` | Use a specific key file | `ssh -i ~/.ssh/mykey chef@server.com` |
| `-v` | Verbose mode (shows what's happening -- useful for debugging) | `ssh -v chef@server.com` |

Pause and predict: before running `ssh -v chef@server.com`, what kind of output do you expect during connection negotiation?

<details>
<summary>Check your prediction</summary>

Expect debugging messages about the client's progress. The messages depend on how far the connection gets and can help diagnose connection, authentication, and configuration problems. Treat the output as potentially sensitive.

</details>

```bash
ssh -v chef@server.com
```

The options can be combined when the server uses a non-default port and you must use a specific key. The order of `-p` and `-i` does not matter as long as they appear before the `user@host` target.

```bash
ssh -p 2222 -i ~/.ssh/work_key admin@10.0.0.5
```

## Passwords, SSH Keys, and Host Trust

Authentication is the step where the server decides whether you are allowed to become the requested remote user. The simplest method is a password: the server asks for the account password, you type it, and the server checks it. Passwords are familiar, but familiarity is not the same thing as operational safety.

```bash
ssh chef@kitchen.example.com
# Server asks: chef@kitchen.example.com's password:
# Type your password at the prompt; it may not be displayed.
```

Password input may not echo characters. Type it at the password prompt and press Enter; do not paste it into a chat window, command line, or visible note because the prompt appears frozen.

Passwords have three practical weaknesses in server operations. Humans reuse them, attackers phish them, and automation handles them badly. A deployment script that waits for someone to type a password is not automation, while a deployment script that stores a reusable password in plain text creates a new secret-management problem.

With public-key authentication, you protect a private key on the client and arrange for the server to authorize its matching public key. The client signs authentication data with the private key; the server verifies the signature with the public key. The private key itself is not sent to the server. Server policy can require additional authentication.

```text
When you connect:
Client: keeps the private key and signs authentication data.
Server: checks that the public key is authorized and verifies the signature.
The server may require another authentication step or reject the login.
```

Share the public key with systems that should allow your login, and protect the private key because someone who obtains it may be able to authenticate as you.

OpenSSH's `ssh-keygen` can generate an Ed25519 key pair. You do not need to generate a key to read this module. If you try it, choose a new file name and avoid overwriting an existing key.

```bash
ssh-keygen -t ed25519
```

The command commonly creates two files under your home directory's `.ssh` directory. `~/.ssh/id_ed25519` is the private key and must stay private. `~/.ssh/id_ed25519.pub` is the public key and can be copied to services such as GitHub or to a server's `authorized_keys` file when that server should accept your login.

```text
~/.ssh/id_ed25519      private key, kept on your computer
~/.ssh/id_ed25519.pub  public key, copied to systems that should trust you
```

OpenSSH can use `~/.ssh/authorized_keys` for an account's authorized public keys. Server configuration and file ownership and permissions affect whether a key is accepted; a matching key alone does not guarantee login.

```text
remote user home
└── .ssh
    └── authorized_keys   may list public keys authorized for this account
```

Host trust is separate from user authentication. The first time you connect to a new host, SSH may warn that the authenticity of the host has not been established and show a fingerprint. The following prompt is synthetic. It illustrates the client asking whether you trust the host key, not the server asking who you are.

```text
The authenticity of host 'localhost (127.0.0.1)' can't be established.
ED25519 key fingerprint is SHA256:AbCdEf123456...
Are you sure you want to continue connecting (yes/no)?
```

Before accepting a host key, including for `localhost`, compare its fingerprint with a value obtained through a trusted, independent channel. For a production host, the responsible administrator or an authenticated runbook may provide it. A name alone does not verify the key.

Pause and predict: which access architecture would you choose for team administration and why: sharing a single administrative account password among five engineers, or issuing five separate SSH key pairs with five distinct public keys installed on the server?

<details>
<summary>Check your prediction</summary>

Separate credentials let an administrator authorize and revoke each key independently. Whether activity can be attributed to a person also depends on account, logging, and key-management practices. A shared password must be changed for everyone when access is withdrawn.

</details>

## The Lifecycle of a Remote Session

Thinking of SSH as a lifecycle prevents two common mistakes: treating connection as the whole job and forgetting to disconnect. A session has a beginning, a working middle, and an ending. Each phase has a different question: can I reach the host, am I authenticated as the right user, am I acting in the right directory, and have I returned to local control?

```text
Your computer                          Remote server
    |                                       |
    |  --- ssh chef@server.com ---------->  |
    |                                       |  "Connection request received"
    |  <--- "Prove your identity" --------  |
    |                                       |
    |  --- sends signature or password -->  |
    |                                       |  "Identity confirmed"
    |  <--- "Welcome! Here's a shell" ----  |
    |                                       |
    |  --- ls, pwd, nano, etc. --------->  |  (commands run HERE, on the server)
    |  <--- [ BLANK 1: Predict what happens here ] --- |
    |                                       |
    |  --- [ BLANK 2: How do you disconnect? ] ------> |
    |                                       |  "Goodbye"
    |  (back to local terminal)             |
```

Pause and predict: look closely at `BLANK 1` and `BLANK 2` in the lifecycle diagram above. What does the remote server send across the network in response to your commands at `BLANK 1`, and what specific command or key sequence do you send at `BLANK 2` to terminate the session?

<details>
<summary>Check your prediction</summary>

`BLANK 1` represents output from the remote commands, displayed in your local terminal. `BLANK 2` represents the shell's `exit` command (or `Ctrl + D` to send end-of-file). After the shell exits, check that you have returned to the local session; other SSH channels can affect when the connection closes.

</details>

During the working middle of a session, every ordinary terminal command you have learned keeps its spelling but changes its target. `ls` lists remote files, `pwd` prints the remote directory, `nano` edits a remote file, and `cat /etc/os-release` reads the remote operating system information. The visible terminal window did not move, but the shell did.

```bash
ls
pwd
nano notes.txt
cat /etc/os-release
```

This is also why destructive commands deserve a context check. If you are SSH'd into a server and run `rm -rf /home/yourname/projects`, the server's path is affected, not your laptop's path. That statement is simple, but it is the line between careful operation and accidental damage.

The safe habit is to make context verification boring and automatic. After login, run a small context block, read the output, and only then continue. In a team setting, pasting that block into an incident channel can also help another person verify that you are looking at the same machine they expect.

```bash
hostname
whoami
pwd
date
```

The command `date` helps you compare the displayed time and time zone with your logs. Compare it with a trusted clock before concluding that the system clock is correct.

Connection failures are part of the lifecycle too. A timeout leaves routing, filtering, host availability, and addressing as hypotheses. A refusal suggests a missing listener or active rejection, possibly by an intermediary; it does not identify the cause alone. SSH's "Permission denied" indicates authentication failed after reaching an SSH service.

| Symptom | Likely Layer | First Beginner Check |
|---------|--------------|----------------------|
| Connection timed out | Network path or firewall | Confirm host, network, VPN, and security group rules |
| Connection refused | Listener or active rejection | Check the intended endpoint, listener and rejection policy with its owner |
| Permission denied | Authentication | Confirm username, key file, password, and account access |
| Host key warning changed | Host identity | Stop and verify whether the server was rebuilt or intercepted |

Exercise scenario: you are told to connect as `ubuntu` but you try `admin` three times and get `Permission denied`. The network may be fine. The server may be fine. The mistake may simply be the account name, and the fix is to use the username assigned by the image or administrator.

## Practicing SSH Without a Cloud Server

One practice target is `localhost`, your own computer, if an authorized SSH server is available. It lets you practice the client, server, authentication, host-key, shell, command, and disconnect flow without a separate machine. It does not test a remote network path.

Before connecting, record your local context. This gives you something to compare after login and trains the muscle memory you will later use on cloud servers and Kubernetes nodes. If you use `ssh localhost`, the hostname may be identical before and after because both sides are the same machine, so the proof is the session establishment and the authentication flow rather than a different host name.

```bash
hostname
whoami
pwd
```

If you already have an authorized local SSH server, use the same command shape as for a server elsewhere. Otherwise, read the example without connecting.

```bash
ssh localhost
```

The first connection to a new host record may display a host authenticity prompt. Verify the presented fingerprint independently before answering `yes`. The following prompt is synthetic, not a recording from a real host.

```text
The authenticity of host 'localhost (127.0.0.1)' can't be established.
ED25519 key fingerprint is SHA256:AbCdEf123456...
Are you sure you want to continue connecting (yes/no)?
```

Once connected, run a small set of harmless commands. The point is not to discover surprising files. The point is to prove that the remote shell accepts ordinary terminal commands and returns ordinary output through the encrypted session.

```bash
hostname
whoami
pwd
ls
echo "Hello from SSH!"
```

Disconnect cleanly when finished. Your prompt should return to the local shell after the remote shell exits. Because both shells run on the same machine, `hostname` alone cannot distinguish them; check the session's disconnect message as well.

```bash
exit
```

Optional server setup is only for a disposable Debian/Ubuntu VM that you own or are explicitly authorized to administer, with a console and a network restricted to the lab. Do not do this on a shared host or your everyday machine just to complete the lesson. Use the following setup commands only in that VM. Skip setup and read the examples if no authorized VM is available.

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl start ssh
```

Then test the same local connection flow. If this fails, read the error text rather than retrying blindly. An error can narrow the investigation, but it may have more than one cause.

```bash
ssh localhost
```

After disconnecting, tear down the disposable VM through the same lab system that created it, including any lab-only network exposure. Do not blindly disable or remove an existing SSH service: another user may depend on it. Practice command reading without changing services when no authorized disposable environment is available. The following transcript is synthetic.

```text
# This is what connecting to a real server would look like:
ssh yourname@192.168.1.100

# You would see:
yourname@192.168.1.100's password:

# After entering the password:
yourname@remote-server:~$

# Ordinary shell commands now run on the remote server.
# Type "exit" to disconnect.
```

With an authorized cloud server, the lifecycle is still connect, authenticate, verify context, work, and disconnect. The following transcript is synthetic: `192.0.2.24` is a reserved example address, not a connection target. Substitute only a host and account your lab owner has explicitly authorized; never probe an arbitrary public address copied from an example.

```text
# Connect to a server in the cloud
ssh ubuntu@192.0.2.24

# You'd see:
ubuntu@training-server:~$

# Now you're inside a Linux server in a data center somewhere
# Ordinary shell commands run there:
ls          # Shows files on the server
pwd         # Shows your path on the server
nano        # Opens nano on the server
cat /etc/os-release    # Shows the server's operating system

# Disconnect when done
exit
```

The same local-versus-remote discipline applies when you move on to Kubernetes.

## How SSH Thinking Transfers to Kubernetes

The beginner-friendly way to keep this straight is to describe every action in a sentence before running it. "I am running a local command that opens a remote shell on host `x` as user `y`." "I am running a local command that asks the Kubernetes API for pods in namespace `z`." If that sentence does not come out clearly, pause until the target and control surface are both clear.

## Reading Prompts, Paths, and Output Carefully

Read the output as well as the command. A prompt such as `ubuntu@ip-10-0-1-25:~$` suggests a user, host, and directory, but shell configuration controls it. Use the context checks and host-key verification before acting.

Paths deserve the same care. The path `/home/admin/app` on your laptop and `/home/admin/app` on a server can have identical spelling and entirely different contents. The path text alone does not identify the machine. You need the host context and the current session context before the path becomes meaningful.

Output can also contain hints about privilege. If `whoami` prints `root`, your commands may have broad authority on the remote machine, and caution should increase. If it prints a regular account such as `ubuntu`, some commands may require `sudo`, and some files may be intentionally unavailable. Neither result is automatically good or bad; it tells you what kind of power the current shell has.

The same careful reading helps with passwords and keys. If SSH says `Permission denied (publickey)`, check which authentication methods the server permits. `Permission denied, please try again` does not by itself establish why an attempt failed. If authentication never begins, investigate the connection or service first.

Treat copied commands as drafts, not as truth. A runbook may contain the right pattern but the wrong host for your situation, or a teammate may paste a command from a staging environment while you are investigating production. Before pressing Enter, read the username, host, port, key path, and current shell context as separate pieces of information.

That habit becomes even more important when commands include quoted strings, redirects, or file paths. A command that appends to `~/.ssh/authorized_keys` changes the remote account's allowed keys only if you are on the correct remote host and in the correct account. Run it locally by mistake and you may edit your laptop's SSH configuration instead, which solves a different problem and creates a confusing future symptom.

This is why the hands-on exercise asks for written notes. Writing the before and after values forces your brain to distinguish observation from assumption. In real operations, those notes also become a small audit trail: they show what host you entered, what user you had, where you stood in the file system, and when you returned to local control.

## When This Applies and When It Does Not

Use SSH when you need an interactive shell or a remote command on a specific machine, or a diagnostic path that a higher-level platform does not expose. A lab can make the difference between your laptop and a server concrete.

Do not treat SSH as the only way to manage servers. Configuration management, cloud-init, immutable images, Kubernetes controllers, CI pipelines, and GitOps workflows exist because repeated manual shell work does not scale well. SSH is a sharp, useful tool, but if every production change requires a person typing commands into many hosts, the process will eventually drift.

| Pattern | Use It When | Why It Works |
|---------|-------------|--------------|
| Verify context after login | You have just opened any SSH session | It supplies clues about machine, user, and directory before risky commands |
| Prefer individual SSH keys | Multiple people or systems need access | Access can be granted and revoked without sharing one secret |
| Keep manual SSH changes small | You are learning or diagnosing a narrow issue | Small changes are easier to reason about, record, and undo |
| Move repeated work into automation | The same command must run on many servers | Automation reduces drift and makes review possible before execution |

Connect, verify the target, then act. A familiar prompt alone is not enough to establish context.

## Decision Framework

Choose your remote-access method by asking what level of control you need, how often the action repeats, and how much risk comes from manual execution. A beginner SSH session is appropriate for a single machine and a learning task. A fleet operation across many machines should push you toward automation, even if SSH is still one transport underneath.

| Need | Better Starting Point | Tradeoff |
|------|-----------------------|----------|
| Learn what a remote shell feels like | `ssh localhost` or a lab VM | Safe and concrete, but not a full production model |
| Inspect one server interactively | SSH with context checks | Fast and direct, but easy to forget documentation |
| Copy a public key to allow login | SSH account setup process | Simple for small teams, but needs ownership and revocation discipline |
| Change many servers the same way | Automation or configuration management | More setup, but safer review and repeatability |

When in doubt, start with observation rather than mutation. Connect, verify context, read files, inspect service state, and write down what you see. Only after the target and problem are clear should you edit files, restart services, or delete data. This bias toward observation is one of the habits that separates calm operations from frantic guessing.

## Did You Know?

- **SSH's architecture is standardized in RFC 4251.** The RFC describes SSH as secure remote login and other secure network services over an insecure network, which is exactly the beginner mental model you need before server work becomes routine.
- **OpenSSH defaults to port 22.** An administrator can configure another port.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Sharing your private key | People confuse the private key with the public key because both files have similar names | Never share `id_ed25519`; share only `id_ed25519.pub` or another public key file |
| Forgetting you are on a remote server | The terminal window looks the same after login, so the operator relies on habit | Run `hostname`, `whoami`, and `pwd` after connecting and before changing anything |
| Typing a password into the wrong place | A password prompt may not display keystrokes | Type the password at the SSH prompt and press Enter |
| Using the wrong remote username | Cloud images and lab environments often use account names such as `ubuntu`, `ec2-user`, or `admin` | Read the lab or provider instructions and put the correct user before the `@` sign |
| Ignoring host key warnings | People treat the warning as a nuisance instead of a host identity check | Verify the fingerprint through trusted documentation or an administrator before accepting it |
| Leaving sessions open after the task | A session can remain open after the work ends | Type `exit` or press `Ctrl + D`, then confirm you are back at the local prompt |
| Automating with passwords | A script that needs a human password prompt feels easy at first but breaks unattended operation | Use key-based authentication with proper secret handling and per-system access controls |
| Panicking when a connection drops | Network interruptions make the remote state uncertain | Reconnect through an authorized path, verify context, and inspect the remote state |

## Quiz

<details>
<summary>Question 1: You SSH into a server, run `hostname`, and it shows your laptop name. What do you check before running any more commands?</summary>

Check whether the SSH connection succeeded or you are back in your local shell. A failed connection, an exited session, a localhost connection, or two machines sharing a hostname could explain the result. Check the connection output, `whoami` and `pwd`; verify the host identity independently before proceeding.

</details>

<details>
<summary>Question 2: Your teammate asks you to send your private key so they can log in quickly. What should you do instead?</summary>

You should refuse to share the private key and ask the teammate to generate their own key pair. They can send you their public key, which can then be added to the appropriate account on the server if they are authorized. Separate keys permit independent revocation; attribution also depends on logging and account practices. Sharing a private key makes it a shared credential.

</details>

<details>
<summary>Question 3: A deployment server must connect to a database server without a human typing a password. Which part of the key pair belongs on the database server?</summary>

The public key belongs on the database server, usually in the target account's `authorized_keys` file or equivalent access mechanism. The private key stays on the deployment server and must be protected as a secret. During authentication, the database server verifies that the client possesses the matching private key without receiving it. Placing the private key on the database server would spread the sensitive material to the wrong side of the trust boundary.

</details>

<details>
<summary>Question 4: You are connected to `ssh admin@10.0.0.5` and run `touch recipe.txt`. Where does the command target, and how can you check whether it succeeded?</summary>

The command targets the current directory of the remote shell at `10.0.0.5`; it may fail. Check the exit status immediately, then inspect the remote directory with `ls`. Use `hostname`, `whoami`, and `pwd` to check context. After `exit`, a local `ls` checks the local directory instead.

</details>

<details>
<summary>Question 5: Your SSH command returns "Connection refused" immediately, but the host name is correct. What layer do you investigate first?</summary>

Investigate connection establishment: confirm the intended port, server listener, and active rejection policies with the host owner. A refusal can come from a missing listener or firewall rejection, so it does not prove which device answered. This differs from SSH's "Permission denied," which indicates authentication failed after an SSH service was reached.

</details>

<details>
<summary>Question 6: You need to run the same package update on many servers. Why might manual SSH be the wrong primary method?</summary>

Manual SSH does not scale cleanly because each server becomes a separate chance for typos, missed steps, forgotten documentation, and unreviewed drift. For many servers, configuration management, image rebuilding, or another automation path gives you repeatability and review before execution. SSH may still help diagnose one failed host, but it should not be the normal way to fan out routine changes. The decision is about reducing operational variance, not about disliking SSH.

</details>

<details>
<summary>Question 7: While connecting to a production host, SSH warns that the host key changed. What is the careful response?</summary>

Stop and verify the host identity through a trusted source before accepting the changed key. A changed host key can be harmless if the server was rebuilt, but it can also indicate that you are not talking to the machine you expect. Ask for the expected fingerprint from the runbook, cloud console, or responsible administrator. Continuing blindly defeats one of SSH's core protections.

</details>

## Hands-On Exercise: SSH to Localhost

This exercise uses `localhost` so you can practice the SSH lifecycle without needing a cloud account. If your operating system does not currently run an SSH server, use the relevant setup notes in the practice section above, or read the command flow carefully and complete the written checks. The goal is not to make your laptop more complicated; the goal is to make the remote-shell model concrete.

Work slowly enough to record evidence at each stage. A good operator's notes are simple: the command used, the host observed, the user observed, the directory observed, and the command used to disconnect. Those notes make it obvious whether the session was local, remote, or a loopback connection to the same machine.

- [ ] Record your local context by running `hostname`, `whoami`, and `pwd` before any SSH command.
- [ ] Open an SSH connection to `localhost`, accepting the first-time host key only after independently verifying its fingerprint.
- [ ] Inside the SSH session, run `hostname`, `whoami`, `pwd`, `ls`, and `echo "Hello from SSH!"`.
- [ ] Disconnect with `exit`, then check the disconnect message and run `hostname` again to compare with your local notes.
- [ ] Write one sentence explaining whether the hostname changed and why that result makes sense for `localhost`.
- [ ] Build, but do not run, the command that would connect as `admin` to `10.0.0.5` on port `2222` with key file `~/.ssh/work_key`.
- [ ] Diagnose the three connection failures in Incident A by matching each error symptom to its failure layer and identifying an initial diagnostic check.
- [ ] Analyze Incident B to identify the command's reported target and the missing exit-status/file checks, without claiming unverified file creation.
- [ ] Evaluate the changed host key warning in Incident C to explain why immediate key removal is hazardous and detail the out-of-band verification procedure.

<details>
<summary>Solution guidance</summary>

Your local context block should show the machine, user, and directory before connection. The localhost SSH command is `ssh localhost`, though some systems may require a username such as `ssh yourname@localhost` depending on account setup. Inside the SSH session, the command output may look very similar because the endpoint is local, but the SSH authentication and shell lifecycle still happened. The final command for the remote example is `ssh -p 2222 -i ~/.ssh/work_key admin@10.0.0.5`.

</details>

### Diagnostic Challenge: SSH Failure Layers and Context Evidence

In this unguided challenge, examine three synthetic terminal transcripts. They are examples, not recordings of real incidents. For each, identify the failing layer or machine context, point to the evidence, and determine a safe next step.

```text
# Terminal session 1:
$ ssh -p 22 ubuntu@198.51.100.24
ssh: connect to host 198.51.100.24 port 22: Connection timed out

# Terminal session 2:
$ ssh -p 22 ubuntu@198.51.100.25
ssh: connect to host 198.51.100.25 port 22: Connection refused

# Terminal session 3:
$ ssh -i ~/.ssh/id_ed25519 devops@198.51.100.26
devops@198.51.100.26: Permission denied (publickey).
```

Examine the three recorded errors. A team lead initially claims all servers suffered the same crash. Explain what each symptom establishes, which causes remain hypotheses, and which authorized check would narrow them. Distinguish connection establishment from authentication without pretending each error identifies a unique failing device or mechanism. Optional transfer: a teammate sees the same host-key warning after a planned test-server rebuild. Explain what independent evidence you would obtain before changing `known_hosts`, and what you would do if the fingerprints differ.
<details><summary>Hint 1</summary>Decide whether each message occurs before or during authentication.</details><details><summary>Hint 2</summary>Separate what the message reports from explanations that still need evidence.</details><details><summary>Hint 3</summary>For session 3, consider whether `-i` proves which identity was offered; verbose output can help you check.</details>

<details>
<summary>Diagnosis and layer analysis for Incident A</summary>

**Session 1 (`198.51.100.24` - `Connection timed out`):**
- **Observed Layer:** Connection establishment timed out before SSH authentication.
- **Evidence and Mechanism:** The client did not establish the connection within its timeout. Filtering, routing trouble, an unavailable host, or loss are hypotheses; the message alone does not show packet captures or identify which device caused the failure.
- **First Diagnostic Check:** Check cloud provider security group rules to confirm inbound TCP port 22 is permitted from your client IP, verify VPN connectivity if connecting to private subnets, and check instance health and power status in the cloud management console.

**Session 2 (`198.51.100.25` - `Connection refused`):**
- **Observed Layer:** The connection to port 22 was actively refused before SSH authentication.
- **Evidence and Mechanism:** A missing listener or active rejection by a firewall could explain the refusal. The error alone does not identify the rejecting device or prove that the destination operating system was reached.
- **First Diagnostic Check:** Confirm the intended host and port with its owner, then inspect listener state and rejection policies through an authorized management path. A service-status check on that intended host tests one hypothesis; it does not prove that host produced the refusal.

**Session 3 (`198.51.100.26` - `Permission denied (publickey)`):**
- **Failing Layer:** Authentication and authorization layer.
- **Evidence and Mechanism:** The client reached SSH authentication, but public-key authentication did not succeed. The `-i` argument selects an identity file; this transcript does not show whether that key was usable or offered, and configured identities or an agent may also contribute keys. It does not establish the server's authorization-file contents.
- **First Diagnostic Check:** On the authorized host only, use verbose client output to inspect identity selection and actual offers, verify the username, and ask the administrator to check authorized keys and access policy. Treat debug output as potentially sensitive; do not blindly append keys or change server files from this error alone.

</details>

```text
laptop-user@workstation:~$ ssh deployer@worker-prod-04
deployer@worker-prod-04:~$ whoami
deployer
deployer@worker-prod-04:~$ hostname
worker-prod-04
deployer@worker-prod-04:~$ pwd
/var/www/site
deployer@worker-prod-04:~$ git pull origin main
Updating a1b2c3d..e4f5g6h
Fast-forward
 app.js | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
deployer@worker-prod-04:~$ touch maintenance.flag
deployer@worker-prod-04:~$ exit
logout
Connection to 192.0.2.85 closed.
laptop-user@workstation:~$ ls -la maintenance.flag
ls: cannot access 'maintenance.flag': No such file or directory
```

An engineer intended to test a maintenance flag script locally, ran the sequence above, disconnected, and then grew alarmed when `ls -la maintenance.flag` failed on their workstation. What does the transcript establish about the `touch` command's target, and which checks are missing before you can declare success? Cite the session-boundary evidence and evaluate the operational risk introduced by confusing local and remote context.

<details>
<summary>Diagnosis and context analysis for Incident B</summary>

**Did the command fail?**
No error is shown, but the transcript does not include an exit-status check or a remote file listing. Success is plausible, not verified; an immediate `echo $?` after `touch` and a remote `ls -l maintenance.flag` would supply the missing evidence.

**Which machine holds `maintenance.flag`?**
If `touch` succeeded, its target was `/var/www/site/maintenance.flag` on the remote server `worker-prod-04`. The local failed listing does not verify the remote file's existence; confirm it through an authorized read-only check before claiming success.

**Transcript Evidence for Session Boundaries:**
- The prompt `laptop-user@workstation:~$ ssh deployer@worker-prod-04` initiated a remote SSH session.
- In this illustrative session, `whoami` returned `deployer`, `hostname` returned `worker-prod-04`, and `pwd` returned `/var/www/site`. These outputs identify the reported user, host, and directory within the session; they do not replace SSH host-identity verification.
- The command `touch maintenance.flag` executed while the shell was still active on `worker-prod-04`.
- The command `exit` closed the remote session, verified by `logout` and `Connection to 192.0.2.85 closed.`, returning the prompt to `laptop-user@workstation:~$`.
- The final command `ls -la maintenance.flag` ran in the local workstation directory and found no file there; it says nothing about the remote path.

**Operational Risk:**
The engineer intended a local test but targeted a production path. If `touch` succeeded there, an application configured to treat that flag as maintenance mode could change behavior. The transcript alone proves neither file creation nor an outage. Assuming failure from the later local listing could lead to repeated writes before the remote state is checked.

</details>

```text
$ ssh admin@prod-api.example.com
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!
Someone could be eavesdropping on you right now (man-in-the-middle attack)!
It is also possible that a host key has just been changed.
The fingerprint for the ED25519 key sent by the remote host is
SHA256:uR9v8Kx3Jb5Pq1Lm9N0w2Z4y7Xa6Ce8Gh0Ik2Mo4Qs8.
Please contact your system administrator.
Add correct host key in /home/user/.ssh/known_hosts to get rid of this message.
Offending ED25519 key in /home/user/.ssh/known_hosts:42
Host key verification failed.
```

While investigating an alert on an API server, an engineer encounters the security warning displayed above. A forum post suggests immediately running `ssh-keygen -R prod-api.example.com` to remove line 42 from `known_hosts` so the connection can proceed without warnings. Why is deleting this host key record without out-of-band verification hazardous, which security layer is raising this alert, and what exact procedure must the engineer follow before connecting?

<details>
<summary>Diagnosis and host-trust analysis for Incident C</summary>

**Security Layer and Mechanism:**
The client compares the presented public host key with the key recorded in `~/.ssh/known_hosts`. In this synthetic example the keys differ and host-key verification fails. The warning does not establish why the key changed.

**Hazard of Immediate Key Removal:**
The mismatch may indicate interception or a legitimate change. Removing the stored host-key record before verification discards the comparison that produced the warning; blindly accepting a replacement can expose the session to an impostor.

**Benign Causes vs Attack Scenarios:**
A rebuild or a different machine at the same address may explain a change. Neither explanation is established by the warning; verify the expected key independently.

**Required Verification Procedure:**
1. Stop connection attempts immediately; do not delete line 42 from `~/.ssh/known_hosts`.
2. Obtain the expected host-key fingerprint from the administrator through an authenticated, independent channel.
3. Compare the verified fingerprint against the fingerprint reported in the warning banner (`SHA256:uR9v8Kx3Jb5Pq1Lm9N0w2Z4y7Xa6Ce8Gh0Ik2Mo4Qs8`).
4. If the fingerprints match and the change is authorized, remove the obsolete host record using `ssh-keygen -R prod-api.example.com` and reconnect, verifying the fingerprint prompt before typing `yes`. If they do not match, stop and escalate the unexplained mismatch for investigation.

</details>

<details>
<summary>Success criteria</summary>

Your notes should show before/inside/after context checks and a clean disconnect for the guided localhost exercise. For Incident A, distinguish connection symptoms from authentication failure and propose justified checks. For Incident B, identify the reported command target and missing success/file evidence. For Incident C, require out-of-band host-key verification before changing `known_hosts`. Success means keeping observations and hypotheses separate before choosing an action.

</details>

## Sources

- [OpenSSH client configuration: identity selection](https://man.openbsd.org/ssh_config.5)
- [RFC 5737: IPv4 documentation addresses](https://www.rfc-editor.org/rfc/rfc5737.html)
- [GitHub Docs Source: Generating a New SSH Key](https://github.com/github/docs/blob/main/content/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent.md)
- [RFC 4251: The Secure Shell (SSH) Protocol Architecture](https://www.rfc-editor.org/rfc/rfc4251)
- [RFC 4250: The Secure Shell (SSH) Protocol Assigned Numbers](https://www.rfc-editor.org/rfc/rfc4250)
- [IANA Service Name and Transport Protocol Port Number Registry](https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml)
- [Portable OpenSSH](https://github.com/openssh/openssh-portable)
- [OpenSSH Manual Page: ssh](https://man.openbsd.org/ssh)
- [OpenSSH Manual Page: ssh-keygen](https://man.openbsd.org/ssh-keygen)
- [OpenSSH Manual Page: sshd](https://man.openbsd.org/sshd)
- [OpenSSH Manual Page: authorized_keys](https://man.openbsd.org/sshd#AUTHORIZED_KEYS_FILE_FORMAT)
- [Ubuntu Server Documentation: OpenSSH Server](https://documentation.ubuntu.com/server/how-to/security/openssh-server/)
- [Apple macOS User Guide: Allow a remote computer to access your Mac](https://support.apple.com/guide/mac-help/allow-a-remote-computer-to-access-your-mac-mchlp1066/mac)
- [Microsoft Learn: OpenSSH for Windows overview](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_overview)
- [Kubernetes Documentation: Nodes](https://kubernetes.io/docs/concepts/architecture/nodes/)

## Next Module

**Next Module**: [Module 0.9: Software and Packages](../module-0.9-software-and-packages/) - Learn how software gets installed on your computer, what package managers are, and how to install tools from the terminal.
