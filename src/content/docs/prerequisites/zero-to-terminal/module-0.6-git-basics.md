---
title: "Module 0.6: Git Basics — Track Your Work"
slug: prerequisites/zero-to-terminal/module-0.6-git-basics
revision_pending: false
sidebar:
  order: 7
---

> **Complexity**: `[MEDIUM]` - Long-form foundational read with git drills
>
> **Time to Complete**: 90–120 minutes (long-form beginner read + git drills)
>
> **Prerequisites**: [Module 0.5: Editing Files](../module-0.5-editing-files/)

---

## What You'll Be Able to Do

After completing this module, you will be able to:

- Diagnose repository state by interpreting `git status`, `git diff`, and `git log` output instead of guessing what Git will save.
- Construct focused commits by moving selected file changes from the working directory into the staging area and then into repository history.
- Implement a safe local Git setup with accurate author identity, a new repository, and an ignore policy for generated files and secrets.
- Compare local and remote repository timelines so you can choose when to clone, push, pull, fetch, or pause for conflict resolution.
- Design a small Git workflow for Kubernetes configuration files that produces reviewable history without leaking credentials or generated artifacts.

## Why This Module Matters

Hypothetical scenario: an operations group keeps Kubernetes manifests on a shared drive because everyone can open the folder quickly, edit YAML, and copy the latest files into a deployment script. One morning the production namespace changes in a way nobody expected, the cluster accepts the update, and the team cannot tell whether the current file is the intended version, a half-finished experiment, or a copy of an older configuration. The outage investigation is slow not because Kubernetes is mysterious, but because the team has no trustworthy timeline for the text files that describe its infrastructure.

Git solves that operational problem by turning ordinary files into a deliberate, reviewable history. It records snapshots, authors, messages, and parent relationships, so a team can compare what changed, why it changed, and when the change entered the shared record. That matters for source code, but it matters just as much for cloud-native work: a Deployment, a Namespace, a Terraform module, or a CI pipeline definition can all change production behavior when automation trusts the repository as the source of truth.

This module starts with local Git because local confidence comes before collaboration. You will initialize a repository, configure identity, stage changes intentionally, read diffs before committing, and use a `.gitignore` file to keep noise out of history. By the end, you should not merely remember a list of commands; you should be able to diagnose what Git is about to do and explain whether the next action should be `git add`, `git commit`, `git pull`, `git push`, or no action at all.

That diagnostic mindset is what separates a useful Git user from someone who only knows a happy-path recipe. A recipe works when every file is exactly where the tutorial expects it to be, but engineering work rarely stays that neat. You may have half-finished edits, generated logs, a teammate's new remote commits, or a local file that must never leave your machine. Git gives you precise tools for each case, and this module teaches you to choose among them based on observed state.

## How Git Thinks About Your Files

Git is often described as version control, but beginners sometimes hear that phrase and imagine a cloud backup tool that continuously syncs the latest file contents. That model leads to mistakes, because Git is not trying to mirror every keystroke to a server. Git records deliberate snapshots when you ask it to, keeps those snapshots in a local database, and lets you decide exactly which changes belong together before they become part of the project history.

Think of Git like a manual save system in a strategy game. You can explore, make a risky move, inspect the result, and decide whether that state deserves a save point. If you save at thoughtful moments, later decisions become easier because you can compare states and explain how you moved from one state to the next. If you save everything randomly, the history exists, but it does not help you reason during a review or incident.

Historically, many version control systems were centralized. A central server held the authoritative history, and clients depended on that server to inspect history or create new commits. Git is distributed: when you clone a repository, you receive a full local history, not just the latest files. That means you can inspect commits, compare versions, and create local commits while offline, then synchronize with a remote server when connectivity and team coordination are available.

The practical result is that Git has two personalities. Locally, it is a fast database and comparison engine for your files. Collaboratively, it is a synchronization protocol that lets multiple people exchange histories through a remote such as GitHub, GitLab, or Bitbucket. Good Git habits come from respecting both personalities: make clean local commits first, then share them only after you have checked what they contain.

This local-first design is especially helpful in cloud-native work because many infrastructure changes need careful review before they touch a cluster. You can edit manifests, compare the patch, commit a narrow change, and ask another engineer to review the branch without applying anything to Kubernetes yet. Git does not validate the cluster behavior for you, but it gives the team a stable object to discuss. A reviewer can point to a line, a commit, or a branch instead of relying on a vague description of what changed.

Git manages your files through three logical areas. The names matter because most confusing Git messages are simply Git telling you which area contains a change. Your working directory is where your editor writes files, the staging area is where you assemble the next snapshot, and the repository is the saved history inside the hidden `.git` database. The staging area is the piece many beginners skip, but it is what lets you turn messy work into a clean commit.

```text
+---------------------+       +---------------------+       +---------------------+
|                     |       |                     |       |                     |
|  Working Directory  | ----> |    Staging Area     | ----> |     Repository      |
|  (Your local files) |       | (The loading dock)  |       | (The saved history) |
|                     |       |                     |       |                     |
+---------------------+       +---------------------+       +---------------------+
           |                             |                             |
           |   1. Modify files           |                             |
           |---------------------------->|                             |
           |                             |   2. Group changes          |
           |                             |---------------------------->|
           |                             |                             |
           |                                                           |
           |<----------------------------------------------------------|
                               3. Restore old versions
```

The working directory is the current project folder on disk. When you edit `namespace.yaml`, create a README, or delete a temporary file, you are changing the working directory. Git can detect that tracked files differ from the last commit, and it can also notice new untracked files, but it will not automatically decide that those changes belong in the next snapshot. This is why `git status` is the first diagnostic command to learn.

The staging area, also called the index, is a deliberate selection of what the next commit will contain. You can stage one file while leaving another modified file unstaged, or even stage only some hunks from a file with more advanced commands later. That separation is valuable when real work is messy. A debugging session might touch authentication, deployment YAML, and local notes, but the commit should capture one coherent reason for change.

The repository is the permanent local database, stored inside `.git`, where commits live. A commit records file contents, author metadata, a message, a timestamp, and a pointer to its parent commit. In common repositories, each commit is named by a hash such as a SHA-1 object identifier, and newer Git versions can also support SHA-256 repositories. The important beginner idea is simpler than the cryptography: if the content or metadata changes, the identifier changes too.

