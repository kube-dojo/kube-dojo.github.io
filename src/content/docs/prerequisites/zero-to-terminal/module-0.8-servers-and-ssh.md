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
> **Complexity**: `[QUICK]` - Concepts and a hands-on connection
>
> **Time to Complete**: 80–100 minutes (read + Killercoda lab)
>
> **Prerequisites**: [Module 0.5 - Editing Files](../module-0.5-editing-files/)

---

## What You'll Be Able to Do

After this module, you will be able to:

- **Diagnose** whether a command is running locally or on a remote server by checking `hostname`, `whoami`, and `pwd`.
- **Implement** a basic SSH connection using the correct `username@host` syntax, optional port selection, and a deliberate disconnect.
- **Compare** password authentication with SSH key authentication and choose the safer method for human and automated access.
- **Evaluate** server access risks before running commands that change files, logs, configuration, or service state.

## Why This Module Matters

Hypothetical scenario: you are helping a teammate investigate a service that works on a laptop but fails on the Linux machine where the rest of the team runs it. The teammate sends you a host name, a user account, and a note that says, "SSH in and check the logs." If the words local, remote, server, shell, key, and prompt blur together, the situation becomes stressful before the real troubleshooting even begins.

Servers are ordinary computers doing a particular job for other computers, but the way you operate them changes the moment they are not sitting in front of you. You do not rely on a screen, a mouse pointer, or the visual cues of your laptop desktop. You rely on a terminal session, the identity of the machine, the identity of the user, and the confidence that each command is running where you think it is running.

Kubernetes makes this foundation more important, not less. A Kubernetes 1.35 cluster is built from servers called nodes, and even when `kubectl` becomes your main cluster interface, you still need the mental model that a command has a location, a user, and a blast radius. This module gives you that model before the command surface becomes larger.

You will practice SSH in the safest possible way by connecting back to `localhost`, which means your own computer. That may sound artificial, but the protocol steps are the same as connecting to a cloud VM across the internet: the client contacts a host, the host asks for proof, the shell opens, commands run on the other side of the connection, and you disconnect when the work is finished.

## Servers Are Computers With a Job

A server is not a mystical machine category. It is a computer assigned to serve something to other computers, such as web pages, database responses, files, logs, build artifacts, or API calls. Your laptop is optimized for one person sitting at it, while a server is optimized for being reachable over a network and doing repeatable work for many clients.

The original beginner distinction is worth preserving because it prevents a lot of false intimidation. A server can have a CPU, memory, storage, a network card, fans, an operating system, and files just like your laptop. The difference is usually packaging, reliability expectations, remote management, and the narrowness of its job.

```text
Your laptop:
  - Has a screen, keyboard, trackpad
  - Designed for ONE person to sit in front of
  - Runs a graphical interface (windows, icons, mouse)
  - You browse the web, write documents, watch videos

A server:
  - Often has NO screen, keyboard, or mouse
  - Designed to serve MANY users/computers simultaneously
  - Usually runs ONLY a terminal interface (no desktop)
  - It hosts websites, runs databases, processes data
```

The kitchen analogy still works because it separates the worker from the customer. Your laptop is like a home kitchen where the cook and diner are usually the same person. A server is like a restaurant kitchen: customers do not stand next to the stove, but they still receive food because a clear request path exists between the dining room and the kitchen.

When your browser opens a web page, it behaves like the customer in that dining room. It sends a request over the network to a server, the server processes that request, and the server sends a response back. You do not need to see the server's screen because the useful work is already happening through the request and response path.

Under the hood, the comparison is practical rather than magical. The following table keeps the original shape of the module while making the operational meaning clearer: more cores and memory usually help with many simultaneous requests, less attached display hardware reduces waste, and Linux is common because it is scriptable, stable, and deeply integrated with server tooling.

| Component | Your Laptop | A Typical Server |
|-----------|-------------|-----------------|
| CPU | 4-8 cores | 16-128 cores |
| RAM | 8-32 GB | 64-512 GB |
| Storage | 256 GB - 2 TB | 1 TB - 100 TB+ |
| Screen | Yes | Usually no |
| Keyboard | Yes | Usually no |
| Operating System | macOS/Windows | Linux (almost always) |
| Purpose | One person, many tasks | Many clients, specific tasks |

