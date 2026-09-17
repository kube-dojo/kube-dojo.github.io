---
citations_verified: true
title: "Module 0.3: Vim for YAML"
slug: k8s/cka/part0-environment/module-0.3-vim-yaml
sidebar:
  order: 3
lab:
  id: cka-0.3-vim-yaml
  url: https://killercoda.com/kubedojo/scenario/cka-0.3-vim-yaml
  duration: "25 min"
  difficulty: intermediate
  environment: ubuntu
revision_pending: false
---

> **Complexity**: `[MEDIUM]` - Long-form editor workflow module with repeated YAML drills
>
> **Time to Complete**: 25-35 minutes
>
> **Prerequisites**: Basic terminal navigation, Module 0.1 environment setup recommended

---

## Learning Outcomes

After this module, you will be able to:

- **Configure** vim so Kubernetes YAML uses two-space indentation, spaces instead of tabs, and line numbers that make parser errors easier to locate.
- **Diagnose** common YAML editing failures by comparing vim state, hidden whitespace, indentation levels, and `kubectl` validation output.
- **Refactor** Kubernetes manifests in vim by copying, deleting, indenting, and replacing blocks without retyping large sections under exam pressure.
- **Evaluate** when vim, nano, `kubectl --dry-run`, or shell redirection is the fastest safe editing path for a given CKA task.
- **Repair** broken Pod and Deployment manifests using a repeatable edit-validate-fix loop that works in a terminal-only environment.

---

## Why This Module Matters

A candidate is twenty minutes into a performance exam when a Deployment manifest fails validation. The application idea is simple, the YAML looks almost right, and the cluster is healthy, yet the terminal shows a parser error pointing near a line that appears visually harmless. The candidate opens the file again, presses a few keys in the wrong mode, accidentally deletes part of the manifest, and loses more time recovering the editor than solving Kubernetes.

That situation is not really a vim problem. It is a workflow problem. Kubernetes work often happens in a terminal, YAML is whitespace-sensitive, and the editor becomes part of the diagnostic path. A learner who can move quickly through a file, see line numbers, preserve indentation, and validate small changes can spend attention on Kubernetes behavior instead of fighting invisible characters.

This module teaches vim as a practical Kubernetes editing tool, not as a lifestyle choice. You do not need plugin mastery, macros, custom themes, or years of muscle memory. You need a dependable mental model, a tiny set of commands, a safe `.vimrc`, and enough YAML-specific troubleshooting practice to recover when the file on screen disagrees with what the parser sees.

The exam environment may make nano available and may even default to it, depending on the current image. That does not make vim irrelevant. Vim remains widely available on Linux systems, appears in many production troubleshooting sessions, and is often the editor people reach for inside minimal terminal environments. The right standard is not loyalty to an editor; the right standard is whether you can edit a manifest safely under pressure.

> **The Flight Deck Analogy**
>
> Vim modes are like controls on a flight deck. One set of controls moves the aircraft, another changes radio settings, and another manages navigation. Confusing those controls is dangerous, but once the separation is clear, each action becomes faster because the controls are specialized. In vim, Normal mode moves and edits structure, Insert mode types text, and Command mode saves, quits, searches, or changes editor behavior.

---

## Part 1: Build the Vim Mental Model Before Typing YAML

Vim feels strange at first because it does not treat every keypress as text entry. That design is the source of both the frustration and the speed. In a normal text box, pressing `d` inserts the letter `d`; in vim Normal mode, pressing `dd` deletes a line. The same keyboard becomes a command surface, so the first skill is knowing which mode owns the next keypress.

The safest recovery habit is simple: when the editor surprises you, press `Esc` once or twice before doing anything else. Pressing `Esc` returns you to Normal mode, where commands like save, quit, undo, search, and line deletion behave predictably. This habit matters because many exam mistakes come from trying to run `:wq` while still in Insert mode or trying to type YAML while still in Normal mode.

```text
+------------------+        i, a, o         +------------------+
|  NORMAL MODE     | ---------------------> |  INSERT MODE     |
|  move/edit lines |                        |  type YAML text  |
|  dd, yy, p, u    | <--------------------- |  letters appear  |
+------------------+          Esc           +------------------+
          |
          | :
          v
+------------------+
|  COMMAND MODE    |
|  :w, :q, :wq     |
|  :set paste      |
|  :%s/old/new/g   |
+------------------+
```

The diagram shows why `Esc` is the reset key. You can enter Insert mode through several commands, but you leave it the same way every time. Command mode is reached from Normal mode with `:`, so a reliable save sequence is always `Esc`, then `:w`, then `Enter`. A reliable save-and-exit sequence is always `Esc`, then `:wq`, then `Enter`.

| Mode | How to Enter | What It Does | Kubernetes Editing Example |
|------|--------------|--------------|----------------------------|
| Normal | `Esc` | Navigate, delete, copy, paste, undo | Delete a bad `env:` block with `4dd` |
| Insert | `i`, `a`, `o`, `O` | Type text into the file | Add `image: nginx:1.25` under a container |
| Command | `:` from Normal mode | Save, quit, search, replace, configure vim | Run `:%s/nginx:old/nginx:1.25/g` |

> **Pause and predict**: You press `j` expecting the cursor to move down, but the letter `j` appears inside `metadata.name`. Which mode are you in, what should you press, and what should you check before continuing?

The answer is that you are in Insert mode. Press `Esc` to return to Normal mode, then use `j` only for navigation. Before continuing, check whether the accidental `j` changed a meaningful field. This tiny recovery loop matters because accidental characters inside YAML values can create valid YAML that produces the wrong Kubernetes object, which is worse than an obvious parser error.

### 1.1 The Commands Worth Memorizing

You can complete most CKA editing tasks with a compact command set. The goal is not to become fast at every vim feature. The goal is to become reliable at the actions that map directly to Kubernetes manifest work: insert a field, delete a block, copy a block, adjust indentation, search for a value, save, and validate.

```text
ENTERING INSERT MODE
i        Insert before the cursor
a        Insert after the cursor
o        Open a new line below and enter Insert mode
O        Open a new line above and enter Insert mode

NAVIGATION IN NORMAL MODE
h        Move left
j        Move down
k        Move up
l        Move right
gg       Go to the first line
G        Go to the last line
0        Go to the beginning of the current line
$        Go to the end of the current line
w        Jump forward one word
b        Jump backward one word

EDITING IN NORMAL MODE
x        Delete the character under the cursor
dd       Delete the current line
5dd      Delete five lines starting at the current line
yy       Copy the current line
p        Paste below the current line
P        Paste above the current line
u        Undo the last change
Ctrl+r   Redo the undone change

YAML BLOCK EDITING
>>       Indent the current line one level to the right
<<       Indent the current line one level to the left
V        Start visual line selection
>        Indent the selected lines right
<        Indent the selected lines left
=        Reindent the selected lines using vim's indentation rules

SEARCH AND REPLACE
/pattern            Search forward for pattern
n                   Move to the next match
N                   Move to the previous match
:%s/old/new/g       Replace old with new throughout the file

SAVE AND QUIT
:w       Save the file
:q       Quit if there are no unsaved changes
:wq      Save and quit
:q!      Quit and discard unsaved changes
```