Pause and predict: you fixed a database connection bug in `db.py`, but while searching for it you also added temporary print statements to `auth.py` and `api.py`. Which part of Git lets you save only the real fix while keeping the temporary debug code on disk? Decide which area of Git you would use and which exact command moves only the intended file before opening the reveal.

<details>
<summary>Check your prediction</summary>

The staging area (or index) lets you save only the real fix while keeping the temporary debug code on disk. It decouples the files you are still editing from the files you are ready to save as the next snapshot. You can run `git add db.py` and commit only that file, while leaving `auth.py` and `api.py` as unstaged modifications in your working directory until you are ready to clean them up.

</details>

## Configure Git and Create a Repository

Git is a command-line tool at its core, even when teams use graphical clients or web interfaces around it. Platform engineers must be comfortable with the terminal version because many workflows happen over SSH, inside automation logs, or on machines where a graphical client is unavailable. The goal is not to memorize every option. The goal is to become fluent enough that repository state is visible instead of mysterious.

Start by checking that Git is installed. Your exact version may differ from the example, and that is fine. The version number matters when you troubleshoot features, but the basic commands in this module have been stable for years. If this command fails, install Git through your operating system package manager before continuing, then reopen the terminal so the executable is available on your `PATH`.

```bash
git --version
```

Expected output should include the Git version installed on your machine; the exact number may differ from this example.

```text
git version 2.39.2
```

Before creating commits, configure the identity Git will place into commit metadata. This is not the same thing as authenticating to GitHub during a push. The name and email configured here answer the question, "Who authored this snapshot?" Remote authentication answers a different question: "Is this person allowed to upload to that server?" Keeping those concepts separate prevents confusion when a commit succeeds locally but a push later asks for credentials.

Replace the placeholder name and email below with your own real values before you run the commands.

```bash
# Set your name (use your real name, this appears in the history)
git config --global user.name "Your Name"

# Set your email address
git config --global user.email "you@example.com"
```

The `--global` flag writes to configuration associated with your user account on this computer, usually in `~/.gitconfig`. You can also set repository-specific configuration without `--global`, which is useful when one laptop contributes to both personal and work repositories. For now, a global beginner setup is enough, and you can inspect it with a command that prints the settings Git sees.

```bash
git config --list
```

Now create a small project directory for the examples. The project uses Kubernetes-flavored filenames because infrastructure configuration is where Git habits quickly become operational habits. The commands below make a directory, enter it, and initialize a repository. Run them in a practice location such as your home directory or a temporary folder, not inside a real work repository.

```bash
# Create a new directory
mkdir k8s-webapp
cd k8s-webapp

# Tell Git to start tracking this directory
git init --initial-branch=main
```

Expected output should confirm that Git created an empty repository database in a hidden `.git` directory.

```text
Initialized empty Git repository in /home/alex/k8s-webapp/.git/
```

What exactly changed? Git created a hidden `.git` directory inside `k8s-webapp`. That hidden directory is not decorative; it is the repository database for this project. It contains objects, references, local configuration, and the machinery Git uses to know which branch you are on. If you delete `.git`, your current files may remain on disk, but the local history, branches, and repository identity are gone.

```bash
# List all files, including hidden ones
ls -la
```

Expected output should show the hidden `.git` directory beside the normal current and parent directory entries.

```text
total 12
drwxr-xr-x 3 alex alex 4096 Oct 12 10:00 .
drwxr-xr-x 5 alex alex 4096 Oct 12 09:59 ..
drwxr-xr-x 7 alex alex 4096 Oct 12 10:00 .git
```

Before running the next command in any new repository, make a habit of predicting what state you expect Git to report. You just ran `git init --initial-branch=main` inside an empty folder and have not created any files yet. What exact branch state, commit count, and staging status should `git status` output? Commit to your prediction before revealing the answer.

<details>
<summary>Check your prediction</summary>

In a brand-new repository with no tracked files and no commits, `git status` reports that you are on branch `main`, that there are "No commits yet", and that there is "nothing to commit (create/copy files and use \"git add\" to track)". That prediction habit is more valuable than it sounds, because every later Git recovery task starts by comparing expected state with observed state.

</details>

## Build Commits Deliberately

The command you will use most often is `git status`, because it is the safest way to ask Git what it sees. It does not change files, create commits, or contact a remote. It simply reports which branch you are on, whether the working directory has modified files, which changes are staged, and which files are untracked. Treat it as your compass before every staging, committing, pulling, or pushing decision.

There is another subtle reason `git status` matters: it teaches you Git's vocabulary in context. "Untracked" means Git sees a file but has no committed baseline for it. "Changes not staged" means Git tracks the file but the current working copy differs from the last commit. "Changes to be committed" means the staging area already contains content for the next snapshot. Those messages are not noise; they are a compact state machine report.

Create the first file in the practice repository. This file defines a Kubernetes Namespace, which is a simple object that lets us focus on Git behavior without needing a running cluster. The content is valid YAML, but the point is the workflow: write a file, inspect repository state, stage the file, and commit the staged snapshot with a message that explains the intent. You can write the file using the `cat` heredoc below, or open `nano namespace.yaml` (practiced in Module 0.5) if you prefer editing in an interactive editor.

```bash
cat << 'EOF' > namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: webapp-prod
EOF
```

Run `git status` immediately. New learners often skip this because they believe they already know what changed, but memory is a weak audit system. Git's report is the objective state. In production work, that objectivity is what keeps temporary notes, generated files, and secret material from entering history by accident.

```bash
git status
```

The output should classify the new file as untracked because it exists on disk but is not part of the next snapshot.

```text
On branch main

No commits yet

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	namespace.yaml

nothing added to commit but untracked files present (use "git add" to track)
```

The file is untracked, which means Git sees it in the working directory but has not been told to include it in version control. Untracked files are not part of the next commit, and Git will not compare future edits to them until you stage and commit them. This behavior is intentional. A directory often contains notes, generated artifacts, or local test files that should not automatically become project history.