The table does not mean a laptop can never serve traffic or a server can never have a keyboard. It means the design center is different. A laptop assumes a nearby person, while a server assumes a network client and a remote operator.

The beginner trap is thinking remote machines are less real because they are not visible. They are very real. If you create a file on a server, disk space is consumed on that server; if you delete a directory on a server, that directory is gone from the server; if you restart a process on a server, users who depend on that process may notice.

Pause and predict: if a web server has no monitor attached, how can anyone know whether its disk is full or its service is running? The answer is that operators ask through remote interfaces: SSH sessions, monitoring systems, logs, cloud consoles, serial consoles, and automation tools. SSH is the first remote interface in this beginner path because it feels like the terminal you already know.

## Local and Remote Are About Where Work Runs

Local means the command runs on the computer in front of you. Remote means the command runs on another computer reached over a network. The same command can be harmless in one place and risky in another because the command's location decides which files, processes, users, and network interfaces it touches.

```text
Local:  Your kitchen. You're standing in it.
Remote: A kitchen in another city. You call them on the phone to give orders.
```

When you open Terminal and type `ls`, the shell on your own computer lists files from your own current directory. When you connect to a server with SSH and then type `ls`, the shell on the server lists files from the server's current directory. The letters on your keyboard are local, but the command execution after login is remote.

This is why experienced engineers build a habit of checking context before acting. The prompt may show a user and host, but prompts are customizable and sometimes misleading. Commands such as `hostname`, `whoami`, and `pwd` give you independent evidence about the machine, account, and directory you are currently controlling.

```bash
hostname
whoami
pwd
```

The three checks answer three separate questions. `hostname` answers "which machine is executing this command?" `whoami` answers "which account is executing this command?" `pwd` answers "where in the file system am I standing?" Together they reduce the chance that you apply a fix to your laptop while believing you are on the server, or worse, apply a destructive change to production while believing you are in a practice environment.

Pause and predict: you open a terminal, immediately run `hostname`, and see your laptop name. Then you run `ssh admin@10.0.0.5`, authenticate successfully, run `hostname` again, and see a different name. Which machine will receive a `touch practice.txt` command now? The file is created on the remote machine because the active shell after SSH login belongs to that remote host.

The following quick classification exercise is retained from the original module because it trains the most important beginner reflex. Do not answer by looking for a fancy command; answer by asking where the work happens.

<details>
<summary>Quick check: classify these operations as local or remote.</summary>

1. Editing a photo on your laptop's desktop is local because the application and file are on the machine in front of you.
2. Using SSH to check logs on a web server in London is remote because the log command runs on that server.
3. Running `pwd` immediately after opening a terminal is local because no remote session exists yet.
4. Typing `ls` after connecting via `ssh admin@10.0.0.5` is remote because the shell is now on `10.0.0.5`.
5. Your browser requesting a page from Wikipedia is remote from the browser's point of view because a server sends the page data back.

</details>

Exercise scenario: you are documenting a deployment process and want the first line of every troubleshooting session to prove context. A strong runbook does not start with "restart the service." It starts with "connect to the correct host, record `hostname`, record `whoami`, record `pwd`, then inspect the service." That order may feel slow, but it protects the system before the commands become powerful.

## SSH Opens a Secure Shell on Another Machine

SSH stands for Secure Shell. It is both a protocol and a family of tools that let one computer open an authenticated, encrypted terminal session on another computer. In everyday terms, SSH is a secure phone line to a remote kitchen: you dial the remote address, prove who you are, receive a shell, and then your typed commands are carried out on the other side.