The most important command in that list is not the cleverest one. It is `u`, because fast editing without fast undo creates hesitation. If you delete too much with `5dd`, press `u`. If a paste goes wrong, press `u`. If an indentation experiment makes the file worse, press `u` and choose a smaller selection.

The second most important habit is prefacing destructive commands with a count only when you have counted the target lines. `3dd` is excellent when the broken block is exactly three lines. It is risky when you are guessing. Under pressure, count visible lines with line numbers, delete a smaller block, and validate rather than trying to perform one dramatic edit.

### 1.2 How Vim Commands Map to YAML Structure

Kubernetes YAML is hierarchical. A line's meaning depends on where it is indented relative to the lines around it. Vim's line-based commands fit that structure well because you often need to move or remove entire YAML records, not individual characters. A container item, an environment variable item, a port item, and a label line each occupy predictable line blocks.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web
  labels:
    app: frontend
spec:
  containers:
  - name: app
    image: nginx:1.25
    ports:
    - containerPort: 80
```

In this manifest, deleting only `image: nginx:1.25` leaves a container with a name but no image, which Kubernetes rejects. Deleting the whole container item would require deleting the `- name`, `image`, `ports`, and `containerPort` lines together. That is why line selection and counted deletes are not editor trivia; they are how you preserve or remove complete Kubernetes structure.

```text
metadata:
  name: web              <- child of metadata
  labels:                <- child of metadata
    app: frontend        <- child of labels
spec:
  containers:            <- child of spec
  - name: app            <- list item under containers
    image: nginx:1.25    <- field in the same container item
```

A useful mental check is to ask, "What parent owns this line?" If the answer changes unexpectedly after an edit, the YAML structure changed. Moving `image` left or right by two spaces can move it out of the container item or into a different parent. Vim makes that movement easy with `>>` and `<<`, but the learner must still understand what the indentation means.

> **Stop and decide**: In the manifest above, what happens if `image: nginx:1.25` is moved left so it aligns with `- name: app`? Would that still describe an image field for the container, or would it become a different structure?

It would no longer be a normal field inside the same container item. YAML parsers may still parse the file, but Kubernetes schema validation will reject the object because the container item no longer has the expected `image` field in the expected place. This is why `kubectl` validation is part of editing, not a separate step done only at the end.

---

## Part 2: Configure Vim for Kubernetes YAML

A default vim installation is usable, but it is not always friendly to YAML. YAML treats tabs differently from spaces, Kubernetes examples commonly use two-space indentation, and validation errors often include line references. A small `.vimrc` turns those concerns into defaults so each edit starts from a safer baseline.

Run this command in your shell to create a focused vim configuration. The command is runnable as written and uses a quoted heredoc so the shell does not expand anything inside the file.

```bash
cat << 'EOF' > ~/.vimrc
" Kubernetes YAML editing defaults
set number
set tabstop=2
set softtabstop=2
set shiftwidth=2
set expandtab
set autoindent
set smartindent
set cursorline
set hlsearch
syntax on

" Make hidden whitespace easier to inspect when needed.
set listchars=tab:>-,trail:.,extends:>,precedes:<

" YAML files should always use spaces and two-space indentation.
autocmd FileType yaml setlocal tabstop=2 softtabstop=2 shiftwidth=2 expandtab
autocmd FileType yml setlocal tabstop=2 softtabstop=2 shiftwidth=2 expandtab
EOF
```

This configuration does not turn vim into an integrated development environment. It makes the invisible parts of YAML less risky. `set number` gives you a coordinate system for parser errors. `set expandtab` means pressing the Tab key inserts spaces instead of a literal tab character. `set shiftwidth=2` means indentation commands like `>>` and `<` move by the same width Kubernetes examples expect.

| Setting | Why It Matters for YAML | Failure It Prevents |
|---------|--------------------------|---------------------|
| `set number` | Shows line numbers beside the file | Hunting blindly for parser error locations |
| `set tabstop=2` | Displays tab width as two columns | Misreading visual alignment during inspection |
| `set softtabstop=2` | Makes Tab and Backspace feel like two-space steps | Awkward partial indentation edits |
| `set shiftwidth=2` | Makes `>>`, `<<`, and visual indentation move two spaces | Over-indenting blocks by large jumps |
| `set expandtab` | Converts Tab key presses into spaces | Literal tab characters breaking YAML indentation |
| `set autoindent` | Carries current indentation onto new lines | Rebuilding nested indentation from scratch |
| `set cursorline` | Highlights the current line | Editing the wrong line in dense manifests |
| `set hlsearch` | Highlights search matches | Missing repeated image or label values |

> **Pause and explain**: Why is `tabstop=2` not enough by itself? Predict what happens if the file contains a real tab character and another machine displays tabs using a different width.

`tabstop=2` only changes how a tab is displayed. It does not stop vim from inserting a tab character unless `expandtab` is also enabled. YAML cares about actual characters, not your visual preference, so a manifest can look aligned in one terminal and fail or mislead you in another. `expandtab` changes what gets written to the file, which is the behavior Kubernetes validation sees.

### 2.1 Verify the Configuration Instead of Trusting It

A senior workflow verifies assumptions. After writing `.vimrc`, open a scratch YAML file, press Tab at the start of a line, save, and inspect the file with tools that expose hidden characters. This short check proves that your editor is writing spaces, not just displaying something that looks like spaces.

```bash
cat << 'EOF' > vimrc-check.yaml
apiVersion: v1
kind: Pod
metadata:
  name: vimrc-check
spec:
  containers:
  - name: app
    image: nginx:1.25
EOF

vim vimrc-check.yaml
cat -A vimrc-check.yaml
rm -f vimrc-check.yaml
```

In `cat -A` output, literal tab characters usually appear as `^I`. If you see `^I` inside indentation, replace the tabs or fix your editor settings before doing serious YAML work. If you see `$` at line endings, that is normal; `cat -A` uses it to show where each line ends.

There is also a vim-side inspection method. Inside vim, run `:set list` to show tabs and trailing spaces using the `listchars` configuration. Run `:set nolist` when you are done inspecting. This is useful when a manifest looks fine in normal view but validation keeps pointing toward whitespace-sensitive areas.

### 2.2 The Paste Mode Trade-Off

Old terminal vim setups can mis-handle pasted blocks when autoindent is active. Paste mode temporarily disables some automatic formatting so vim accepts pasted text more literally. The trade-off is that paste mode also disables some helpful insert behavior, so it should be turned off after the paste.

```text
:set paste
```

Paste the YAML block only after paste mode is active, then pause before saving so you can check whether the indentation still matches the parent-child structure you intended. This small pause catches the common case where pasted documentation includes leading spaces from a web page, wrapped lines from a terminal, or fields copied from a different context.

```text
:set nopaste
```

You should treat paste mode as a tool, not a permanent configuration. If it stays enabled, normal typing may feel less helpful because automatic indentation behavior changes. A clean exam habit is to enter paste mode immediately before a paste, paste once, leave paste mode, save, and validate.

Modern terminal bracketed paste support often reduces this problem, but the exam-safe principle remains the same: after any pasted YAML, validate the result. Pasted manifests may include tabs, non-breaking spaces, long wrapped lines, or fields from a different API version. Editor safety reduces risk; `kubectl` validation confirms the object.

---

## Part 3: Create, Edit, and Validate a Manifest in a Tight Loop

The fastest Kubernetes editing workflow is not "write everything perfectly the first time." The fastest workflow is a tight loop: generate or open a manifest, make a small edit, save, validate, and fix the next concrete error. This loop turns vague anxiety into specific feedback from the Kubernetes client.

In this module, the first full worked example creates a Pod manifest, intentionally changes it, validates it, and then repairs it. Every runnable shell block uses the full `kubectl` command name because copied exam notes, shell scripts, and non-interactive shells cannot assume that an interactive shortcut exists. Some engineers use a short local alias during daily work, but the portable habit is to write commands that remain correct when pasted into a fresh terminal.

```bash
kubectl version --client
```

That quick client check is also a useful reminder that these examples target modern Kubernetes behavior, including the Kubernetes 1.35 exam era where `kubectl` dry-run and generated reference pages remain central to fast manifest work. If the command itself is unavailable, fix the environment before practicing editor recovery because validation is the feedback loop that makes the rest of the module useful.

### 3.1 Worked Example: Add a Label and Validate the Pod

Start with a known-good manifest. Creating a valid baseline before making edits is a professional habit because it separates "my starting point is bad" from "my latest edit broke something." The file below is intentionally small so the edit mechanics stay visible.

```bash
cat << 'EOF' > pod-edit.yaml
apiVersion: v1
kind: Pod
metadata:
  name: pod-edit