Move the file into the staging area with `git add`. This command is easy to underestimate because it sounds like you are adding a file to Git forever. More precisely, you are adding the current content of that file to the staging area for the next commit. If you edit the file again after staging, the new edit will be unstaged until you add it too.

```bash
git add namespace.yaml
```

Run `git status` again and compare the wording. The file has moved from "Untracked files" to "Changes to be committed." That wording tells you the next commit will include the file as it existed when you staged it. Nothing has been permanently saved yet; you have only prepared the next snapshot.

```bash
git status
```

The output should now show the file under changes to be committed, which means it is staged.

```text
On branch main

No commits yet

Changes to be committed:
  (use "git rm --cached <file>..." to unstage)
	new file:   namespace.yaml
```

Commit the staged change. The message should explain the reason for the snapshot at a level useful to a future reviewer. A message like "update" forces people to inspect the diff just to understand the intent. A message like "feat: add production namespace definition" gives the reader a quick summary and still lets them open the diff for detail when needed.

```bash
git commit -m "feat: add production namespace definition"
```

The output should report the root commit, the commit subject, and the number of inserted lines.

```text
[main (root-commit) a1b2c3d] feat: add production namespace definition
 1 file changed, 4 insertions(+)
 create mode 100644 namespace.yaml
```

Check status after the commit. A clean working tree means the tracked files in your working directory match the latest committed snapshot and nothing is staged for the next commit. Clean does not mean the project is correct, secure, or ready for production. It only means Git has no uncommitted tracked changes to report.

```bash
git status
```

The output should now report a clean working tree because the staged content has been committed.

```text
On branch main
nothing to commit, working tree clean
```

Pause and predict: while testing locally, an engineer places a real access token into a YAML file, confirms the application starts, and immediately runs `git commit -am "test config"` before pushing to a shared repository. If they delete the token in a second commit ten minutes later, is the credential safe? Commit to your analysis and determine what operational steps must follow before opening the reveal.

<details>
<summary>Check your prediction</summary>

No, the credential is not safe. Git records permanent snapshots, so deleting the secret in a later commit leaves the token visible in the earlier commit's history for anyone who clones or inspects the repository. Once a real secret is committed and pushed, the token must be treated as immediately compromised and rotated at the provider level, and the repository history must be cleaned or rewritten. The operational lesson is direct: always inspect state with `git status` and patches with `git diff` before staging and committing configuration files.

</details>

The safer professional habit is to make each commit earn its place in history. Before staging, ask whether the patch has one reason that a reviewer can evaluate. Before committing, ask whether the staged content is the exact content you want attached to the message. Before pushing, ask whether the branch contains only work you are ready to share. These questions slow you down by seconds and can save hours of cleanup when a repository becomes the input to deployment automation.

Now modify the Namespace by adding a label. This is a realistic kind of infrastructure edit because labels help teams organize objects, select resources, and drive automation. The Git workflow, however, remains the same: make the change, inspect the difference, stage only the intended content, and commit a focused snapshot.

```bash
cat << 'EOF' > namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: webapp-prod
  labels:
    environment: production
EOF
```

Before staging, read the diff. `git diff` compares the working directory against the last committed snapshot for unstaged changes. This is one of the most protective commands in your toolbox because it shows the exact lines that would surprise a reviewer if you committed without checking. It also trains you to think in patches, which is the unit of review in most professional Git workflows.

```bash
git diff
```

The output should show only the new label lines as additions, with surrounding unchanged YAML for context.

```text
diff --git a/namespace.yaml b/namespace.yaml
index e46b825..8394c41 100644
--- a/namespace.yaml
+++ b/namespace.yaml
@@ -2,3 +2,5 @@ apiVersion: v1
 kind: Namespace
 metadata:
   name: webapp-prod
+  labels:
+    environment: production
```

Diff output has a compact grammar. The `---` and `+++` lines name the old and new sides of the comparison. The chunk header beginning with `@@` tells Git and the reader where in the file the change appears. Lines that begin with a space are context, lines beginning with `+` are additions, and lines beginning with `-` are removals. A modified line is represented as one removal and one addition, which is why line-by-line review is more precise than "I changed the file."

When you review a diff for infrastructure files, read it like a deployment plan, not like a spelling check. A one-line image tag change can move workloads to a different binary. A replica count change can alter cost, availability, and load on dependencies. A namespace or label change can affect automation that selects objects by metadata. Git's diff format is simple, but the operational interpretation of those lines requires attention to what the changed fields control.

Pause and predict: imagine the next diff appears in a Deployment file. Before reading the answer, decide whether this is a new field, a deleted field, or a changed value, and describe the operational effect in plain language. Commit to your answer before opening the reveal.

```text
@@ -10,3 +10,3 @@
 spec:
   replicas: 3
-  image: nginx:1.14
+  image: nginx:1.24
```

<details>
<summary>Check your prediction</summary>

The engineer changed an existing image value from `nginx:1.14` to `nginx:1.24`. That is not merely a formatting update; it changes which container image Kubernetes will pull and run for this workload. In a real pull request review, you would ask whether this ten-minor-version jump is intentional, whether the target tag exists in the registry, and whether the application configuration was tested against that newer version.

</details>

After confirming the label change is the intended change, stage it with `git add namespace.yaml`. Once staged, running plain `git diff` produces no output because there are no unstaged modifications left in the working directory. To review what is currently waiting in the staging area for the next commit, run `git diff --staged` (or its synonym `git diff --cached`). This gives you a final pre-commit safety check before recording the snapshot.

```bash
git add namespace.yaml
git diff --staged
```

The staged diff output confirms that the environment label is queued for the next snapshot, while surrounding lines provide contextual reference for reviewers reading the patch:

```text
diff --git a/namespace.yaml b/namespace.yaml
index e46b825..8394c41 100644
--- a/namespace.yaml
+++ b/namespace.yaml
@@ -2,3 +2,5 @@ apiVersion: v1
 kind: Namespace
 metadata:
   name: webapp-prod
+  labels:
+    environment: production
```

Notice that the commit message should be specific to the label. It does not say "fix stuff" or "update namespace" because those messages decay quickly when someone is scanning history during an incident. A commit message is a tiny piece of operational documentation attached to the exact patch it describes.