The secure part matters because server administration often crosses networks you do not fully control. Without encryption, someone positioned on the network could read commands, outputs, passwords, or sensitive file contents. SSH protects confidentiality and integrity for the session, which is why it replaced older plaintext remote-login habits for normal shell administration.

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
6. Your prompt changes to show the remote server's name
7. Every command you type now runs on the REMOTE server
8. Type "exit" to disconnect and return to your local terminal
```

Your prompt might change from a local-looking prompt to a remote-looking prompt. Treat that as a helpful clue, not as the only proof. A prompt is text generated by a shell configuration, while `hostname` asks the operating system directly.

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

Pause and predict: if you connect to a remote server using `ssh chef@192.168.1.100` and then run `echo $USER`, what output do you expect? It should print `chef`, because the command runs inside the remote session as the remote account you authenticated as. If you expected your laptop username, you were thinking about where your keyboard is, not where the shell is.

The default SSH port is usually 22, but real systems sometimes choose a different port because of network policy, lab setup, port forwarding, or a deliberate administrative decision. You specify that port with `-p`, and you specify a particular private key file with `-i`. Verbose mode, `-v`, prints connection details that are useful when authentication or network reachability fails.

| Option | What It Does | Example |
|--------|-------------|---------|
| `-p` | Connect on a different port (default is 22) | `ssh -p 2222 chef@server.com` |
| `-i` | Use a specific key file | `ssh -i ~/.ssh/mykey chef@server.com` |
| `-v` | Verbose mode (shows what's happening -- useful for debugging) | `ssh -v chef@server.com` |

Before running this, what output do you expect from verbose mode? You should expect more diagnostic text before login succeeds or fails, not a different kind of shell. Verbose output is for explanation, not for changing the remote machine.

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
# You type your password (it won't show on screen -- that's normal)
```

SSH intentionally hides password input. The absence of dots, asterisks, or moving characters is not a bug; it prevents someone nearby from learning password length. The correct response is to type the password carefully and press Enter, not to paste it into a chat window, command line, or visible note because you think the prompt is frozen.

Passwords have three practical weaknesses in server operations. Humans reuse them, attackers phish them, and automation handles them badly. A deployment script that waits for someone to type a password is not automation, while a deployment script that stores a reusable password in plain text creates a new secret-management problem.

SSH keys solve a different version of the identity problem. Instead of sending a shared secret to the server, you keep a private key on your machine and place the matching public key on servers that should trust you. During login, the server can verify that your client possesses the private key without receiving the private key itself.

```text
You have a KEY (private key) -- kept on your computer, never shared.
The server has a LOCK (public key) -- it knows what key fits.

When you connect:
1. You present your key
2. The server checks: "Does this key fit my lock?"
3. If yes: "Come in!" (no password needed)
4. If no: "Access denied."
```

The original house-key analogy is useful as long as you keep the sharing rule exact. Your private key is the house key, and your public key is the lock information that servers can store. You may share the public key with systems that should allow your login, but you never share the private key because anyone who possesses it may be able to authenticate as you.

Generating an Ed25519 key is usually done with `ssh-keygen`. You do not need to generate a new key just to read this module, but you should recognize the command and the default file names it creates. Ed25519 is widely recommended for modern SSH key use because it is compact, fast, and supported by current OpenSSH releases.

```bash
ssh-keygen -t ed25519
```

The command commonly creates two files under your home directory's `.ssh` directory. `~/.ssh/id_ed25519` is the private key and must stay private. `~/.ssh/id_ed25519.pub` is the public key and can be copied to services such as GitHub or to a server's `authorized_keys` file when that server should accept your login.

```text
~/.ssh/id_ed25519      private key, kept on your computer
~/.ssh/id_ed25519.pub  public key, copied to systems that should trust you
```

On many Linux servers, the public keys allowed for an account live in `~/.ssh/authorized_keys` for that account. That file is not magic either; it is a list the SSH server checks during authentication. If your public key is present and file permissions allow the SSH service to read it safely, your matching private key can prove your identity.

```text
remote user home
└── .ssh
    └── authorized_keys   accepts matching private keys for this account
```

Host trust is separate from user authentication. The first time you connect to a new host, SSH may warn that the authenticity of the host has not been established and show a fingerprint. That is the client asking, "Am I really talking to the server I think I am talking to?" not the server asking who you are.

```text
The authenticity of host 'localhost (127.0.0.1)' can't be established.
ED25519 key fingerprint is SHA256:AbCdEf123456...
Are you sure you want to continue connecting (yes/no)?
```

For a local practice connection to `localhost`, accepting the prompt is reasonable because the host is your own machine. For a production server, you should verify the fingerprint through a trusted source such as cloud console metadata, a team runbook, or an administrator-provided value. Blindly accepting changed host keys trains the exact habit SSH is trying to prevent.