spec:
  containers:
  - name: app
    image: nginx:1.25
EOF

kubectl apply -f pod-edit.yaml --dry-run=client
```

Now open the file in vim and treat the first edit as a controlled experiment rather than a free-form typing session. The file is valid before you touch it, so any validation failure after the next save should point directly toward the label block you just added.

```bash
vim pod-edit.yaml
```

Press `Esc` to ensure you are in Normal mode, then move to the `metadata:` line. Press `o` to open a new line below it and enter Insert mode. Type the label block below, preserving two-space indentation under `metadata` and four-space indentation under `labels`.

```yaml
  labels:
    app: web
```

Press `Esc`, type `:wq`, and press `Enter`, then validate the file again before making any other changes. The immediate validation step is what turns vim editing into an engineering loop: one change, one check, one clear result.

```bash
kubectl apply -f pod-edit.yaml --dry-run=client
```

The important teaching point is not the label itself. The important point is the sequence. You started from valid YAML, made one structural edit, saved, and validated. When this loop fails, the search space is small. The error is probably in the block you just changed, not somewhere random in the manifest.

### 3.2 Worked Example: Recover from a Bad Indentation Edit

Now create a broken version deliberately. This kind of deliberate breakage is useful because it lets you practice the recovery path before the exam creates the pressure for you.

```bash
cat << 'EOF' > broken-pod-edit.yaml
apiVersion: v1
kind: Pod
metadata:
  name: broken-pod-edit
labels:
    app: web
spec:
  containers:
  - name: app
    image: nginx:1.25
EOF

kubectl apply -f broken-pod-edit.yaml --dry-run=client
```

This file may parse as YAML, but it does not describe the intended Kubernetes object. The `labels` field is aligned at the top level instead of living under `metadata`. [Kubernetes expects labels under `metadata.labels`](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/), so the fix is structural: move `labels:` two spaces to the right and `app: web` so it remains a child of `labels`.

Open the file and repair it with a structural edit instead of manually tapping spaces on each line. Because both affected lines belong to the same misplaced label block, selecting them together is faster and less error-prone than editing their indentation independently.

```bash
vim broken-pod-edit.yaml
```

One efficient repair path is to use visual line selection so the two related lines move as a unit. That approach preserves their relationship to each other while changing their relationship to the surrounding `metadata` block, which is exactly what the broken manifest needs.

1. Press `Esc` to enter Normal mode.
2. Move to the `labels:` line.
3. Press `V` to select the current line.
4. Press `j` once to include `app: web`.
5. Press `>` once to indent both selected lines by `shiftwidth`, which your `.vimrc` set to two spaces.
6. Press `Esc`, type `:wq`, and press `Enter`.

Validate the repair immediately after saving so you know whether the indentation change moved the labels under the intended parent. If validation still fails, reopen the same small area instead of scanning the whole file from the top.

```bash
kubectl apply -f broken-pod-edit.yaml --dry-run=client
rm -f pod-edit.yaml broken-pod-edit.yaml
```

This is the difference between beginner and practitioner editing. A beginner stares at the parser output and nudges spaces manually. A practitioner identifies the parent-child relationship, selects the affected block, applies a controlled indentation operation, and validates the object immediately.

### 3.3 Editing Decision Matrix

Not every task deserves the same editing approach. In a timed exam, the correct tool is the one that safely produces the desired manifest with the least cognitive overhead. Vim is excellent for modifying existing files and repairing structure. Shell redirection is often faster for creating a tiny file from scratch. `kubectl create` or `kubectl run` with `--dry-run=client -o yaml` can generate a correct skeleton faster than memory can.

| Situation | Best Starting Tool | Why This Is Usually Fastest |
|-----------|--------------------|-----------------------------|
| Create a simple Pod from scratch | `kubectl run ... --dry-run=client -o yaml` | Kubernetes generates valid structure and API fields |
| Edit an existing manifest | `vim file.yaml` | You can preserve most structure and change only the target fields |
| Paste a long documentation snippet | `vim` with paste discipline or heredoc | You can inspect and validate after paste |
| Replace repeated image tags | vim search and replace | One command changes every repeated value consistently |
| Remove a broken YAML block | vim visual selection or counted delete | Line-oriented edits match YAML block structure |
| Create a short scratch file | `cat << 'EOF' > file.yaml` | Avoids editor overhead for small known content |

The decision matrix is not a rulebook. It is a way to reduce wasted motion. If `kubectl` can generate an object skeleton, let it. If the file already exists, edit it. If the edit is repeated across the file, use search and replace. If you are unsure whether the result is valid, validate before moving to the next task.

---

## Part 4: Refactor YAML Blocks Without Retyping

Retyping YAML is slow and error-prone because indentation carries meaning. Kubernetes manifests often contain repeated structures: multiple containers, several environment variables, several ports, several volume mounts, and repeated labels. Vim's copy, paste, visual selection, indentation, and search commands let you transform those structures without rebuilding them character by character.

The key is to copy a complete semantic block. Copying only part of a list item creates broken structure. Copying too much may duplicate fields that must remain unique. Before pressing `yy`, `V`, or `p`, identify the smallest complete block that represents the Kubernetes object part you want to duplicate.

```yaml
env:
- name: LOG_LEVEL
  value: info
- name: FEATURE_FLAG
  value: "true"
```

In the example above, each environment variable item is two lines. Copying only `- name: FEATURE_FLAG` creates a variable with no value. Copying only `value: "true"` creates a value with no name. Copying both lines preserves the list item, and then you can edit the duplicated name and value.

### 4.1 Duplicate a Container Block

Create a Pod with one container so the block you duplicate has a small, visible boundary. Starting with a compact object makes it easier to practice the editing mechanics before you apply the same pattern to larger Deployments with probes, resources, and volume mounts.

```bash
cat << 'EOF' > multi-container-edit.yaml
apiVersion: v1
kind: Pod
metadata:
  name: multi-container-edit