```bash
git commit -m "chore: add environment label to namespace"
```

## Inspect History and Diagnose State

Once a repository has more than one commit, history becomes a diagnostic tool. `git log` shows the timeline of snapshots, newest first by default, including commit identifiers, author information, dates, and messages. During troubleshooting, this lets you answer who changed something recently and what explanation they left. During code review, it lets you assess whether the branch history tells a coherent story.

History is most useful when commits are small enough to inspect and messages are specific enough to search. If a branch contains one giant commit that changes namespaces, deployments, scripts, and documentation together, reverting or reviewing it becomes risky because every concern is tangled. If the branch contains focused commits, you can inspect the deployment change separately from the documentation change. Git does not force that discipline, but it rewards it every time you need to reason under pressure.

```bash
git log
```

The output should show the most recent commit first, followed by the earlier root commit.

```text
commit 9f8e7d6c5b4a39281716151413121110abcdef12 (HEAD -> main)
Author: Your Name <you@example.com>
Date:   Wed Oct 12 10:45:12 2023 -0400

    chore: add environment label to namespace

commit a1b2c3d4e5f60718293a4b5c6d7e8f9012345678
Author: Your Name <you@example.com>
Date:   Wed Oct 12 10:15:30 2023 -0400

    feat: add production namespace definition
```

The long hexadecimal strings are commit identifiers. In many repositories they are SHA-1 object names, commonly displayed as long hashes and shortened in user interfaces when the short prefix is unambiguous. You do not need to calculate the hash yourself, but you should recognize it as a precise handle for a snapshot. Saying "the namespace label commit" is helpful in conversation; using the commit identifier is how tools inspect or compare the exact commit.

For daily use, the compact log format is easier to scan. The `--oneline` option shows abbreviated commit identifiers and subjects on one line each. This is often enough when you want to verify that the expected commits exist in the expected order before pushing a branch or asking someone for review.

```bash
git log --oneline
```

The compact output should preserve the same order while reducing each commit to a short identifier and subject.

```text
9f8e7d6 chore: add environment label to namespace
a1b2c3d feat: add production namespace definition
```

You can also use `git log -p` to inspect the patch introduced by each commit. That is useful when the question is not only "When did this change?" but "What exact lines did this commit add or remove?" As repositories grow, you will learn more targeted history tools, but `status`, `diff`, and `log` already give you a strong diagnostic loop: current state, uncommitted line changes, and committed timeline.

Use that loop before assuming Git is broken. If a commit seems to be missing, check whether the change was ever staged and committed. If a file seems to be ignored, check whether it is already tracked or whether the ignore pattern actually matches. If a push is rejected, check whether the remote moved ahead of your local branch. Most beginner Git problems become ordinary state questions once you slow down and collect the evidence in the right order.

The most important habit is to read these commands as a set. If `git status` says a file is modified, `git diff` explains the unstaged modification. If the working tree is clean but behavior changed recently, `git log` tells you which commits to inspect. If a file is untracked, no amount of `git commit` will include it until you stage it. The tool is consistent; confusion usually comes from asking the wrong tree the right question.

Pause and predict: you just ran `git commit -m "chore: add environment label to namespace"` in your practice repository and have not edited any files since. What exact message do you expect `git status` to output when you run it right now? Commit to an answer before opening the reveal.

<details>
<summary>Check your prediction</summary>

If you have not edited or created any files since the commit, `git status` will output `nothing to commit, working tree clean`. That indicates that every tracked file matches the latest committed snapshot and no untracked files are present in the directory. If it reports anything else, pause and inspect the remaining changes rather than making another commit immediately, because the mismatch tells you there is still unrecorded state in your workspace.

</details>

## Work With Remotes Without Losing the Plot

Everything so far has happened on your local machine. That is enough to practice Git, but it is not enough for team work or backup. A remote is another repository reachable over a network, usually hosted by a service such as GitHub, GitLab, or Bitbucket. Because Git is distributed, the remote is not magic; it is another copy of the repository history that your local repository can fetch from and push to when the histories are compatible.

```text
+-----------------------+                    +-----------------------+
|                       |                    |                       |
|   Local Repository    |                    |   Remote Repository   |
|   (Your Laptop)       |                    |   (GitHub/GitLab)     |
|                       |                    |                       |
|  commit C (HEAD)      | ==== git push ===> |  commit C             |
|  commit B             |                    |  commit B             |
|  commit A             | <=== git pull ==== |  commit A             |
|                       |                    |                       |
+-----------------------+                    +-----------------------+
```

When you create an empty repository on a hosting platform, the platform gives you a URL. You connect your local repository to that URL with `git remote add`. By convention, the first and primary remote is named `origin`, but the name is just a local nickname. The URL is where data goes; the remote name is how you refer to that URL in commands.

```bash
# Example command (do not run unless you have a real repository URL prepared)
git remote add origin https://github.com/yourusername/k8s-webapp.git
```

If the repository already exists on the server, do not create a new local repository and try to glue the histories together. Use `git clone <url>` instead. Cloning initializes the local `.git` directory, downloads the repository history, checks out a working tree, and records the remote as `origin`. Most professional work starts from cloning because the team history already exists before you arrive.

Pushing uploads your local commits to the remote branch. The first push of a new branch often includes `-u`, which sets an upstream tracking relationship so future `git push` and `git pull` commands can infer the remote branch. This convenience is useful, but only after you understand what is being tracked. If the branch relationship is wrong, Git may push somewhere unexpected or ask you to be more explicit.

```bash
# Push your main branch to the origin remote for the first time
git push -u origin main
```

Pulling downloads remote commits and integrates them into your current branch. Conceptually, `git pull` is `git fetch` followed by an integration step such as merge or rebase, depending on configuration. Beginners can treat it as "bring the remote branch into my local branch," but it is worth remembering the two-part nature because `git fetch` alone is safer when you only want to inspect remote changes before modifying your working branch.

```bash
# Fetch changes from the remote and merge them into your local branch
git pull origin main
```

Pause and predict: you made two local commits while offline, and a colleague pushed three commits to the same remote branch before you reconnected. What happens if you try `git push origin main` immediately? Decide what Git will do and what your recovery sequence should be before opening the reveal.