Which approach would you choose here and why: a shared password for five teammates, or five separate SSH key pairs with five separate public keys on the server? The separate-key approach is better because each person can be granted, audited, and removed independently. Shared credentials make revocation and accountability harder than they need to be.

## The Lifecycle of a Remote Session

Thinking of SSH as a lifecycle prevents two common mistakes: treating connection as the whole job and forgetting to disconnect. A session has a beginning, a working middle, and an ending. Each phase has a different question: can I reach the host, am I authenticated as the right user, am I acting in the right directory, and have I returned to local control?

```text
Your computer                          Remote server
    |                                       |
    |  --- ssh chef@server.com ---------->  |
    |                                       |  "Connection request received"
    |  <--- "Prove your identity" --------  |
    |                                       |
    |  --- sends key/password ----------->  |
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

The first blank is command output, because the server sends back the result of the command you ran remotely. The second blank is `exit`, because that command closes the remote shell and returns you to your local terminal. `Ctrl + D` often does the same thing because it sends end-of-input to the shell, but `exit` is explicit and readable in teaching examples.

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

The command `date` is included because time matters in troubleshooting. If logs are in UTC but your laptop clock displays local time, you may search the wrong window. The date output also confirms that the remote system clock is not wildly wrong, which can affect certificates, authentication, scheduled jobs, and log ordering.

Connection failures are part of the lifecycle too. "Connection timed out" often points to routing, firewall, host-down, or wrong-address problems. "Connection refused" often means the host answered but no SSH service is listening on that address and port. "Permission denied" usually means you reached the SSH service but authentication failed.

| Symptom | Likely Layer | First Beginner Check |
|---------|--------------|----------------------|
| Connection timed out | Network path or firewall | Confirm host, network, VPN, and security group rules |
| Connection refused | SSH service or port | Confirm the server is listening on the expected port |
| Permission denied | Authentication | Confirm username, key file, password, and account access |
| Host key warning changed | Host identity | Stop and verify whether the server was rebuilt or intercepted |

Exercise scenario: you are told to connect as `ubuntu` but you try `admin` three times and get `Permission denied`. The network may be fine. The server may be fine. The mistake may simply be the account name, and the fix is to use the username assigned by the image or administrator.

## Practicing SSH Without a Cloud Server

The safest first practice target is `localhost`, which is a standard name for your own machine. Connecting to `localhost` through SSH may feel like calling yourself on the phone, but it tests the same client, server, authentication, host-key, shell, command, and disconnect flow. The only difference is that the remote host happens to be the same physical computer.

Before connecting, record your local context. This gives you something to compare after login and trains the muscle memory you will later use on cloud servers and Kubernetes nodes. If you use `ssh localhost`, the hostname may be identical before and after because both sides are the same machine, so the proof is the session establishment and the authentication flow rather than a different host name.

```bash
hostname
whoami
pwd
```

On macOS, you may need to enable Remote Login before an SSH server accepts local connections. Open System Settings, go to General, then Sharing, and turn on Remote Login. After that, the command shape is the same as it would be for a server elsewhere.

```bash
ssh localhost
```

The first connection to a new host record often displays a host authenticity prompt. For this local exercise, answer `yes` when you intentionally connected to your own machine. Then enter your Mac password if prompted; the password characters will not appear while you type.

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

Disconnect cleanly when finished. Your prompt should return to the local shell after the remote shell exits. If you are unsure whether you are back, run `hostname` again and compare it with your notes.

```bash
exit
```

On Linux, the SSH client may already be installed, but the SSH server varies by distribution and image. Many desktop systems do not expose SSH until you install and start OpenSSH Server. On Debian or Ubuntu systems where OpenSSH Server is missing or stopped, the following commands install it and start it immediately.

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
```

Then test the same local connection flow. If this fails, read the error text rather than retrying blindly. A missing service, blocked port, or wrong account name produces a different symptom than a wrong password.

```bash
ssh localhost
```

On Windows, the exact localhost setup depends on whether the OpenSSH Server optional feature is installed and running. For this beginner module, it is acceptable to practice command reading without changing Windows services. The important part is recognizing the shape of a real connection and the prompt that follows successful login.

```text
# This is what connecting to a real server would look like:
ssh yourname@192.168.1.100

# You would see:
yourname@192.168.1.100's password:

# After entering the password:
yourname@remote-server:~$

# Now every command runs on the remote server.
# Type "exit" to disconnect.
```