spec:
  containers:
  - name: app
    image: nginx:1.25
    ports:
    - containerPort: 80
EOF
```

Open the file and identify the complete container item before copying anything. The useful block begins at `- name: app` and includes every child field that should travel with that container.

```bash
vim multi-container-edit.yaml
```

Use this workflow to duplicate the container and convert the copy into a sidecar. The sequence deliberately copies a complete YAML list item first and then removes fields that do not belong in the sidecar, which is safer than trying to assemble the second container from memory.

1. Press `Esc`.
2. Move to the `- name: app` line.
3. Press `V` to start visual line selection.
4. Press `j` three times to include `image`, `ports`, and `containerPort`.
5. Press `y` to yank the selected block.
6. Move to the `- containerPort: 80` line.
7. Press `p` to paste the copied block below.
8. Edit the pasted block so the second container is named `sidecar` and uses `busybox:1.36`.
9. Delete the copied `ports` lines from the sidecar with `2dd`.
10. Save with `:wq`.

The expected result is a Pod with two entries under the same `containers:` list. Notice that the second `- name` aligns with the first one, while `image` remains indented as a child field of the sidecar container.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: multi-container-edit
spec:
  containers:
  - name: app
    image: nginx:1.25
    ports:
    - containerPort: 80
  - name: sidecar
    image: busybox:1.36
```

Validate and clean up only after inspecting that alignment, because a manifest can look almost correct while placing the second container under the wrong parent. The dry-run confirms the API shape, and the cleanup keeps later drills from reusing stale files.

```bash
kubectl apply -f multi-container-edit.yaml --dry-run=client
rm -f multi-container-edit.yaml
```

> **Active learning checkpoint**: Before validating, predict whether the sidecar needs its own `ports` field. Explain your reasoning in terms of the Pod schema rather than the editor command you used.

The sidecar does not need a `ports` field unless you want to document or expose a container port. A container item can be valid with only a name and image. The editor step duplicated `ports` because it was part of the copied block, but Kubernetes design determines whether that field belongs in the final manifest.

### 4.2 Search and Replace Without Creating Collateral Damage

Search and replace is powerful because it compresses repeated edits into one command. It is also risky because an overly broad pattern changes text you did not intend to touch. The professional move is to search first, inspect matches, and then replace with the narrowest pattern that expresses the intended change.

Create a Deployment with repeated image tags so search and replace has a realistic risk profile. The point is not merely to change text quickly; the point is to change the one value the task requested while proving that similar-looking values stayed untouched.

```bash
cat << 'EOF' > version-replace.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: version-replace
spec:
  replicas: 2
  selector:
    matchLabels:
      app: version-replace
  template:
    metadata:
      labels:
        app: version-replace
    spec:
      containers:
      - name: web
        image: nginx:1.25
      - name: metrics
        image: busybox:1.36
        command: ["sh", "-c", "sleep 3600"]
EOF
```

Open the file and search before replacing, because the match list tells you whether a global edit would be safe. In a real manifest, the same number can appear in labels, annotations, image tags, command arguments, and comments, and not all of those occurrences mean the same thing.

```bash
vim version-replace.yaml
```

Inside vim, run the search first and move through the matches with `n` until you can describe exactly which lines would be affected. That preview step is the difference between a deliberate replacement and a broad text mutation.

```text
/image:
```

Press `n` to move through image lines. If the task is to change only the nginx image tag, the broad pattern `:%s/1.25/1.26/g` may be acceptable in this file, but `:%s/nginx:1.25/nginx:1.26/g` is safer because it ties the replacement to the image name. In larger manifests, that extra specificity prevents accidental edits to unrelated version fields.

```text
:%s/nginx:1.25/nginx:1.26/g
```

Save, validate, and clean up after checking the replacement with a normal shell command. The validation step catches YAML and schema mistakes, while the `grep` inspection catches the intent mistake of changing too much or too little.

```bash
kubectl apply -f version-replace.yaml --dry-run=client
grep "nginx:1.26" version-replace.yaml
rm -f version-replace.yaml
```

Search and replace should be followed by inspection when the change touches production-like configuration. In the exam, validation often suffices for syntax and schema, but it cannot always prove intent. A Deployment can be valid while pointing to the wrong image. That is why the `grep` check is included after validation.

### 4.3 Delete Blocks by Structure, Not by Panic

Deleting a block is common when removing an incorrect `volumeMount`, `env`, `resources`, or `ports` section. The mistake is to mash Delete or Backspace in Insert mode until the file "looks better." That approach often leaves orphaned list items or fields under the wrong parent. Vim gives you cleaner options.

Create a Pod with an intentionally unwanted environment variable so the delete operation has a clear semantic target. The variable is a two-line list item, which lets you practice deleting a complete YAML unit rather than erasing visible characters until the screen looks quieter.

```bash
cat << 'EOF' > delete-block.yaml
apiVersion: v1
kind: Pod
metadata:
  name: delete-block
spec:
  containers:
  - name: app
    image: nginx:1.25
    env:
    - name: KEEP_ME
      value: stable
    - name: REMOVE_ME
      value: temporary
EOF
```

Open the file and move to the first line of the item you want to remove. Before typing the delete command, check the next line so you know the count represents the whole variable and nothing more.

```bash
vim delete-block.yaml
```

The block to delete is exactly two lines: `- name: REMOVE_ME` and `value: temporary`. Move to the `- name: REMOVE_ME` line, press `Esc`, and type:

```text
2dd
```

Save and validate once the two-line item is gone, then inspect the remaining `env:` list if validation reports a nearby problem. A clean delete should leave `KEEP_ME` as a complete list item and should not leave a dangling `value` field behind.

```bash
kubectl apply -f delete-block.yaml --dry-run=client
rm -f delete-block.yaml
```

If you accidentally delete both environment variables, press `u` immediately. Do not attempt to reconstruct from memory before using undo. Undo is faster and more accurate than retyping, especially when the surrounding structure has similar-looking list items.

---

## Part 5: Diagnose YAML Failures Like an Operator

A YAML failure can come from three different layers. The file can be invalid YAML, meaning the parser cannot read it. The file can be valid YAML but invalid Kubernetes, meaning the object does not match the API schema. The object can be valid Kubernetes but wrong for your intent, meaning it applies successfully but does not do what the task requires.

Distinguishing those layers is a senior skill because it prevents random editing. Parser errors point toward syntax and indentation. Schema errors point toward field names, field types, API versions, or object structure. Intent errors require comparing the manifest against the task, the running object, or the behavior you expected.

```text
+----------------------+     +------------------------+     +----------------------+
| YAML PARSER          | --> | KUBERNETES SCHEMA      | --> | OPERATOR INTENT      |
| Can the file be read?|     | Is this object valid?  |     | Is this the right    |
| spaces, colons, tabs |     | fields, types, apiVersion |  | behavior for task?  |
+----------------------+     +------------------------+     +----------------------+
```

A useful troubleshooting loop is to start with the cheapest check. Save the file. Run client-side dry-run. Read the first error carefully. Open the file at the referenced line if one is provided. Fix one cause. Save and dry-run again. Repeating this loop beats making several speculative changes because each validation run gives you a smaller, clearer problem.