<details>
<summary>Check your prediction</summary>

Git will reject the push with an error stating that updates were rejected because the remote contains work that you do not have locally (non-fast-forward push). Git refuses to let your push overwrite the remote timeline by accident. To recover, you must run `git fetch` or `git pull` to bring in the colleague's commits, inspect the combined history, resolve any merge conflicts if the same lines were touched, and then push your updated branch.

</details>

This protection is one reason Git is safer than copying files over a shared folder, but it is not a substitute for communication. If two people edit the same line in the same file, Git can detect a conflict, but it cannot decide the correct business or operational outcome. In Kubernetes manifests, that may mean choosing the correct replica count, image tag, namespace, or resource limit. The human decision still matters; Git simply prevents silent overwrites.

There is also a difference between remote synchronization and deployment. Pushing a manifest to a repository shares code with the team and may trigger automation if the project has CI/CD configured, but Git itself is not Kubernetes and does not apply resources to a cluster. That boundary is important. A clean Git history makes deployment automation auditable, yet you still need separate checks, reviews, and cluster feedback to know whether the infrastructure change is safe.

## Ignore Noise and Protect Secrets

Real projects generate files that do not belong in version control. Build directories, logs, local cache files, operating system metadata, editor swap files, downloaded dependencies, Terraform state, and private environment files can all appear beside source files. If those files enter Git history, they create different kinds of damage: large binaries bloat the repository, generated files cause noisy reviews, and secrets create immediate security incidents.

Git handles this with `.gitignore`, a plain text file usually stored at the repository root. Each line is a pattern for files Git should ignore when they are untracked. The "untracked" part is crucial. `.gitignore` prevents new matching files from being noticed as candidates for staging, but it does not make Git forget a file that is already tracked in history. If a secret was committed, you must treat the secret as compromised and rotate it, not merely add it to `.gitignore`.

Create an ignore file for the practice repository. The exact patterns below are intentionally small so you can reason about them. They show operating system noise, local secrets, a local kubeconfig-style file, and Terraform state. In a production repository, you would adapt patterns to the tools actually used by the project and review them just like any other infrastructure policy.

```bash
cat << 'EOF' > .gitignore
# Ignore operating system generated files
.DS_Store
Thumbs.db

# Ignore local secret and credential files
.env
secret-keys.yaml
kubeconfig-local

# Ignore terraform state files (if we add Infrastructure as Code later)
*.tfstate
*.tfstate.backup
.terraform/
EOF
```

Git reads ignore patterns and normally hides matching untracked files from `git status`. That reduces the chance of a broad staging command pulling in local-only files. It does not eliminate the need to read `git status` and `git diff`, because ignore files can be incomplete and because tracked files remain tracked even if their names later match an ignore rule.

Pause and predict: with the `.gitignore` file configured above containing `*.tfstate`, `secret-keys.yaml`, and `kubeconfig-local`, which of these three new untracked files would still appear when you run `git status`: `main.tfstate`, `secret-keys.yaml`, or `secret-keys.txt`? Commit to your prediction for each file before opening the reveal.

<details>
<summary>Check your prediction</summary>

Only `secret-keys.txt` will show up as untracked under `git status`. `main.tfstate` is ignored because it matches the `*.tfstate` wildcard pattern, and `secret-keys.yaml` is ignored because it matches the exact filename pattern. The file `secret-keys.txt` does not match any rule in `.gitignore`, so Git reports it as an untracked candidate ready to be staged.

</details>

Now consider a late ignore rule. You committed `database-creds.txt` last week, then today you add that filename to `.gitignore` and edit the file. Git will still report the modification because the file is already tracked. To stop tracking the file while keeping the local copy, you would need a command such as `git rm --cached database-creds.txt`, followed by a commit, and you would still rotate any credential that was ever committed.

This is why a strong Git workflow is both technical and behavioral. The technical controls are `.gitignore`, `git status`, `git diff`, and secret scanning on the server side. The behavior is slower and more deliberate: do not stage blindly, do not store real credentials in practice manifests, and do not assume a later cleanup commit erases exposure. Git history is useful because it remembers, and that same remembering makes leaked secrets persistent.

For Kubernetes and cloud projects, a useful `.gitignore` policy usually appears before the first serious commit. Local kubeconfig files, generated manifests, temporary logs, Terraform working directories, and downloaded tool caches can all accumulate quickly. Some of those files are harmless noise, while others may contain credentials or environment-specific state. Ignoring them early keeps reviews focused on source files and reduces the chance that a local workstation detail becomes part of the team's permanent history.

## Patterns & Anti-Patterns

Git patterns are useful when they make history easier to review and safer to automate. The common thread is intentionality: stage intentionally, commit one coherent change at a time, and keep generated or sensitive files out of the repository. The anti-patterns below usually come from speed pressure, but they create slower recovery later because the history stops answering operational questions.

| Pattern or Anti-Pattern | When It Appears | Why It Matters | Better Habit |
| :--- | :--- | :--- | :--- |
| Pattern: inspect before staging | Any change to code, YAML, scripts, or docs | You catch accidental edits, debug output, and secrets before they enter history. | Run `git status`, then `git diff`, then stage named files. |
| Pattern: focused commits | A task touches several files for different reasons | Reviewers can understand and revert one logical change without dragging unrelated work along. | Commit the namespace change separately from README edits or local experiments. |
| Pattern: repository-root `.gitignore` | A project has generated files, logs, state files, or local credentials | Shared ignore policy prevents common local noise from appearing for every contributor. | Review ignore patterns with the same care as build or deployment configuration. |
| Anti-pattern: broad staging by reflex | A learner types `git add .` after every edit | Git may stage files the learner forgot existed, including generated files or local configuration. | Use named files first; use broad staging only after reading status and diff carefully. |
| Anti-pattern: vague commit messages | A branch has messages such as "update" or "fix" | Incident review becomes slower because history no longer explains intent. | Write a short subject that names the operational reason for the snapshot. |
| Anti-pattern: treating pull as harmless | A local branch has uncommitted work and the remote moved | Pull may create conflicts or merge commits before the learner understands local state. | Start with `git status`; commit, stash, or discard local work deliberately before integrating remote history. |