With a real cloud server, the experience looks almost identical. The address might be public, the username might come from the image vendor, and key-based authentication may be required by default, but the lifecycle is still connect, authenticate, verify context, work, and disconnect.

```bash
# Connect to a server in the cloud
ssh ubuntu@54.123.45.67

# You'd see:
ubuntu@ip-54-123-45-67:~$

# Now you're inside a Linux server in a data center somewhere
# Every command runs there:
ls          # Shows files on the server
pwd         # Shows your path on the server
nano        # Opens nano on the server
cat /etc/os-release    # Shows the server's operating system

# Disconnect when done
exit
```

Kubernetes does not remove this knowledge. In many managed clusters you rarely SSH to nodes, and that is usually a good thing because the cluster API should be the normal control surface. In learning labs, bare-metal clusters, emergency diagnostics, and some self-managed environments, SSH still appears, and the same local-versus-remote discipline protects you from misreading the machine you are operating.

## How SSH Thinking Transfers to Kubernetes

Kubernetes introduces new nouns, but it does not repeal the old ones. A node is still a server, a process is still running somewhere, a file path still belongs to a particular machine or container, and an operator still needs to know the target before acting. The difference is that Kubernetes adds an API layer that can schedule work across many servers, so the target may be selected indirectly rather than by opening a shell to one host.

In Kubernetes 1.35, you will usually inspect cluster resources through `kubectl` rather than by logging into every node. That is a higher-level habit and it is the right default for most workload questions. Still, the SSH mental model helps because `kubectl` has its own version of local versus remote: the command runs locally, the API request goes to the cluster, and the effect happens on resources managed by remote servers.

Think about the chain from your keyboard to a workload. Your terminal sends a command to a local program. That program sends an authenticated request to the Kubernetes API server. The control plane stores or reads desired state, and worker nodes run the containers that satisfy that state. If you understand where each part runs, you will be less likely to blame your laptop for a node problem or blame a node for a local configuration problem.

The same context habit becomes more specific later. With SSH you ask, "Which host, which user, which directory?" With Kubernetes you ask, "Which cluster, which namespace, which resource, which container?" The habit is identical even though the commands are different. You prove the target first because a correct command aimed at the wrong target is still a bad operation.

For example, a future troubleshooting flow may start with `kubectl get pods` to identify a failing workload, then `kubectl logs` to read its container output, then `kubectl describe node` to inspect the node where it is scheduled. Most of that work should not require SSH. If the node itself has a disk, network, or system-service issue beyond what the cluster API explains, an operator may then open an SSH session to that specific node and use the same context checks from this module.

The important lesson is not "SSH into everything." The important lesson is "know which control surface you are using." SSH controls a machine shell. `kubectl` controls Kubernetes resources through the Kubernetes API. A cloud console controls provider resources. Mixing those surfaces without naming them leads to confusion because each one has different permissions, audit trails, failure modes, and recovery paths.

Exercise scenario: a pod fails because it is unable to write to a mounted volume, and a learner immediately wants to SSH to the worker node. A better first move is to inspect the pod events, volume configuration, namespace, and storage class through the Kubernetes API. SSH becomes reasonable only if the evidence points to a node-level condition such as a full disk, broken mount, or failed system service that the higher-level tools do not resolve.

This transfer also explains why senior engineers can sound cautious about direct node access. Direct SSH can be necessary, but it bypasses some of the review and intent captured in Kubernetes resource definitions. If a manual node change fixes the symptom but never becomes documented configuration, the next node rebuild may erase it, and the team may rediscover the same problem later.

The beginner-friendly way to keep this straight is to describe every action in a sentence before running it. "I am running a local command that opens a remote shell on host `x` as user `y`." "I am running a local command that asks the Kubernetes API for pods in namespace `z`." If that sentence does not come out clearly, pause until the target and control surface are both clear.

## Reading Prompts, Paths, and Output Carefully

Remote work rewards slow reading. Many mistakes happen because the operator reads only the command they intended to type, not the output the system actually returned. SSH output often tells you whether the failure is network reachability, host trust, authentication, or remote shell startup, but only if you pause long enough to classify the message.