```bash
kubectl apply -f some-file.yaml --dry-run=client
```

### 5.1 Parser Error: Hidden Tabs

Create a file that contains tabs. The file may look reasonable when printed normally, which is precisely why hidden-character inspection matters.

```bash
printf 'apiVersion: v1\nkind: Pod\nmetadata:\n\tname: tab-pod\nspec:\n\tcontainers:\n\t- name: app\n\t  image: nginx:1.25\n' > tabs-pod.yaml

cat tabs-pod.yaml
cat -A tabs-pod.yaml
kubectl apply -f tabs-pod.yaml --dry-run=client
```

Open the file in vim and inspect it with whitespace visibility in mind. The normal view may make the tabs look like acceptable indentation, so this repair is really about changing the bytes in the file rather than trusting what the terminal happens to display.

```bash
vim tabs-pod.yaml
```

Inside vim, replace tabs with two spaces, then review the affected block before saving. A mechanical tab replacement is usually right for this small example, but larger files can still need parent-child inspection afterward because tabs may have represented different visual widths.

```text
:%s/\t/  /g
```

Save, validate, and remove the file only after the parser and schema checks agree with the repaired structure. If validation still complains, use line numbers and `:set list` to inspect the smallest area around the reported error.

```bash
kubectl apply -f tabs-pod.yaml --dry-run=client
rm -f tabs-pod.yaml
```

The search pattern `\t` means a literal tab character. The replacement contains two spaces. This works because the intended indentation level in the sample advances by two spaces. In a more complex file, replacing tabs mechanically may not be enough if the tabs represented different visual widths, so inspect the parent-child structure after replacing.

### 5.2 Schema Error: Correct YAML, Wrong Field Shape

A file can be perfectly valid YAML and still fail Kubernetes validation. That happens when the structure is readable but the object does not match the Kubernetes API. For CKA work, this is common when list items are placed under the wrong parent, strings are used where integers are expected, or a field belongs in `template.spec` but is placed under the Deployment's top-level `spec`.

Create an example with a wrong `containerPort` type to practice separating YAML validity from Kubernetes API validity. The file is intentionally readable as YAML, so the interesting failure comes from the schema expecting an integer at that field path.

```bash
cat << 'EOF' > schema-error.yaml
apiVersion: v1
kind: Pod
metadata:
  name: schema-error
spec:
  containers:
  - name: app
    image: nginx:1.25
    ports:
    - containerPort: "80"
EOF

kubectl apply -f schema-error.yaml --dry-run=client
```

Open the file and remove the quotes around the integer, then compare that fix with the environment-variable examples earlier in the module. The same visual edit can be right in one field and wrong in another because Kubernetes schema, not personal style, defines the expected type.

```bash
vim schema-error.yaml
```

The corrected block should keep the `ports` list structure unchanged while changing only the scalar type of `containerPort`. That narrow repair demonstrates good troubleshooting discipline: preserve everything that is already correct and touch only the field the error identifies.

```yaml
    ports:
    - containerPort: 80
```

Validate and clean up after the type correction so the exercise ends with a confirmed-good file rather than an assumed-good file. This habit matters during the CKA because a later task can build on a manifest you edited minutes earlier.

```bash
kubectl apply -f schema-error.yaml --dry-run=client
rm -f schema-error.yaml
```

