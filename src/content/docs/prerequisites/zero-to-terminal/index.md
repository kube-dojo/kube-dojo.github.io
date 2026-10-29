---
title: "Zero to Terminal"
sidebar:
  order: 0
---
> **From "I've never used a terminal" to serving a website and checking it in a browser**

---

## Who Is This Track For?

This track is for **absolute beginners**. No IT or coding background is assumed; use each module's platform guidance and setup notes as you go.

You will need a browser for the interactive labs and website checks, and a terminal appropriate for your operating system; Windows learners should use the modules' WSL guidance where required. The capstone offers two paths: an authorized, preconfigured local Docker Engine 28.0.0 or newer with a local context, or an authorized cloud account and disposable VM, with provider console steps and possible billing. The track does not provision these for you. If a suitable environment is unavailable, you can still read the examples without starting resources; ask your instructor or lab owner for help with setup.

Maybe you're:
- A student curious about technology
- Someone switching careers into tech
- A non-technical person who wants to understand what developers do
- Someone who's been told "just open a terminal" and felt lost

**You are welcome here.** Every expert was once a beginner.

---

## What You'll Learn

By the end of this track, you'll be able to:

- Understand what's happening inside your computer (and why it matters)
- Use the terminal (command line) to navigate, create, and manage files
- Edit files using a text editor right in the terminal
- Understand networking, servers, and how to connect to them remotely
- Know what "the cloud" actually means (spoiler: it's not magic)
- **Use terminal commands to serve a website and check it in a browser**: locally on loopback, or on an authorized cloud VM for a public test

This track leads into the main prerequisites route — **Cloud Native 101** and then **Kubernetes Basics** — with the **Linux** track as an optional systems-internals fork you can take anytime.

### Optional first-terminal preview

Before starting the ordered route, you may preview the existing [terminal opening and prompt guide](module-0.2-what-is-a-terminal/#opening-the-terminal-and-reading-the-prompt) and [first safe-command exercise](module-0.2-what-is-a-terminal/#hands-on-exercise-your-first-terminal-session). Use Module 0.2's own platform guidance. Then return to Module 0.1 and complete the modules in order; the preview does not replace the track.

---

## The Restaurant Kitchen Analogy

Several modules use a **restaurant kitchen** analogy to introduce these terms:

| Computer Concept | Kitchen Equivalent |
|-----------------|-------------------|
| CPU | The chef (does the work) |
| RAM | Counter space (temporary workspace) |
| Disk/SSD | The pantry (long-term storage) |
| Operating System | The restaurant manager |
| Programs | Recipes |
| Terminal | A way to pass written requests to the kitchen |
| Server | A restaurant kitchen (handles requests) |
| Cloud | Renting a commercial kitchen instead of building your own |

Use the kitchen table as an optional orientation aid, not a literal model. A terminal presents a text interface; a shell interprets commands, and permissions control what they can do. CPUs [can have many cores](https://www.apple.com/newsroom/2024/10/apple-introduces-m4-pro-and-m4-max/), not just one chef. A server may be a program serving requests or the computer running it. Cloud services can be public or private, and renting a kitchen does not capture that distinction. Disk storage can outlast a power-off, but can still fail or be lost: keep backups of important data. The technical explanations, platform notes, and exercises give the details; skip the analogy if it obscures them.

---

## Modules

| Module | Title | Time | What You'll Learn |
|--------|-------|------|-------------------|
| 0.1 | [What is a Computer?](module-0.1-what-is-a-computer/) | 90–120 min | CPU, RAM, disk, OS -- the kitchen hardware |
| 0.2 | [What is a Terminal?](module-0.2-what-is-a-terminal/) | 90–120 min | Opening and understanding the terminal |
| 0.3 | [First Terminal Commands](module-0.3-first-commands/) | 80–100 min | Navigate, create, move, and delete files |
| 0.4 | [Files and Directories](module-0.4-files-and-directories/) | 90–120 min | Paths, file types, organizing your filesystem |
| 0.5 | [Editing Files](module-0.5-editing-files/) | 80–100 min | Edit files with nano, write your first script |
| 0.6 | [Git Basics — Track Your Work](module-0.6-git-basics/) | 90–120 min | Track your work with Git -- init, add, commit, log |
| 0.7 | [What is Networking?](module-0.7-what-is-networking/) | 90–120 min | IPs, ports, DNS -- how computers talk to each other |
| 0.8 | [Servers and SSH](module-0.8-servers-and-ssh/) | 80–100 min | What servers are, how to connect remotely |
| 0.9 | [Software and Packages](module-0.9-software-and-packages/) | 80–100 min | Installing and managing software from the terminal |
| 0.10 | [What is the Cloud?](module-0.10-what-is-the-cloud/) | 80–100 min | Cloud computing, AWS/Azure/GCP, where K8s fits |
| 0.11 | [Your First Server -- Putting It All Together](module-0.11-your-first-server/) | 90–120 min | Capstone: serve and check a small website |

These are planning estimates copied from the eleven module headers, not measured learner completion times. Their arithmetic gives an aggregate range of **940–1220 minutes (about 15 hours 40 minutes–20 hours 20 minutes)**; individual setup, reading, and practice time will vary.

---

## How to Use This Track

1. **Follow the suggested order.** Later exercises combine earlier skills, although some introductions can stand alone.
2. **Do the exercises.** Read the explanation, try the task, and compare your result with the success criteria.
3. **Go at your own pace.** Spend more time on a topic when you need it.
4. **Re-read if needed.** Return to an explanation or example when it helps.
5. **Take breaks.** Pause and return when you are ready.

---

## What's Next?

On the **suggested prerequisites route**, continue straight into Cloud Native 101 and then Kubernetes Basics—the linear spine from terminal skills to hands-on cluster work.

**Default next step:** [Cloud Native 101](../cloud-native-101/module-1.1-what-are-containers/) — containers, Docker, and the cloud-native ecosystem.

**Optional fork:** [Linux](../../linux/) if you want deeper operating-system knowledge before operations-heavy work. Linux is not required for the main route; you can return to it anytime.

If you are unsure where to go, start with Cloud Native 101 and keep the Linux path as an optional parallel route.

```text
               Zero to Terminal
                     |
              Module 0.11 (Capstone)
                     |
          Cloud Native 101  (default — suggested route)
                     |
            Kubernetes Basics
                     |
                     ...
          
          Linux  (optional fork — anytime)
```

---

## Time Investment

The module-header planning range is **about 15 hours 40 minutes–20 hours 20 minutes**. It is an unmeasured estimate, not a completion promise; setup, reading, and practice can take longer.

---

> **Start with one action.** Try it, check what happened, and ask questions before moving on. You do not need to master the whole track in one sitting.