Begin with the prompt, but do not stop there. A prompt such as `ubuntu@ip-10-0-1-25:~$` suggests a user, host, and directory, yet it is still a convention created by shell configuration. The stronger evidence comes from commands whose purpose is to ask the system directly. That is why this module repeats `hostname`, `whoami`, and `pwd` until they feel ordinary.

Paths deserve the same care. The path `/home/admin/app` on your laptop and `/home/admin/app` on a server can have identical spelling and entirely different contents. The path text alone does not identify the machine. You need the host context and the current session context before the path becomes meaningful.

Output can also contain hints about privilege. If `whoami` prints `root`, your commands may have broad authority on the remote machine, and caution should increase. If it prints a regular account such as `ubuntu`, some commands may require `sudo`, and some files may be intentionally unavailable. Neither result is automatically good or bad; it tells you what kind of power the current shell has.

The same careful reading helps with passwords and keys. If SSH says `Permission denied (publickey)`, the server may not accept password login at all, and typing your normal account password repeatedly will not help. If it says `Permission denied, please try again`, password authentication may be allowed but the value is wrong. If it never reaches an authentication message, you may be dealing with a network or service problem instead.

Treat copied commands as drafts, not as truth. A runbook may contain the right pattern but the wrong host for your situation, or a teammate may paste a command from a staging environment while you are investigating production. Before pressing Enter, read the username, host, port, key path, and current shell context as separate pieces of information.

That habit becomes even more important when commands include quoted strings, redirects, or file paths. A command that appends to `~/.ssh/authorized_keys` changes the remote account's allowed keys only if you are on the correct remote host and in the correct account. Run it locally by mistake and you may edit your laptop's SSH configuration instead, which solves a different problem and creates a confusing future symptom.

This is why the hands-on exercise asks for written notes. Writing the before and after values forces your brain to distinguish observation from assumption. In real operations, those notes also become a small audit trail: they show what host you entered, what user you had, where you stood in the file system, and when you returned to local control.

## When This Applies and When It Does Not

Use SSH when you need an interactive shell on a specific machine, a small remote command, secure file transfer through related tools, or a direct diagnostic path that the higher-level platform does not expose. It is especially useful in labs because it lets you feel the difference between your laptop and a server without introducing a full automation system too early.

Do not treat SSH as the only way to manage servers. Configuration management, cloud-init, immutable images, Kubernetes controllers, CI pipelines, and GitOps workflows exist because repeated manual shell work does not scale well. SSH is a sharp, useful tool, but if every production change requires a person typing commands into many hosts, the process will eventually drift.

| Pattern | Use It When | Why It Works |
|---------|-------------|--------------|
| Verify context after login | You have just opened any SSH session | It proves machine, user, and directory before risky commands |
| Prefer individual SSH keys | Multiple people or systems need access | Access can be granted and revoked without sharing one secret |
| Keep manual SSH changes small | You are learning or diagnosing a narrow issue | Small changes are easier to reason about, record, and undo |
| Move repeated work into automation | The same command must run on many servers | Automation reduces drift and makes review possible before execution |

The strongest beginner pattern is "connect, verify, then act." It sounds almost too simple, but it generalizes. You will later use the same idea with Kubernetes contexts and namespaces: select the target, prove the target, then run the command. The technology changes, but the safety pattern remains recognizable.

The matching anti-pattern is "prompt blindness." Prompt blindness happens when the terminal looks familiar enough that you stop seeing where it points. Teams fall into it because local and remote shells both accept the same command language, and because productive operators move quickly. The fix is not fear; the fix is a tiny verification ritual that survives speed.

## Decision Framework

Choose your remote-access method by asking what level of control you need, how often the action repeats, and how much risk comes from manual execution. A beginner SSH session is appropriate for a single machine and a learning task. A fleet operation across many machines should push you toward automation, even if SSH is still one transport underneath.

| Need | Better Starting Point | Tradeoff |
|------|-----------------------|----------|
| Learn what a remote shell feels like | `ssh localhost` or a lab VM | Safe and concrete, but not a full production model |
| Inspect one server interactively | SSH with context checks | Fast and direct, but easy to forget documentation |
| Copy a public key to allow login | SSH account setup process | Simple for small teams, but needs ownership and revocation discipline |
| Change many servers the same way | Automation or configuration management | More setup, but safer review and repeatability |
| Work with Kubernetes workloads | Kubernetes API through `kubectl` | Higher-level and auditable, but node-level issues may still need SSH |