The lesson is not that quotes are always bad. Many Kubernetes fields are strings and should be quoted when values look like booleans, numbers, or URLs. The lesson is that Kubernetes schema determines the expected type. [`containerPort` is an integer; environment variable `value` is a string.](https://kubernetes.io/zh-cn/docs/reference/kubernetes-api/workload-resources/pod-v1/) Good editing means knowing when YAML syntax and Kubernetes schema are separate concerns.

### 5.3 Intent Error: Valid Object, Wrong Location

Intent errors are the most subtle because validation can pass. Suppose a task asks you to add a label to the Pod template of a Deployment, but you add it only to the Deployment object metadata. The YAML is valid, the Kubernetes object is valid, and the command may succeed, but the ReplicaSet selector or Pod labels may not behave as required.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: label-location
  labels:
    app: web
spec:
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
        tier: frontend
    spec:
      containers:
      - name: web
        image: nginx:1.25
```

The `metadata.labels` near the top describes the Deployment object. The `spec.template.metadata.labels` block describes Pods created by the Deployment. Editing the wrong label block can leave the application behavior unchanged even though the manifest applies. When tasks mention Pods created by a Deployment, service selection, or rollout behavior, inspect the template block before editing.

> **What would happen if** you changed only the top-level `metadata.labels.app` to `api` but left `spec.selector.matchLabels.app` and `spec.template.metadata.labels.app` as `web`? Would the Deployment still create Pods selected by its own selector?

The Deployment could remain structurally valid because the top-level object label is independent from the Pod selector relationship. [The Pods would still be selected based on the selector and template labels](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/), both of which remain `web`. This is a classic valid-but-wrong edit: the field changed, but not the field that controlled the required behavior.

---

## Part 6: Exam-Speed Editing Patterns

Exam-speed editing is about reducing decisions. When a task begins, choose a pattern quickly: generate then edit, open then patch, copy then modify, search then replace, or abandon a bad edit and regenerate. Each pattern has a small command sequence. Practicing those sequences makes the editor fade into the background.

The most useful pattern for resource creation is generate then edit. For example, you can ask Kubernetes to [produce a Pod skeleton and send it to a file](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_run/), then use vim to add labels, ports, resources, or environment variables. This avoids memorizing every field placement from scratch.

```bash
kubectl run generated-web --image=nginx:1.25 --dry-run=client -o yaml > generated-web.yaml
vim generated-web.yaml
kubectl apply -f generated-web.yaml --dry-run=client
rm -f generated-web.yaml
```

The most useful pattern for repair is open then patch. You already have a failing manifest, so the task is to inspect the error, open the file at the right area, fix one structural issue, save, and validate. Resist rewriting the whole file unless the object is tiny. Large rewrites create new errors and erase useful structure.

```bash
kubectl apply -f broken.yaml --dry-run=client
vim broken.yaml
kubectl apply -f broken.yaml --dry-run=client
```

The most useful pattern for repeated value changes is search then replace. Search first, replace narrowly, validate, and inspect the changed lines. When the value appears in labels, selectors, names, and images, do not blindly replace every occurrence unless the task truly asks for that global change.

```text
/nginx
:%s/nginx:1.25/nginx:1.26/g
```

The most useful pattern for a bad paste is undo then paste safely. If a pasted block explodes into stair-step indentation, press `Esc`, press `u`, enable paste mode, paste again, disable paste mode, save, and validate. Do not manually repair twenty shifted lines if undo can return the file to a clean pre-paste state.

```text
Esc
u
:set paste
```

Paste the block, then leave paste mode before you continue typing normal YAML. Paste mode is a temporary guardrail, and leaving it on can make later insert behavior feel inconsistent when you are trying to make a precise small edit.

```text
:set nopaste
:w
```

### 6.1 Nano as a Valid Fallback

Nano is a valid editor for the CKA if it is available and you are faster with it. The goal is not to prove vim superiority. The goal is to produce correct manifests under time pressure. Nano's visible shortcut bar can reduce mode confusion, but vim's Normal mode operations are faster for block edits once learned.

Create a minimal nano configuration if nano is your chosen fallback, and hold it to the same YAML standards as vim. A simpler editor interface does not remove the need for spaces, line numbers, validation, and deliberate parent-child inspection.

```bash
cat << 'EOF' > ~/.nanorc
set tabsize 2
set tabstospaces
set autoindent
set linenumbers
EOF
```

Nano basics are straightforward: `Ctrl+O` writes the file, `Enter` confirms the file name, and `Ctrl+X` exits. `Ctrl+K` cuts a line, and `Ctrl+U` pastes it. If you choose nano for the exam, practice the same edit-validate loop. Editor choice changes keystrokes; it does not change YAML structure, Kubernetes schema, or the need to validate.

The practical recommendation is to choose one primary editor before the exam and one fallback. If vim mode errors still consume attention after practice, use nano for simple tasks and reserve vim for environments where nano is missing. If block editing feels natural in vim, use vim consistently. Switching editors during a stressful task often costs more time than it saves.

---

## Did You Know?

- **[Vim is often present on minimal Linux systems](https://github.com/vim/vim)** because it is small, terminal-native, and useful over SSH. That makes the skill portable beyond the CKA exam, especially during production troubleshooting sessions where graphical tools are unavailable.
- **YAML indentation is semantic, not cosmetic**. Moving a line two spaces can change which parent owns that field, even when the file still parses successfully.
- **`vimtutor` is an interactive practice tool** installed with many vim packages. Running `vimtutor` for half an hour teaches movement, editing, undo, search, and save habits in a guided environment.
- **Client-side dry-run is an editing companion**. [`kubectl apply --dry-run=client -f file.yaml` can catch many syntax and schema errors](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/) before you spend time applying a broken object to the cluster.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|---------|----------|
| Typing commands while still in Insert mode | `:wq`, `dd`, or search text appears inside the YAML file | Press `Esc` first, then run the command from Normal mode |
| Trusting visual alignment when tabs are present | The file looks aligned but YAML or Kubernetes validation fails | Use `set expandtab`, inspect with `cat -A`, or run `:%s/\t/  /g` carefully |
| Pasting long YAML without paste discipline | Autoindent or terminal behavior can create cascading indentation changes | Use `:set paste`, paste once, run `:set nopaste`, save, and validate |
| Replacing a broad pattern globally | Labels, selectors, names, or unrelated versions change accidentally | Search first, use a narrow replacement pattern, then inspect changed lines |
| Deleting partial YAML blocks | Orphaned fields remain under the wrong parent and create schema errors | Delete complete list items or field blocks with visual selection or counted deletes |
| Adding fields to the wrong object level | The manifest validates but does not change the intended Pods or workload behavior | Identify the parent path, especially `metadata` versus `spec.template.metadata` |
| Skipping validation after a small edit | A tiny indentation or type error is discovered only after more changes pile up | Save and run `kubectl apply -f file.yaml --dry-run=client` after each meaningful edit |
| Leaving paste mode enabled | Normal typing and indentation behavior feel wrong after a paste | Run `:set nopaste` immediately after the pasted block is in place |

---

## Quiz

<details>
<summary>Scenario: Your Deployment manifest fails after you add an environment variable. The error points near the `env:` block, and you notice the new variable has `value: true` without quotes. The task requires the application to receive the literal string `true`. What should you change, and how would you validate the fix?</summary>

Change the value to `value: "true"` because environment variable values in Kubernetes are strings, and an unquoted YAML boolean can be interpreted as a boolean before schema validation. Save the file and run `kubectl apply -f deployment.yaml --dry-run=client`. If validation passes, inspect the relevant block to confirm you changed the environment variable value, not a different field with similar text. This answer works because it separates YAML parsing from Kubernetes schema rules and then confirms that the intended field changed.
</details>

<details>
<summary>Scenario: You paste a Pod manifest into vim during the exam, and every nested line shifts farther right than the previous line. You have not saved yet. What recovery sequence minimizes risk, and why is it better than manually moving lines left?</summary>

Press `Esc`, then `u` to undo the bad paste. Run `:set paste`, paste the manifest again, then run `:set nopaste`, save, and validate with `kubectl apply -f file.yaml --dry-run=client`. This is safer than manual repair because undo restores the last known clean state, while manually shifting many lines can introduce new parent-child mistakes. The reasoning is operational: when the file is still unsaved, preserving a known-good buffer state is faster than repairing uncertain indentation by hand.
</details>

<details>
<summary>Scenario: A Service is not selecting Pods after you edit a Deployment. The Deployment YAML validates successfully. You changed `metadata.labels.app` at the top of the Deployment but did not inspect `spec.template.metadata.labels` or the Service selector. What should you compare, and what editor workflow helps you avoid missing the right block?</summary>

Compare the Service selector with the Pod template labels under `spec.template.metadata.labels`, not just the Deployment object's top-level labels. In vim, search for `labels:` and move through each match with `n`, checking the parent path around each label block. This avoids a valid-but-wrong edit where the object metadata changes but the Pods still carry the old label. The important distinction is that validation proves the object is acceptable to the API, not that the edited label controls the workload behavior you intended.
</details>

<details>
<summary>Scenario: You need to remove one environment variable from a container. The variable is represented by two lines, `- name: DEBUG` and `value: "true"`. What vim command can remove it efficiently, and what should you verify afterward?</summary>

Move to the `- name: DEBUG` line in Normal mode and type `2dd`. Then validate with `kubectl apply -f file.yaml --dry-run=client` and inspect the surrounding `env:` list to confirm no orphaned `value` line remains. The command is efficient because it deletes the complete two-line list item rather than characters inside it. If the wrong lines disappear, undo immediately with `u` before attempting a manual reconstruction.
</details>

<details>
<summary>Scenario: You run `cat -A pod.yaml` and see `^I` before several YAML fields. The file looked aligned in vim, but `kubectl` reports a parsing problem. What is the likely root cause, and how can vim repair it?</summary>

`^I` indicates literal tab characters. YAML indentation should use spaces, and visual alignment can be misleading when tabs are displayed with a convenient width. In vim, run `:%s/\t/  /g` to replace tabs with two spaces, then inspect the structure and validate again. For prevention, use `set expandtab`, `set softtabstop=2`, and `set shiftwidth=2` in `~/.vimrc`, because those settings change what the editor writes instead of only changing how indentation appears.
</details>

<details>
<summary>Scenario: A task asks you to update only the nginx image from `nginx:1.25` to `nginx:1.26`. The same file also contains `busybox:1.25` in a sidecar. Why is `:%s/1.25/1.26/g` risky, and what command is safer?</summary>

The broad command changes every `1.25` occurrence, including the busybox sidecar if it uses the same tag. A safer command is `:%s/nginx:1.25/nginx:1.26/g` because it ties the replacement to the exact image that the task mentions. After saving, search for `image:` or use `grep` to verify that only the intended image changed. Kubernetes validation cannot prove this intent by itself because both image tags can be syntactically and structurally valid.
</details>

<details>
<summary>Scenario: You generated a Pod manifest with `kubectl run --dry-run=client -o yaml`, opened it in vim, and added a `ports` block. Validation now says `containerPort` has the wrong type. The line reads `containerPort: "80"`. How do you reason about the fix?</summary>

The file is readable YAML, but Kubernetes schema expects `containerPort` to be an integer, not a string. Remove the quotes so the line reads `containerPort: 80`, save, and run `kubectl apply -f file.yaml --dry-run=client`. The reasoning separates YAML syntax from Kubernetes API schema: quoted strings can be valid YAML while still being wrong for a specific Kubernetes field. The same logic explains why environment variable values often need quotes even though port numbers do not.
</details>

---

## Hands-On Exercise

**Task**: Configure vim, repair broken Kubernetes YAML, and practice the edit-validate loop until you can make structural changes without retyping whole files.

This exercise uses client-side dry-run so you can practice without creating live resources. If your environment has no cluster context, most client-side schema checks still work for built-in resources, but exact behavior can vary by kubectl version and local configuration. The main skill is the loop: edit a small section, save, validate, interpret feedback, and repeat.

### Step 1: Install the editing baseline

Create a vim configuration for Kubernetes YAML before you begin editing manifests. This step gives the editor the same assumptions the rest of the exercise depends on: two-space indentation, spaces instead of literal tabs, line numbers for navigation, and visible whitespace controls when a file behaves strangely.

```bash
cat << 'EOF' > ~/.vimrc
set number
set tabstop=2
set softtabstop=2
set shiftwidth=2
set expandtab
set autoindent
set smartindent
set cursorline
set hlsearch
syntax on
set listchars=tab:>-,trail:.,extends:>,precedes:<
autocmd FileType yaml setlocal tabstop=2 softtabstop=2 shiftwidth=2 expandtab
autocmd FileType yml setlocal tabstop=2 softtabstop=2 shiftwidth=2 expandtab
EOF
```

Success criteria for this step:

- [ ] `~/.vimrc` exists.
- [ ] The file contains `set expandtab`.
- [ ] The file contains `set shiftwidth=2`.
- [ ] The file contains `set number`.

### Step 2: Create a valid baseline manifest

Create a simple Pod manifest from the shell, then validate it before editing so you have a known-good starting point. When a baseline validates first, the next failure belongs to your edit rather than to a typo in the initial file.

```bash
cat << 'EOF' > exercise-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: exercise-pod
spec:
  containers:
  - name: app
    image: nginx:1.25
EOF

kubectl apply -f exercise-pod.yaml --dry-run=client
```

Success criteria for this step:

- [ ] `exercise-pod.yaml` exists.
- [ ] `kubectl apply -f exercise-pod.yaml --dry-run=client` succeeds.
- [ ] You can explain why validating before editing gives you a clean baseline.

### Step 3: Add metadata labels in vim

Open the file and navigate to the `metadata:` block before typing any YAML. Your goal is to add labels as children of `metadata`, not as top-level fields beside it.

```bash
vim exercise-pod.yaml
```

Add this block under `metadata:` with two spaces before `labels:` and four spaces before each label key. The indentation is the lesson here: the label names must be children of `labels`, and `labels` must be a child of `metadata`.

```yaml
  labels:
    app: exercise
    tier: web
```

Save and validate after the label edit so the exercise checks both syntax and Kubernetes object shape. If dry-run fails, reopen the exact label area and compare its indentation with the expected parent-child structure.

```bash
kubectl apply -f exercise-pod.yaml --dry-run=client
```

Success criteria for this step:

- [ ] `labels:` is indented under `metadata:`.
- [ ] `app` and `tier` are indented under `labels:`.
- [ ] Client-side dry-run succeeds after the edit.
- [ ] You used `Esc` and `:w` or `:wq` rather than closing the terminal.

### Step 4: Duplicate and modify a YAML block

Open the file again and locate the existing container block as a complete list item. You should be able to say where the item starts, where it ends, and which child fields belong to it before you copy anything.

```bash
vim exercise-pod.yaml
```

Duplicate the existing container block and modify the copy so the Pod has a second container. Copying structure first and editing values second is faster than retyping the list item, but only if the pasted block stays aligned with the original `- name` line.

```yaml
  - name: sidecar
    image: busybox:1.36
    command: ["sh", "-c", "sleep 3600"]
```

Save and validate after the sidecar edit, then read any error as feedback about structure rather than as a sign that vim failed you. A common mistake is to paste the sidecar under the first container's child fields, which changes the YAML shape even though the text looks close.

```bash
kubectl apply -f exercise-pod.yaml --dry-run=client
```

Success criteria for this step focus on list membership and field ownership. The sidecar should be a peer of the app container, and its `command` field should remain a child of the sidecar item.

- [ ] The second container is under the same `containers:` list as the first container.
- [ ] The sidecar has its own `- name` line.
- [ ] The command remains on one YAML line and validates.
- [ ] You copied and modified structure instead of retyping the whole manifest.

### Step 5: Repair a manifest with tabs and wrong types

Create a broken file that combines hidden tabs with a schema type problem. This gives you a compact diagnostic exercise where one tool exposes invisible characters and `kubectl` validation explains what the Kubernetes API expects.

```bash
printf 'apiVersion: v1\nkind: Pod\nmetadata:\n\tname: broken-exercise\nspec:\n\tcontainers:\n\t- name: app\n\t  image: nginx:1.25\n\t  ports:\n\t  - containerPort: "80"\n' > broken-exercise.yaml

cat -A broken-exercise.yaml
kubectl apply -f broken-exercise.yaml --dry-run=client
```

Open it in vim and repair the file in two passes: first remove the hidden indentation problem, then fix the field type. Keeping those passes separate makes it easier to explain which layer each repair addressed.

```bash
vim broken-exercise.yaml
```

Repair the file so it uses spaces for indentation and an integer for `containerPort`. You may use `:%s/\t/  /g` as part of the repair, but inspect the resulting structure before saving. The corrected file should look like this:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: broken-exercise
spec:
  containers:
  - name: app
    image: nginx:1.25
    ports:
    - containerPort: 80
```

Validate the repair.

```bash
kubectl apply -f broken-exercise.yaml --dry-run=client
```

Success criteria for this step require both byte-level cleanup and schema-level correctness. If `cat -A` still shows `^I`, the editor has not actually removed the tabs, even if the file looks aligned on screen.

- [ ] `cat -A broken-exercise.yaml` no longer shows `^I` in indentation.
- [ ] `containerPort` is an integer, not a quoted string.
- [ ] Client-side dry-run succeeds after repair.
- [ ] You can explain whether the original failure was parser-level, schema-level, or both.

### Step 6: Practice a narrow search and replace

Create a file with two images so the replacement task has a realistic distractor. The busybox line should remain untouched, which means the edit must be narrower than replacing every matching version-looking string.

```bash
cat << 'EOF' > replace-exercise.yaml
apiVersion: v1
kind: Pod
metadata:
  name: replace-exercise
spec:
  containers:
  - name: web
    image: nginx:1.25
  - name: helper
    image: busybox:1.36
    command: ["sh", "-c", "sleep 3600"]
EOF
```

Open the file and replace only the nginx tag with `nginx:1.26`. Search through the image lines before replacing so you know the pattern describes the target image rather than a shared version number.

```bash
vim replace-exercise.yaml
```

Use a narrow replacement pattern that includes both the image name and the old tag. This makes the command resilient when another container happens to use a similar tag for a different image.

```text
:%s/nginx:1.25/nginx:1.26/g
```

Validate and inspect after saving because these checks answer different questions. Dry-run tells you the manifest is acceptable to Kubernetes, while `grep` confirms the specific image lines now match the task.

```bash
kubectl apply -f replace-exercise.yaml --dry-run=client
grep "image:" replace-exercise.yaml
```

Success criteria for this step measure intent preservation as much as syntax. A manifest that validates after changing both images would still be wrong for this task because the helper container was not supposed to change.

- [ ] The nginx image changed to `nginx:1.26`.
- [ ] The busybox image did not change.
- [ ] The manifest validates after replacement.
- [ ] You searched or inspected image lines before considering the task complete.

### Step 7: Clean up practice files

Remove the files created by the exercise so future drills start from fresh manifests instead of accidentally reusing edited state. Cleanup is also a useful exam habit when scratch files have similar names.

```bash
rm -f exercise-pod.yaml broken-exercise.yaml replace-exercise.yaml
```

Success criteria for this step:

- [ ] You can create a Kubernetes YAML file in vim without tabs.
- [ ] You can add nested fields under the correct parent.
- [ ] You can duplicate and modify a list item safely.
- [ ] You can repair hidden tab characters.
- [ ] You can distinguish YAML parser errors from Kubernetes schema errors.
- [ ] You can use dry-run validation after each meaningful edit.
- [ ] You have chosen vim or nano as your primary exam editor and practiced the save/exit sequence for that editor.

---

### Practice Drills

### Drill 1: Two-Minute Pod Edit

Generate a Pod skeleton, add labels, and validate it as a short timed drill. The aim is to make the generate-edit-check loop feel automatic while still preserving the discipline of checking label indentation before you trust the file.

```bash
kubectl run drill-web --image=nginx:1.25 --dry-run=client -o yaml > drill-web.yaml
vim drill-web.yaml
kubectl apply -f drill-web.yaml --dry-run=client
rm -f drill-web.yaml
```

Your target edit is to add `app: drill-web` and `tier: frontend` under `metadata.labels`. The learning goal is not raw speed at first. The learning goal is to avoid putting labels at the wrong indentation level or confusing top-level object labels with Pod template labels in later Deployment work.

### Drill 2: Delete a Broken Block

Create a file with an unwanted environment variable and remove only that complete list item. This drill reinforces the idea that deleting by YAML structure is safer than deleting by visual guesswork.

```bash
cat << 'EOF' > drill-delete.yaml
apiVersion: v1
kind: Pod
metadata:
  name: drill-delete
spec:
  containers:
  - name: app
    image: nginx:1.25
    env:
    - name: KEEP
      value: stable
    - name: REMOVE
      value: temporary
EOF

vim drill-delete.yaml
kubectl apply -f drill-delete.yaml --dry-run=client
rm -f drill-delete.yaml
```

Remove only the `REMOVE` variable. Use a structural delete like `2dd` from the `- name: REMOVE` line. If you remove too much, use `u` before trying anything else.

### Drill 3: Fix Parent-Child Indentation

Create a manifest with misplaced labels and repair the parent-child indentation deliberately. The exercise is small, but the same mistake appears in larger Pod and Deployment manifests whenever labels are added at the wrong object level.

```bash
cat << 'EOF' > drill-indent.yaml
apiVersion: v1
kind: Pod
metadata:
  name: drill-indent
labels:
    app: misplaced
spec:
  containers:
  - name: app
    image: nginx:1.25
EOF

vim drill-indent.yaml
kubectl apply -f drill-indent.yaml --dry-run=client
rm -f drill-indent.yaml
```

Move `labels:` under `metadata:` and move `app: misplaced` under `labels:`. Use visual selection and `>` or `<` if that is faster than manual spaces. Validate after saving.

### Drill 4: Replace One Image Safely

Create a file with multiple containers and change only nginx, then prove the helper image stayed unchanged. This drill keeps search-and-replace honest by pairing the editor command with an inspection command.

```bash
cat << 'EOF' > drill-replace.yaml
apiVersion: v1
kind: Pod
metadata:
  name: drill-replace
spec:
  containers:
  - name: web
    image: nginx:1.25
  - name: helper
    image: busybox:1.36
    command: ["sh", "-c", "sleep 3600"]
EOF

vim drill-replace.yaml
grep "image:" drill-replace.yaml
kubectl apply -f drill-replace.yaml --dry-run=client
rm -f drill-replace.yaml
```

Use a narrow search and replace so only `nginx:1.25` becomes `nginx:1.26`. The post-edit `grep` is part of the drill because schema validation cannot prove you changed only the intended image.

### Drill 5: Nano Fallback

If nano is your backup editor, repeat Drill 1 with nano and compare the result against your vim attempt. The useful measurement is not which editor feels more familiar, but which one helps you produce valid YAML with fewer recovery steps.

```bash
kubectl run nano-drill --image=nginx:1.25 --dry-run=client -o yaml > nano-drill.yaml
nano nano-drill.yaml
kubectl apply -f nano-drill.yaml --dry-run=client
rm -f nano-drill.yaml
```

Use `Ctrl+O`, `Enter`, and `Ctrl+X` to save and exit. Compare your error rate, not just your time. The editor that produces valid YAML consistently is the better exam editor for you.

---

## Sources

- https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/
- https://kubernetes.io/docs/reference/kubectl/generated/kubectl_run/
- https://kubernetes.io/docs/reference/kubectl/conventions/
- https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/
- https://kubernetes.io/docs/concepts/workloads/pods/
- https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/pod-v1/
- https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/deployment-v1/
- https://yaml.org/spec/1.2.2/
- https://vimhelp.org/options.txt.html
- https://vimhelp.org/change.txt.html
- https://www.nano-editor.org/dist/latest/nanorc.5.html
- [kubernetes.io: labels](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/) — The Kubernetes labels documentation explicitly shows labels attached in object metadata via `metadata.labels`.
- [kubernetes.io: kubectl run](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_run/) — The `kubectl run` reference explicitly documents client dry-run and YAML output for printing a generated object without creating it.
- [kubernetes.io: pod v1](https://kubernetes.io/zh-cn/docs/reference/kubernetes-api/workload-resources/pod-v1/) — The official Pod API reference explicitly types `ports.containerPort` as `int32` and `env.value` as `string`.
- [kubernetes.io: deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) — The Deployment documentation explicitly distinguishes `.metadata.labels` from `.spec.template.metadata.labels` and states that `.spec.selector` must match the Pod template labels.
- [github.com: vim](https://github.com/vim/vim) — The official Vim repository README says `vim.tiny` is used by many Linux distributions as the default vi editor and that a small Vim is pre-installed on Mac and Linux.
- [kubernetes.io: kubectl apply](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/) — The `kubectl apply` reference documents client dry-run as printing the object without sending it, and its validation flags explain the validation behavior relevant to this workflow.

## Next Module

[Module 0.4: kubernetes.io Navigation](../module-0.4-k8s-docs/) - Finding documentation fast during the exam.