## Decision Framework

When Git feels confusing, choose the next command based on the state you need to inspect or change, not based on a memorized sequence. The same repository may need different commands depending on whether the problem is untracked files, unstaged edits, staged changes, missing remote commits, or a branch that has not been pushed before. This table gives you a beginner decision path that is conservative enough for infrastructure work.

| Situation | Safer First Question | Command to Start With | What You Do Next |
| :--- | :--- | :--- | :--- |
| You edited files and want to know what Git sees | Which tree contains the change? | `git status` | Read whether files are untracked, unstaged, or staged. |
| You want to review exact line changes | What would surprise a reviewer? | `git diff` | Stage only the intended files after reading the patch. |
| You already staged changes but want to inspect staged content | What is in the next snapshot? | `git diff --staged` | Commit if it is correct, or unstage and revise. |
| You want a local save point | Does the staged change have one coherent reason? | `git commit -m "message"` | Write a message that explains intent, not just mechanics. |
| You need work from the remote | Has my local branch got uncommitted work? | `git status` then `git pull` | Pull only when the local state is understood and ready. |
| You need to share local commits | Does the remote have work I lack? | `git push` or explicit `git push -u origin main` | If rejected, fetch or pull, integrate, and push again. |

Use `git init` when you are starting a brand-new local repository in a directory that does not already have history. Use `git clone` when the project already exists somewhere else and you want your local copy to share that existing history. Use `.gitignore` before local files pile up, especially when a project touches credentials or generated artifacts. Use `git log` when behavior changed and you need a timeline, not when you are trying to inspect uncommitted edits.

The decision framework also helps you avoid destructive commands early in your Git journey. There are commands that rewrite history, discard changes, or remove files from the index, and you will learn some of them later. At this stage, prefer observation commands first. A clean diagnosis with `status`, `diff`, and `log` makes recovery commands safer because you know exactly which state you are trying to change.

## Did You Know?