The decision also depends on whether the server is cattle or a pet. A pet server is lovingly modified in place, which can be understandable in a small lab but dangerous at scale. A cattle-style server is replaceable from configuration, and direct SSH becomes a diagnostic escape hatch rather than the normal way to make changes.

When in doubt, start with observation rather than mutation. Connect, verify context, read files, inspect service state, and write down what you see. Only after the target and problem are clear should you edit files, restart services, or delete data. This bias toward observation is one of the habits that separates calm operations from frantic guessing.

## Did You Know?

- **SSH's architecture is standardized in RFC 4251.** The RFC describes SSH as secure remote login and other secure network services over an insecure network, which is exactly the beginner mental model you need before server work becomes routine.
- **Port 22 is the registered default SSH port.** The IANA service-name registry assigns `ssh` to TCP port 22, which is why examples and firewall rules often mention 22 unless an administrator deliberately chooses another port.
- **OpenSSH first appeared in 1999 as part of the OpenBSD project.** It became the common SSH implementation on Unix-like systems because it provided a free, practical suite for remote login, remote command execution, and related secure operations.
- **Kubernetes 1.35 still runs on servers called nodes.** Even when you use the Kubernetes API instead of SSH for normal workload management, node identity, remote execution, and careful context checks remain part of the operational vocabulary.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Sharing your private key | People confuse the private key with the public key because both files have similar names | Never share `id_ed25519`; share only `id_ed25519.pub` or another public key file |
| Forgetting you are on a remote server | The terminal window looks the same after login, so the operator relies on habit | Run `hostname`, `whoami`, and `pwd` after connecting and before changing anything |
| Typing a password into the wrong place | SSH hides password input, which makes beginners think the prompt is not receiving keystrokes | Type the password at the SSH prompt, expect no visible characters, and press Enter |
| Using the wrong remote username | Cloud images and lab environments often use account names such as `ubuntu`, `ec2-user`, or `admin` | Read the lab or provider instructions and put the correct user before the `@` sign |
| Ignoring host key warnings | People treat the warning as a nuisance instead of a host identity check | Verify the fingerprint through trusted documentation or an administrator before accepting it |
| Leaving sessions open after the task | The terminal stays connected because nothing forces the user to close the shell | Type `exit` or press `Ctrl + D`, then confirm you are back at the local prompt |
| Automating with passwords | A script that needs a human password prompt feels easy at first but breaks unattended operation | Use key-based authentication with proper secret handling and per-system access controls |
| Panicking when a connection drops | Network interruptions feel like data loss when the remote/local model is new | Reconnect, verify context again, and remember that remote files remain on the server |

## Quiz

<details>
<summary>Question 1: You SSH into a server, run `hostname`, and it shows your laptop name. What do you check before running any more commands?</summary>

You should first decide whether the SSH connection actually succeeded or whether you are already back in your local shell. A local hostname after an attempted remote login usually means the connection failed, you exited without noticing, or you connected to `localhost` intentionally. Check the command output above the prompt, run `whoami` and `pwd`, and reconnect only after you know which shell is active. The safe response is to stop and verify context, not to continue with server commands.

</details>

<details>
<summary>Question 2: Your teammate asks you to send your private key so they can log in quickly. What should you do instead?</summary>

You should refuse to share the private key and ask the teammate to generate their own key pair. They can send you their public key, which can then be added to the appropriate account on the server if they are authorized. This preserves individual accountability and makes later revocation possible without replacing your own key. The private key is proof of your identity, so sending it turns your identity into a shared credential.

</details>

<details>
<summary>Question 3: A deployment server must connect to a database server without a human typing a password. Which part of the key pair belongs on the database server?</summary>

The public key belongs on the database server, usually in the target account's `authorized_keys` file or equivalent access mechanism. The private key stays on the deployment server and must be protected as a secret. During authentication, the database server verifies that the client possesses the matching private key without receiving it. Placing the private key on the database server would spread the sensitive material to the wrong side of the trust boundary.

</details>

<details>
<summary>Question 4: You are connected to `ssh admin@10.0.0.5` and run `touch recipe.txt`. Where is the file created, and how can you prove it?</summary>

The file is created on the remote machine at `10.0.0.5`, in the current directory of the remote shell. You can prove the context by running `hostname`, `whoami`, and `pwd` before or after the command, then listing the directory with `ls`. Your keyboard and terminal window are local, but the shell receiving commands is remote. If you type `exit` and then run `ls` locally, you are looking at a different file system context.

</details>

<details>
<summary>Question 5: Your SSH command returns "Connection refused" immediately, but the host name is correct. What layer do you investigate first?</summary>

"Connection refused" usually means the host answered but nothing accepted the connection on the target port. Investigate whether the SSH server is installed, running, and listening on the port you used. Also check whether the server uses a non-default port that requires `ssh -p`. This is different from "Permission denied," which means you reached the SSH service but failed authentication.

</details>

<details>
<summary>Question 6: You need to run the same package update on many servers. Why might manual SSH be the wrong primary method?</summary>

Manual SSH does not scale cleanly because each server becomes a separate chance for typos, missed steps, forgotten documentation, and unreviewed drift. For many servers, configuration management, image rebuilding, or another automation path gives you repeatability and review before execution. SSH may still help diagnose one failed host, but it should not be the normal way to fan out routine changes. The decision is about reducing operational variance, not about disliking SSH.

</details>

<details>
<summary>Question 7: After connecting to a new production host, SSH warns that the host key changed. What is the careful response?</summary>

Stop and verify the host identity through a trusted source before accepting the changed key. A changed host key can be harmless if the server was rebuilt, but it can also indicate that you are not talking to the machine you expect. Ask for the expected fingerprint from the runbook, cloud console, or responsible administrator. Continuing blindly defeats one of SSH's core protections.

</details>

## Hands-On Exercise: SSH to Localhost

This exercise uses `localhost` so you can practice the SSH lifecycle without needing a cloud account. If your operating system does not currently run an SSH server, use the relevant setup notes in the practice section above, or read the command flow carefully and complete the written checks. The goal is not to make your laptop more complicated; the goal is to make the remote-shell model concrete.

Work slowly enough to record evidence at each stage. A good operator's notes are simple: the command used, the host observed, the user observed, the directory observed, and the command used to disconnect. Those notes make it obvious whether the session was local, remote, or a loopback connection to the same machine.

- [ ] Record your local context by running `hostname`, `whoami`, and `pwd` before any SSH command.
- [ ] Open an SSH connection to `localhost`, accepting the first-time host prompt only if you intentionally connected to your own machine.
- [ ] Inside the SSH session, run `hostname`, `whoami`, `pwd`, `ls`, and `echo "Hello from SSH!"`.
- [ ] Disconnect with `exit`, then run `hostname` again to confirm you are back at a local prompt.
- [ ] Write one sentence explaining whether the hostname changed and why that result makes sense for `localhost`.
- [ ] Build, but do not run, the command that would connect as `admin` to `10.0.0.5` on port `2222` with key file `~/.ssh/work_key`.

<details>
<summary>Solution guidance</summary>

Your local context block should show the machine, user, and directory before connection. The localhost SSH command is `ssh localhost`, though some systems may require a username such as `ssh yourname@localhost` depending on account setup. Inside the SSH session, the command output may look very similar because the remote endpoint is the same physical computer, but the SSH authentication and shell lifecycle still happened. The final command for the remote example is `ssh -p 2222 -i ~/.ssh/work_key admin@10.0.0.5`.

</details>

<details>
<summary>Success criteria</summary>

You have succeeded when your notes show a before-connection context block, an SSH command, an inside-session context block, a clean disconnect, and a final local context check. If `localhost` reports the same hostname before and after connection, explain that the protocol still opened a remote-style shell, but the remote endpoint was your own machine. If you used a different practice server, the hostname should normally change after login. In either case, the important proof is that you can identify where commands ran before you change anything.

</details>

## Sources

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
- [Secure Shell](https://en.wikipedia.org/wiki/Secure_Shell)

## Next Module

**Next Module**: [Module 0.9: Software and Packages](../module-0.9-software-and-packages/) - Learn how software gets installed on your computer, what package managers are, and how to install tools from the terminal.