1. **Git was built in 2005 under intense pressure.** The Linux kernel project lost its free BitKeeper arrangement, which pushed Linus Torvalds and contributors to create a replacement quickly for a very large distributed project.
2. **The name is intentionally cheeky.** Torvalds has joked about the name ["Git" in public talks and interviews](https://en.wikipedia.org/wiki/Git), and the name stuck because the tool solved a real collaboration problem better than the alternatives available to the kernel community.
3. **Git does not track empty directories.** Git tracks file content, so teams that need an otherwise empty directory usually add a small placeholder file such as `.gitkeep` by convention.
4. **Object identifiers are part of Git's integrity model.** Many repositories still display 40-character SHA-1 object names, while modern Git also includes support for SHA-256 repositories for stronger long-term collision resistance.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
| :--- | :--- | :--- |
| Accidentally committing a password or secret | The learner stages broadly without reading `git status` and `git diff`, so a local `.env` or credential file enters the commit. | If it was pushed, rotate the credential immediately and follow the repository's secret-removal process. If it was only local, remove it from history before sharing and add an ignore rule. |
| Seeing "fatal: refusing to merge unrelated histories" | A repository was initialized locally, while the hosting service also created its own first commit such as a README. | Prefer cloning an existing remote. If combining histories is truly intended, use the explicit unrelated-histories option only after reviewing why the histories differ. |
| Getting "updates were rejected" during push | The remote branch has commits that the local branch lacks, often because someone pushed while you were offline. | Fetch or pull the remote work, resolve any conflicts, verify the combined history, and push again only after the local branch includes the remote commits. |
| Writing empty or meaningless commit messages | The learner treats commits as checkpoints for themselves rather than messages to future maintainers. | Amend an unpushed commit message when needed and practice explaining the operational reason for each snapshot. |
| Forgetting to stage files before committing | The working directory contains changes, but the staging area is empty when `git commit` runs. | Run `git status`, stage the intended files with `git add <file>`, inspect again, and retry the commit. |
| Committing generated or binary artifacts | Build outputs and logs sit beside source files, and the repository has no ignore policy yet. | Remove accidental tracked artifacts with the appropriate Git command, commit the cleanup, and add patterns to `.gitignore` before more work continues. |
| Adding an ignore rule after a file is already tracked | The learner expects `.gitignore` to override history for files already committed. | Remove the file from tracking with an index-only removal such as `git rm --cached <file>`, commit that change, and rotate secrets if sensitive content was ever committed. |

## Quiz

<details>
<summary>1. Your team deployed a Kubernetes configuration and behavior changed immediately. You need to identify the recent commits, authors, and messages before deciding what to inspect next. Which Git command gives you the timeline, and why is it the right starting point?</summary>

Use `git log`, or `git log --oneline` when you need a compact scan. The log shows committed history in reverse chronological order, so it answers who created recent snapshots and what messages they left. `git status` would only describe uncommitted local state, and `git diff` would only show unstaged line changes. During incident triage, the timeline narrows the search before you inspect individual patches.

</details>

<details>
<summary>2. You modified `service.yaml` and ran `git commit -m "expose port 8080"`, but Git said nothing was added to commit. What state did you forget to change, and how should you recover?</summary>

The file was still in the working directory and had not been moved into the staging area. Git does not automatically include every modified file in a commit, because the staging area is where you choose the next snapshot's contents. Run `git status` to confirm the file state, then `git add service.yaml`, inspect status again, and rerun the commit. This preserves the deliberate two-step model that keeps unrelated edits out of history.

</details>

<details>
<summary>3. You are about to stage `configMap.yaml`, but you are unsure whether a real database password is still present in the edited lines. What should you inspect before staging, and what decision should follow?</summary>

Run `git diff` before staging so you can inspect the exact unstaged line changes. If the diff contains a real password, do not stage or commit it; remove the secret, replace it with a safe placeholder or external reference, and verify the diff again. `git log` would not help because the risky content is not committed yet. The safest decision is to make the patch clean before it enters the staging area.

</details>

<details>
<summary>4. You cloned a repository and Git asks you to configure `user.name` and `user.email` before committing. Later, `git push` asks for remote credentials. Why are these two prompts different?</summary>

`user.name` and `user.email` are local commit metadata that identify the author recorded inside new commits. Remote credentials prove to the hosting service that you are allowed to upload commits to that repository. The first setting affects the saved snapshot's attribution, while the second controls network access. Confusing them leads learners to think a successful local commit means the remote will also accept a push, which is not guaranteed.

</details>

<details>
<summary>5. You created `aws-credentials.json` for a local test and never want it committed. What should you do before staging other work, and what limitation must you remember?</summary>

Add `aws-credentials.json` to the repository's `.gitignore` file before broad staging, then run `git status` to confirm the file no longer appears as an untracked candidate. The limitation is that `.gitignore` only applies to untracked files. If the file was already committed, Git will continue tracking it until you explicitly remove it from the index, and any real secret inside should be considered exposed. The safer workflow is to prevent tracking before the file ever reaches a commit.

</details>

<details>
<summary>6. A learner deletes the hidden `.git` directory to "reset" a broken project, then runs `git status`. What happens, and why is this not a safe recovery method?</summary>

Git reports that the directory is not a Git repository, because the `.git` directory contained the repository database, branches, references, and local history. Deleting it does not create a clean Git history; it destroys the local repository metadata while leaving ordinary working files behind. A safer recovery starts with observation commands and a clear goal, such as unstaging a file or reverting a commit. Removing `.git` should not be treated as a normal troubleshooting step.

</details>

<details>
<summary>7. You and a colleague both changed the same `replicas` line in `nginx-deployment.yaml`. Their change reached the remote first, your push is rejected, and then you pull. What should you expect and how do you resolve it?</summary>

Git may stop with a merge conflict because two histories changed the same line differently, and it cannot know which replica count is operationally correct. Open the file, read the conflict markers, choose or combine the intended value, and remove the markers. Then stage the resolved file and complete the merge commit before pushing. The important point is that Git detects the unsafe overlap, but a human still owns the infrastructure decision.

</details>

## Hands-On Exercise

In this exercise, you will create a local repository from scratch, simulate a standard engineering workflow by making multiple logical commits, and observe the resulting history. The files are small Kubernetes-style examples so you can focus on Git's state transitions rather than cluster behavior. Work in a disposable directory, read `git status` after each meaningful step, and do not use real credentials anywhere in the practice files.

### Task 1: Initialization

Create a new directory named `dojo-k8s-project`, navigate into it, and initialize an empty Git repository so you can observe the first status report from a clean practice workspace.

- [ ] Directory created and navigated into.
- [ ] Git repository initialized.

<details>
<summary>Solution: Task 1</summary>

```bash
mkdir dojo-k8s-project
cd dojo-k8s-project
git init --initial-branch=main
git status
```

</details>

### Task 2: The Initial Commit

Create a `README.md` file with the text "# KubeDojo Project". Stage the file and commit it with the message "docs: add initial readme". This task checks that you can move a new file through the working directory, staging area, and repository history without skipping the state checks.

- [ ] File created with correct content.
- [ ] File added to staging area.
- [ ] Commit successfully created.

<details>
<summary>Solution: Task 2</summary>

```bash
echo "# KubeDojo Project" > README.md
git status
git add README.md
git status
git commit -m "docs: add initial readme"
```

</details>

### Task 3: Simulating Infrastructure Development

Create a file named `deployment.yaml` and add the following dummy content so the repository has an infrastructure-style file to track:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
```

Stage and commit this file with the message "feat: add web deployment skeleton" after confirming that Git reports the file as untracked.

- [ ] File created.
- [ ] Commit successfully created with correct message.

<details>
<summary>Solution: Task 3</summary>

```bash
cat << 'EOF' > deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
EOF

git status
git add deployment.yaml
git commit -m "feat: add web deployment skeleton"
```

</details>

### Task 4: Modifying Existing Files

Open `deployment.yaml` and add `replicas: 3` under a `spec:` block, then inspect the resulting line change before you stage it:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 3
```

Use a command to view the exact differences before staging. Then, stage and commit the change with the message "fix: set deployment replicas to 3".

- [ ] File modified.
- [ ] Diff viewed successfully.
- [ ] Change staged and committed.

<details>
<summary>Solution: Task 4</summary>

```bash
# Modify the file using your preferred editor (nano, vim, or cat override)
cat << 'EOF' > deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 3
EOF

# View the diff
git diff

# Stage and commit
git add deployment.yaml
git commit -m "fix: set deployment replicas to 3"
```

</details>

### Task 5: Reviewing the Timeline

Run a command to view your complete commit history in a compact, single-line format. Verify that all three of your commits are present with the most recent first (the default for `git log --oneline`). If a commit is missing, use `git status` to determine whether the change is still unstaged, staged, or never created.

- [ ] History command executed.
- [ ] Three distinct commits visible in the output.

<details>
<summary>Solution: Task 5</summary>

```bash
git log --oneline
```

Output should look similar to:

```text
3b2a1c4 fix: set deployment replicas to 3
9f8e7d6 feat: add web deployment skeleton
1a2b3c4 docs: add initial readme
```

</details>

### Task 6: Bonus Challenge — Advanced Ignore Rules

You are working on a new application that generates numerous log files ending in `.log` across various directories. You want Git to ignore all of them to save space, but you must ensure that one specific file named `audit-trail.log` in the root directory is always tracked for compliance reasons. Create a `.gitignore` file that achieves this exact configuration, then verify the result with dummy files and `git status`.

- [ ] `.gitignore` file created with appropriate wildcard and exclusion rules.
- [ ] Dummy files created to test the rules.
- [ ] `git status` confirms only the required file is untracked.

<details>
<summary>Solution: Task 6</summary>

```bash
# Create the .gitignore file
cat << 'EOF' > .gitignore
*.log
!audit-trail.log
EOF

# Create dummy files
touch app.log
touch database.log
touch audit-trail.log

# Check status
git status
```

Git will show `.gitignore` and `audit-trail.log` as untracked files. The other `.log` files will be successfully ignored.

</details>

### Task 7: Unguided Git-State Diagnostic

In this final challenge, there is no step-by-step command list to copy. You are presented with two realistic scenarios that test whether you can interpret Git state and choose the correct operational action: `git add`, `git commit`, ignore configuration, `git fetch`/`git pull`, or do nothing.

Challenge 1: The Planted Workspace Trap. Run the following setup snippet inside your `dojo-k8s-project` directory to plant a realistic messy state with staged modifications, unstaged modifications, and untracked files:

```bash
# Plant messy workspace state
echo "port: 8080" >> deployment.yaml
git add deployment.yaml
echo "  # verify container port" >> deployment.yaml
touch temp-notes.txt
touch incident-token.env
```

Before running any fix or commit, use your diagnostic commands (`git status`, `git diff`, and `git diff --staged`) to answer these four questions in your notes:
1. Why does `deployment.yaml` appear twice in the output of `git status`?
2. How do you view the change that is staged for commit versus the change that is only in your working directory?
3. Which files must be kept out of version control, and what action ensures they are ignored?
4. What is the precise command sequence to safely ignore the credential and scratch files, unstage the incomplete YAML edit, and return the working tree to clean?

Challenge 2: The Divergent Timelines Diagnostic. A colleague on your infrastructure team reports that running `git push origin main` fails with a rejection error. They share the following output comparing their local commit log with the remote tracking branch on the shared server:

```text
Local log:
f1a2b3c (HEAD -> main) feat: add redis cache deployment
3b2a1c4 fix: set deployment replicas to 3
9f8e7d6 feat: add web deployment skeleton

Remote tracking log (origin/main):
d4e5f6a (origin/main) chore: update prometheus scrape annotations
3b2a1c4 fix: set deployment replicas to 3
9f8e7d6 feat: add web deployment skeleton
```

Without running commands, diagnose the repository state:
1. Why was `git push` rejected, and what does the divergence between `HEAD` and `origin/main` indicate?
2. What should the engineer do next: `git commit`, `git push --force`, `git fetch` followed by inspection, or `git init`?
3. What catastrophic risk would `git push --force` introduce for the rest of the team?

- [ ] Planted workspace state diagnosed using `git status`, `git diff`, and `git diff --staged`.
- [ ] Appropriate action chosen for each file (stage, unstage, or ignore).
- [ ] Divergent remote timeline diagnosed with the correct synchronization action identified.

<details>
<summary>Solution: Task 7 Diagnostic Walkthrough</summary>

For Challenge 1 (The Planted Workspace):
1. `deployment.yaml` appears twice in `git status` because it has two distinct states simultaneously: one line addition (`port: 8080`) was staged with `git add`, and a subsequent comment addition (`# verify container port`) was made in the working directory after staging. The staging area holds a snapshot of how the file looked at the moment `git add` ran.
2. Run `git diff --staged` to inspect the changes staged for the next commit (`port: 8080`), and run plain `git diff` to inspect the unstaged working tree modification (`# verify container port`).
3. `incident-token.env` contains sensitive credential material and must never be staged or committed. `temp-notes.txt` is scratch documentation. Both should be added to `.gitignore` (or deleted from disk).
4. To clean up safely:
   - Add ignore patterns: append `incident-token.env` and `*.txt` to `.gitignore`.
   - Unstage the incomplete YAML change: run `git restore --staged deployment.yaml` (or `git rm --cached deployment.yaml` on older Git versions).
   - Discard the unwanted scratch edits from the working copy: run `git restore deployment.yaml` (or remove the extra lines in `nano`).
   - Remove the untracked scratch files: `rm temp-notes.txt incident-token.env`.
   - Run `git status` to confirm that the working tree is clean.

For Challenge 2 (The Divergent Timelines):
1. `git push` was rejected because the remote branch `origin/main` contains commit `d4e5f6a` ("chore: update prometheus scrape annotations"), which is not present in the local history. Git prevents non-fast-forward pushes to protect remote history from being silently overwritten.
2. The engineer should run `git fetch origin` to download the remote commit objects, then compare the branches with `git log HEAD..origin/main` or `git diff HEAD..origin/main`. Once understood, they can run `git pull origin main` (or `git pull --rebase origin main`) to integrate the remote changes, verify the resulting configuration, and then push.
3. Running `git push --force` would overwrite `origin/main` with the local branch, permanently erasing commit `d4e5f6a` from the shared branch and destroying the teammate's Prometheus monitoring configuration. Force-pushing to shared branches should be forbidden by branch protection rules.

</details>

### Success Criteria

- [ ] You can explain the difference between the working directory, staging area, and repository history using your own practice files.
- [ ] You created at least three focused commits with meaningful messages.
- [ ] You inspected a diff before staging a Kubernetes-style YAML change.
- [ ] You used `git log --oneline` to verify the resulting history.
- [ ] You created and tested a `.gitignore` rule that ignores a broad pattern while allowing one exception.
- [ ] You diagnosed complex repository states and divergent timelines using status, diff, and log without guidance.

## Sources

- [Git documentation](https://git-scm.com/docs)
- [Git book: Getting Started](https://git-scm.com/book/en/v2/Getting-Started-About-Version-Control)
- [Git book: A Short History of Git](https://git-scm.com/book/en/v2/Getting-Started-A-Short-History-of-Git)
- [Git book: Git Basics](https://git-scm.com/book/en/v2/Git-Basics-Getting-a-Git-Repository)
- [Git documentation: git-init](https://git-scm.com/docs/git-init)
- [Git documentation: git-config](https://git-scm.com/docs/git-config)
- [Git documentation: git-status](https://git-scm.com/docs/git-status)
- [Git documentation: git-add](https://git-scm.com/docs/git-add)
- [Git documentation: git-commit](https://git-scm.com/docs/git-commit)
- [Git documentation: git-diff](https://git-scm.com/docs/git-diff)
- [Git documentation: git-log](https://git-scm.com/docs/git-log)
- [Git documentation: gitignore](https://git-scm.com/docs/gitignore)
- [GitHub Git Guide](https://github.com/git-guides)
- [GitHub Git Guide: git pull](https://github.com/git-guides/git-pull)
- [GitHub gitignore templates](https://github.com/github/gitignore)

## Next Module

[Module 0.7: What is Networking?](../module-0.7-what-is-networking/) — Now that you can track files, it is time to understand how computers talk to each other across networks.
