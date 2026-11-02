---
title: "Module 0.10: What is the Cloud?"
slug: prerequisites/zero-to-terminal/module-0.10-what-is-the-cloud
sidebar:
  order: 11
revision_pending: false
---
> **Complexity**: `[MEDIUM]` - Long-form conceptual read; concepts that click into place
>
> **Time to Complete**: 80–100 minutes (long-form beginner read)
>
> **Prerequisites**: [Module 0.9 - Software and Packages](/prerequisites/zero-to-terminal/module-0.9-software-and-packages/); [Module 0.1 - What is a Computer?](/prerequisites/zero-to-terminal/module-0.1-what-is-a-computer/) for the hardware vocabulary this module maps cloud services onto

---

## What You'll Be Able to Do

After this module, you will be able to make practical infrastructure comparisons instead of treating "cloud" as a buzzword:

- **Explain** cloud computing as rented compute, storage, and networking capacity rather than a vague place where data goes.
- **Compare** cloud computing with on-premises infrastructure and evaluate which tradeoffs matter for a new workload.
- **Map** compute, storage, networking, and database services back to the computer parts you already learned in Module 0.1.
- **Diagnose** why Kubernetes is useful when an application must run across many cloud servers instead of one hand-managed machine.

## Why This Module Matters

Hypothetical scenario: your small team has a demo on Friday, and the app needs a server, a place for uploaded files, a public URL, and a database before the customer can try it. If every part must be purchased, shipped, installed, wired, cooled, and patched by your organization, the demo becomes a hardware project before it becomes a software project. If those same building blocks can be rented from a cloud provider, the team can make a technical decision about capacity today, observe real usage tomorrow, and change direction before the hardware purchase would have arrived.

"The cloud" is one of the most repeated phrases in modern technology, but it is also one of the least useful phrases until you connect it to physical reality. There is no mist, no floating data, and no magical second internet where software lives without machines. A cloud service is backed by ordinary computers, disks, cables, power systems, cooling systems, buildings, staff, contracts, and control planes; the difference is that you rent the useful slice of that system instead of owning every layer yourself.

This module matters because Kubernetes usually enters the story after a team has more than one machine to manage. You learned what a computer is, how a terminal sends commands, how files and scripts work, and how SSH reaches a server across the network. Cloud computing is the bridge from "I can operate one remote machine" to "I can reason about hundreds or thousands of machines that appear, disappear, fail, scale, and cost money while I am not watching them."

> **Pause and predict**: Before reading further, write a one-sentence explanation of the cloud in your own words. After the module, compare that sentence with the model of rented compute, storage, networking, and managed services, and notice which parts became more concrete.

## The Cloud Is Rented Infrastructure, Not Weather

The common joke says that the cloud is "just someone else's computer." It is memorable because it punctures the mystery, and it is useful because it keeps you from treating cloud services as magic. At the same time, the joke is incomplete in the same way that calling a hotel "someone else's bed" is incomplete. The bed is real, but the hotel also provides cleaning, locks, fire alarms, plumbing, front-desk systems, booking software, staff, and a business model that lets you use a room for one night without buying a building.

With a public cloud, you can rent infrastructure from a provider instead of buying and operating every physical layer yourself. You still decide what capacity and services you need, where data belongs, and what security boundaries matter. The kitchen analogy helps compare ownership and rental, but cloud billing and responsibilities depend on the service and its terms.

NIST describes cloud computing through on-demand self-service, network access, pooled resources, rapid elasticity, and measured service. Its models also include private clouds, which can be operated for one organization and may be on or off premises; cloud is broader than renting from a public provider.

The most important hidden ingredient is the control plane. A traditional server room might require a ticket, a person with physical access, and a checklist before anything changes. A cloud provider exposes infrastructure through APIs, so creating a server, attaching storage, adding a firewall rule, or deleting a test environment can be automated and repeated. That is why cloud computing became so closely tied to DevOps, infrastructure as code, and Kubernetes: once infrastructure is programmable, teams can treat operations as a design problem rather than a collection of one-off manual tasks.

The kitchen analogy is a practical way to keep the tradeoff honest. If you own a restaurant building, you control the kitchen layout, the ovens, the power, and every maintenance decision, but you also carry the upfront cost and the risk of being wrong about demand. If you rent a commercial kitchen, you give up some control, but you can start faster, use shared facilities, and pay in a way that follows actual usage. Neither choice is morally better; each choice fits a different business shape.

```
- Buy a building                        ($$$$$)
- Install commercial ovens, fridges     ($$$$$)
- Set up plumbing and electrical        ($$$$)
- Hire maintenance staff                ($$$)
- Fix things when they break            (ongoing cost)
- If you get MORE customers:
    Build an extension (takes months)
- If you get FEWER customers:
    You still pay for the empty kitchen
```

That first option is similar to traditional on-premises infrastructure, often shortened to "on-prem." A company buys or leases physical space, installs equipment, connects the network, and builds internal processes for operating the machines. On-prem can be the right choice when workloads are steady, data-location requirements are strict, specialized hardware is needed, or the organization already has the staff and facilities to run servers well. Obtaining more capacity can take time when demand changes.

Owning infrastructure also changes the failure conversation. When the power supply fails, the network switch misbehaves, the disk fills, or the cooling system struggles, the organization must either fix the problem directly or pay a specialist to do so. That control can be valuable, especially in regulated or specialized environments, but it means capacity planning becomes a long-term commitment. A beginner should not hear "on-prem" as outdated; hear it as an ownership model with strong control and strong responsibility.

```
- Walk in and start cooking             (pay hourly)
- Ovens, fridges already there          (included)
- Plumbing, electrical already done     (included)
- Maintenance handled by the landlord   (included)
- If you get MORE customers:
    Rent a bigger kitchen (takes minutes)
- If you get FEWER customers:
    Downsize to a smaller kitchen, pay less
```

That second option is the cloud model. The provider has already built the data centers and control systems, so you request capacity through a web console, API, command-line tool, or infrastructure-as-code workflow. You can request, measure, resize, automate, and release resources as needs change. Reducing charges depends on each resource's billing rules and what remains allocated, not merely whether a VM is running.

Renting also lets a team create a small environment, test an idea, and delete the environment before committing to a bigger design. Pair provisioning with account boundaries, access reviews, and cleanup expectations.

Pause and predict: if a test environment is used only during business hours, which model makes it easier to reduce idle compute charges at night, and what must the team check about retained resources so that the savings actually happen? Commit to an answer in your own words before opening the reveal.

<details>
<summary>Check your prediction</summary>

The rented cloud model can reduce idle compute charges when stopping is supported. Stopping a VM does not stop all billing: AWS documents continuing EBS storage and associated Elastic IP charges while an EC2 instance is stopped. Inventory resources and check provider rules and billing afterward; stopping or deleting one VM does not guarantee zero cost.
</details>

## Build Versus Rent: The Operational Tradeoff

Buying infrastructure can involve lead time, upfront spending, and capacity estimates before demand is known. A personal website may need only a small server, but the same tradeoffs arise in larger systems.

The first problem is lead time. Physical servers are not created by a command; someone must approve a budget, order equipment, wait for shipping, rack the machines, cable them, install operating systems, configure networking, apply updates, and connect monitoring. Large organizations can streamline this, but physics and purchasing still impose delays. Cloud providers reduce that delay by keeping pooled capacity ready and exposing it through software interfaces.

Synthetic dialogue; actual procurement times vary:

```
Company: "We need 10 servers for our new project."
IT department: "OK. We need to:
  - Get budget approval (2 weeks)
  - Order the hardware (4 weeks)
  - Ship it to our data center (1 week)
  - Rack and cable it (3 days)
  - Install the OS (1 day)
  - Configure networking (2 days)
  Total: about 2 months."

Company: "But we need to launch next week..."
```

The contrast is not that cloud providers skip engineering. They did the engineering earlier, at scale, and then wrapped the result in a control plane that lets customers request a slice of it. That control plane is why cloud infrastructure feels different from remote access to a single server. You are not asking one machine to do more work; you are asking a platform to allocate machines, disks, IP addresses, firewall rules, identities, and related services on demand.

Synthetic dialogue; availability and provisioning time vary:

```
Engineer: "We need 10 servers."
*types a command*
Cloud: "Here are your 10 servers. They're ready now."
Time elapsed: about 2 minutes.
```

The second problem is capacity guessing. If you buy too little hardware, a successful launch becomes an outage because the site cannot handle demand. If you buy too much hardware, capital sits idle while finance still counts it as a real cost. Cloud capacity does not remove planning, but it changes the cost of being wrong because you can start small, measure, resize, and automate scaling based on real signals rather than a guess made months earlier.

Hypothetical scenario: a small game launches with a modest audience estimate, then a popular streamer features it unexpectedly on a Saturday. A team locked to fixed on-premises capacity may have no fast way to add machines, so players experience errors while the team waits for procurement or tries risky emergency changes. A team using cloud capacity still has application limits to solve, but it can usually add compute, storage throughput, or network capacity faster than it could acquire new physical hardware.

The third problem is maintenance. Servers need power, cooling, physical security, network redundancy, replacement parts, firmware updates, operating-system patching, backup planning, and failure procedures. Cloud does not make those responsibilities vanish; it moves many of them to the provider and leaves you with a different set of responsibilities. You still own application design, identity configuration, data protection choices, access policies, cost controls, and the decision to use managed services wisely.

Cloud teams often describe this as a shared responsibility model. For AWS, the provider secures the infrastructure underlying its services, while the customer's responsibilities vary with the service and configuration. Accounts, permissions, data protection, backups, and application settings still need attention. Check the actual service terms rather than assuming the provider operates your application correctly.

The shared-responsibility idea also explains why cloud skills are more than clicking buttons in a console. If a storage bucket is public when it should be private, the provider did not necessarily fail; the customer may have configured access incorrectly. If a database has no usable backup, the managed service may still be functioning exactly as configured. Cloud literacy means asking where each responsibility sits, how you would prove it is handled, and what evidence would alert you before a mistake becomes an outage or exposure.

This is also why cloud diagrams usually show boundaries. One boundary separates the provider's facilities from the customer's accounts. Another boundary separates public traffic from private services. A third boundary separates human users from automated service identities. You do not need to master those diagrams yet, but you should start noticing the questions they answer. Where does traffic enter, where is data stored, who can change the system, and which part would still be your team's problem during an incident?

## Cloud providers and the services they sell

Amazon Web Services (AWS), Microsoft Azure, and Google Cloud are examples of public cloud providers. You do not need to choose one today; the goal is to recognize service categories across providers with different labels. Product names and offerings can change, so check the provider's current documentation.

AWS offers services for compute, object storage, networking, and managed databases. The names in the mapping below are examples, not an exhaustive catalog.

Azure and Google Cloud offer comparable categories, though their services and interfaces differ. Kubernetes builds on Google's experience running containerized workloads and can run on different cloud providers or on premises.

Smaller providers also matter. DigitalOcean, Linode under Akamai, Hetzner, OVHcloud, and regional providers can be cheaper, simpler, closer to particular users, or better aligned with a team's needs. The beginner trap is to treat provider choice like a brand identity instead of an engineering decision. First learn the categories, then evaluate a provider based on workload shape, budget, compliance needs, operational skill, support model, and the services your team can run responsibly.

Portability deserves a careful, realistic definition here. Basic concepts transfer well: compute runs code, storage keeps data, networking connects systems, identity controls access, and observability tells you what is happening. Exact services may not transfer cleanly; compare APIs, limits, pricing, database features, load-balancer behavior, and account structures before moving. Kubernetes can reduce some differences for application deployment, but cloud-specific networking, storage, identity, and billing decisions remain.

Provider-neutral thinking is still worth practicing because it keeps your mental model from becoming a product catalog. When you see a new service name, ask what job it performs before asking whether it is impressive. Does it run code, store data, connect systems, protect access, observe behavior, or automate operations? That habit lets you learn one provider deeply without becoming helpless in another provider's documentation. It also prepares you to read Kubernetes documentation, where the same discipline of mapping names to responsibilities is essential.

Pause and predict: if an enterprise already uses Microsoft identity, Windows administration, and Office services heavily, which provider would probably receive an early evaluation, and what would still need to be checked before deciding? Commit to an answer in your own words before opening the reveal.

<details>
<summary>Check your prediction</summary>

Azure would probably receive an early evaluation because existing Microsoft identity and administration investments can reduce friction for accounts, procurement, and support. An early look is not a decision, though: the team would still need to check whether the specific workload fits Azure's regions, managed services, pricing, and limits, and whether team skills, compliance needs, and portability concerns point elsewhere. The habit worth keeping is that integration advantage earns a provider a serious hearing, not an automatic win.
</details>

## Mapping Cloud Services to Computer Parts

The best way to demystify cloud services is to map them back to the ordinary computer parts you already understand. A virtual machine is still a computer from the software's point of view: it has CPU capacity, memory, storage, a network interface, an operating system, and processes. Object storage is still a place to store bytes, but it is optimized for files and objects accessed through APIs rather than for a local filesystem mounted inside one laptop.

Compute is the cloud category for running code on rented processing capacity. When you create a VM or instance, you choose a size that represents a combination of CPU, memory, network capability, and sometimes specialized hardware such as GPUs. You can install software on it, SSH into it, run a web server, or attach it to automation. The tradeoff is that you still operate much of the machine unless you choose a more managed compute service.

```
"I need a computer that runs 24/7."

Cloud service: Virtual Machine (VM) / Instance
  - AWS calls it: EC2 (Elastic Compute Cloud)
  - Azure calls it: Virtual Machines
  - GCP calls it: Compute Engine

Kitchen analogy: Renting a cooking station.
  You choose the size (small burner or industrial oven)
  with billing determined by the provider's current terms.
```

Storage is the cloud category for keeping data after a process stops. Object storage is common for images, backups, logs, static website assets, exports, and large files because it is durable, API-driven, and separated from any one server. Block storage and file storage also exist, but object storage is the easiest beginner mental model: you put named objects into a bucket or container, set access rules, and pay for stored data plus operations and transfer.

```
"I need to store files, images, backups."

Cloud service: Object Storage
  - AWS calls it: S3 (Simple Storage Service)
  - Azure calls it: Blob Storage
  - GCP calls it: Cloud Storage

Kitchen analogy: Renting pantry shelves.
  Storage, requests, and transfer may have separate charges.
```

Networking is the cloud category for connecting resources safely. A virtual network lets you decide which machines can talk privately, which traffic can come from the internet, which ports are exposed, and where load balancers route requests. The terminology varies, but the concept is familiar from earlier modules: computers need addresses, routes, and rules so traffic reaches the right service without exposing everything to everyone.

```
"My servers need to talk to each other and to the internet."

Cloud service: Virtual Networks, Load Balancers
  - AWS calls it: VPC (Virtual Private Cloud)
  - Azure calls it: Virtual Network
  - GCP calls it: VPC

Kitchen analogy: Renting the delivery drivers and route planning.
  Your kitchens need roads between them and routes to customers.
```

You can run a database yourself on a virtual machine or use a managed database. Depending on the service and configuration, the provider may handle tasks such as backups, patching, and monitoring. You still need to choose settings, access controls, retention, and cost boundaries.

```
"I need to store and query structured data."

Cloud service: Managed Databases
  - AWS calls it: RDS (Relational Database Service)
  - Azure calls it: Azure SQL Database
  - GCP calls it: Cloud SQL

Kitchen analogy: A managed filing system for all your recipes,
  orders, and inventory. Someone else maintains the filing cabinets.
```

Before you move on, test the mapping instead of memorizing product names. AWS S3 maps most closely to storage because it keeps objects such as files and backups. GCP Compute Engine maps to compute because it gives you virtual machines with CPU and RAM. Azure Virtual Network maps to networking because it defines communication boundaries and routes. If you can perform that mapping, you can learn new cloud services without being overwhelmed by branding.

There is one more category that beginners often meet early: identity and access management. It does not map neatly to a single laptop part because it answers a different question: who or what is allowed to do which action? In the cloud, every person, automation script, virtual machine, managed service, and Kubernetes component may need permissions. Treat identity as the lock-and-key system for the rented building. A powerful server with careless permissions is not a strong architecture; it is an expensive way to create risk.

Observability is another supporting category that becomes important as soon as a system has users. Logs tell you what software reported, metrics tell you how the system behaved over time, traces can show the path of one request through several services, and alerts tell humans when attention is needed. These tools do not replace compute, storage, or networking, but they make those resources operable. A cloud system you cannot observe is like a rented kitchen with no thermometers, receipts, or inspection records.

### Classification checkpoint (unguided)

This diagnostic has no answer key on purpose. Write your answers in your notes file, then revisit them after the quiz to see how your reasoning held up. For each workload, name the cloud service category you would reach for first: compute, storage, networking, database, identity, or observability.

1. A photo-sharing app must keep millions of uploaded images available even if any single server dies, and the images are fetched through URLs rather than through one machine's filesystem.
2. A data team needs two hundred machines for a three-hour processing job every night, then nothing until the next night.
3. Customers can reach your website, but every login attempt fails with "permission denied" even for users who typed the correct password.
4. A contractor who left the project two weeks ago can still delete production file uploads because nothing ever revoked the access.

Now the failure story. On a Monday morning, customers report that the site is down. Using only the categories above, write the sequence of checks you would walk through: which category tells you whether users can reach the system at all, which tells you whether the application code is running, which tells you whether stored data is intact, which tells you whether an automated system did something it was not allowed to do, and which tells you what actually happened overnight. There is no single correct ordering, but a useful sequence moves from what users observe toward the layer where the evidence lives.

## Pay-As-You-Go Changes the Budget and the Failure Mode

Cloud pricing is often usage-based, which means you can pay for capacity while you use it instead of buying the maximum expected capacity upfront. This is powerful because it makes experiments cheaper and scaling faster, but it also creates a new operational risk. A server left running, a large disk kept after a test, a logging system with runaway volume, or a data transfer pattern nobody noticed can all become real bills.

```
Example:
  Assume a fictional server rate of $0.01/hour
  Running it 24/7 for a month: $0.01 x 24 x 30 = $7.20

  Need it only 8 hours a day for testing?
  $0.01 x 8 x 22 workdays = $1.76/month

  Need 100 servers for 2 hours for a big processing job?
  $0.01 x 100 x 2 = $2.00
```

The numbers are hypothetical, not a provider price quote. Actual rates and billing units depend on the service and can change; check the provider's pricing page, including storage and outbound data transfer. Stopping compute may leave other charges. Steady demand may favor owned infrastructure or committed cloud discounts, depending on the full cost.

Hypothetical scenario: your team creates a performance-test environment with many servers for a two-hour benchmark, then forgets to delete it before the weekend. The cloud made the benchmark easy because capacity arrived quickly, but the same ease made the mistake expensive because the resources kept running without anyone cooking in the kitchen. Cost controls, budgets, tags, cleanup routines, alerts, and ownership labels are not paperwork; they are part of operating cloud systems responsibly.

Cloud cost thinking is also a preparation for Kubernetes. Kubernetes can run multiple copies of an application, use storage, expose services, and replace workloads after failures. Additional capacity and cloud resources depend on the cluster's integrations and configuration. Ask both reliability and budget questions: how many copies do we need, where do they run, and what tells us to scale back down?

Cost visibility is a technical practice, not only an accounting practice. Engineers influence cost when they choose instance sizes, logging volume, storage classes, data-transfer paths, retry behavior, and scaling thresholds. Finance may receive the bill, but architecture creates the bill. In healthy cloud teams, cost dashboards, resource tags, budgets, and cleanup reviews are part of the same operating rhythm as monitoring and incident review because all of them describe whether the system is behaving as intended.

A useful beginner habit is to ask what should happen when nobody is using a resource. A production database may need to stay available, but a practice VM, temporary load test, preview environment, or throwaway storage bucket probably does not. Cloud platforms make it easy to create those resources, so the cleanup rule must be designed before the environment exists. This habit will matter later when Kubernetes creates resources indirectly, because deleting an application object may or may not remove every cloud resource attached to it.

Pause and predict: your new app gets ten times more traffic on weekends than on weekdays. Which resources would you consider scaling up for the weekend, which would you leave steady, and what signal would tell you it is safe to scale back down? Commit to an answer in your own words before opening the reveal.

<details>
<summary>Check your prediction</summary>

Compute is one candidate to scale up, if the application can distribute the extra work; the load balancer and network path may also need capacity. The database may be the bottleneck instead, so measure before choosing. Check utilization, latency, and errors before scaling back down. A timer alone can add capacity when traffic does not arrive or remove it while users are still waiting.
</details>

## Where Kubernetes Fits

Kubernetes helps manage containerized applications across machines. A single server can run a small app, but other systems need multiple copies, extra capacity, rolling updates, and recovery when machines fail. These capabilities require suitable application design, capacity, and configuration; downtime is not automatically prevented.

```
Module 0.1: You learned about one computer (one kitchen)
Module 0.3: You learned to give commands to that kitchen
Module 0.5: You learned to write instructions (recipes/scripts)
Module 0.8: You learned to connect to remote kitchens (servers and SSH)
Module 0.9: You learned to install software and manage packages on those kitchens
Module 0.10: You learned that the cloud has THOUSANDS of kitchens for rent

Kubernetes can coordinate workloads on a set of those machines.
```

Kubernetes, often written as K8s because there are eight letters between K and s, was created from Google's experience operating large fleets of containerized workloads and is now a vendor-neutral open source project under the Cloud Native Computing Foundation. Its job is not to replace cloud providers. Its job is to give you a declarative control system for running applications across available machines, whether those machines come from AWS, Azure, Google Cloud, another provider, or your own data center.

Without Kubernetes, an engineer may choose a specific server and place the app there manually. That can work while the system is tiny, but the operational burden grows quickly. The engineer must notice failures, decide where to restart the app, ensure the new server has capacity, update routing, and avoid breaking other applications. The problem is not that engineers are careless; the problem is that humans are poor schedulers for constantly changing infrastructure.

Synthetic dialogue:

```
Engineer: "Deploy the app to server-42."
*server-42 crashes at 3 AM*
Engineer's phone: *RING RING*
Engineer: "Ugh... let me move it to server-43 manually."
```

With Kubernetes, the engineer describes desired state: for example, keep three copies of this application running. Kubernetes watches actual state and takes action when actual state diverges from desired state. If one server fails, the cluster can place a replacement copy elsewhere, subject to the capacity and policy available. The important mental shift is that you stop thinking only in commands to individual machines and start thinking in declarations to a system that reconciles reality.

Synthetic dialogue; recovery depends on capacity and configuration:

```
Engineer: "I need 3 copies of this app running."
Kubernetes: "Done. Running on server-42, server-67, and server-91."
*server-42 crashes at 3 AM*
Kubernetes: "Server-42 is down. A replacement can be scheduled on an available node."
```

This is why cloud concepts matter before Kubernetes concepts. If you do not understand rented compute, storage, networking, and pay-as-you-go capacity, Kubernetes can feel like a pile of strange objects and commands. If you do understand the cloud model, Kubernetes becomes easier to place: it is the restaurant manager coordinating many kitchens, not the kitchen building itself. It decides where work should run, watches for failure, and helps teams operate applications at a scale where manual placement is too slow.

Managed Kubernetes services make this relationship even clearer. Providers can operate parts of the Kubernetes control plane for you, while you still decide what workloads to deploy, what permissions to grant, what network exposure is acceptable, and how much capacity the cluster needs. That split follows the same shared-responsibility pattern you have already seen. A managed cluster reduces some operational work, but it does not make architecture, security, or cost decisions on behalf of your team.

Kubernetes also shows why abstraction is useful but never free. A Deployment can describe three copies of an application without naming the exact machines, which is much easier than hand-picking servers. Under the abstraction, real CPU, memory, disk, network routes, load balancers, and credentials still exist. When something breaks, operators often move between layers: they inspect the Kubernetes object, then the node, then the cloud resource, then the application logs. The cloud mental model helps you avoid getting lost during that movement.

You have also reached the point where the Zero to Terminal track turns into cloud-native work. The next modules will introduce containers, Docker fundamentals, Kubernetes basics, and eventually certification-oriented skills. Those topics will add commands and objects, but the foundation remains the same: software runs on computers, computers need storage and networks, and reliable systems require deliberate operating models.

```
Zero to Terminal (YOU ARE HERE -- almost done!)
  ✓ Understand computers
  ✓ Use the terminal
  ✓ Edit files
  ✓ Understand servers and SSH
  ✓ Understand cloud computing
  → Capstone next: Module 0.11 (Your First Server)

        ↓

Cloud Native 101 (after Zero to Terminal)
  → What are containers?
  → Docker fundamentals
  → What is Kubernetes?
  → The cloud-native ecosystem

        ↓

Kubernetes Basics
  → Your first cluster
  → kubectl basics
  → Pods, Deployments, Services

        ↓

CKA Certification Track
  → Certified Kubernetes Administrator
  → Your first professional credential

        ↓

Platform Engineering
  → SRE, GitOps, DevSecOps, MLOps
  → Building platforms that other developers use
```

## When This Doesn't Apply

Cloud computing is not automatically the best answer for every workload. If a workload has extremely steady demand, strict physical control requirements, special hardware constraints, unusual licensing terms, or a team that already operates efficient data centers, on-premises infrastructure may be a rational choice. The question is not "cloud or no cloud" as a slogan; the question is which model gives the organization enough speed, control, reliability, compliance, and cost predictability for the work at hand.

The same caution applies inside the cloud. A virtual machine may be better than a managed platform when the team needs low-level control, while a managed service may be better when the team wants the provider to handle routine operations. Object storage may work well for uploaded files and backups, but may not meet an application's need for structured transactions. Match the service to the problem.

A useful pattern is to start uncertain workloads in the cloud because rented capacity lowers the cost of learning. Early prototypes, training environments, temporary test systems, bursty data-processing jobs, and applications with unknown demand usually benefit from fast provisioning and easy teardown. The scaling consideration is discipline: as experiments become permanent, the team must add ownership tags, budgets, monitoring, backups, and architecture reviews so that a cheap experiment does not become an unmanaged production system.

Another pattern is to use managed services when operations are not the product differentiator. A managed database may reduce operational work, but can create dependencies on provider behavior, pricing, limits, and features. Document those dependencies and assess how they affect portability.

The main anti-pattern is cloud adoption by hype. Teams sometimes move workloads because the provider is popular, a conference talk sounded convincing, or a competitor announced a migration. That skips the engineering work. A better alternative is to write down the workload shape, data needs, failure tolerance, expected traffic, compliance concerns, team skills, and cost model before choosing the platform. Cloud is a tool, not a maturity badge.

Another anti-pattern is treating the first working setup as the final architecture. Cloud platforms make it easy to create a server, open a port, attach storage, and declare victory. That is fine for learning, but production requires a second pass: remove public access that is not needed, document ownership, add backups, define monitoring, test recovery, and make cost visible. The beginner version of this habit is simple: every time you create a resource, ask who owns it, what it costs, what data it touches, and how it will be deleted.

## When You'd Use This vs Alternatives

Use cloud computing when you need capacity quickly, when demand may change, when experiments should be cheap to start and cheap to stop, or when managed services remove work your team is not trying to specialize in. Use on-premises infrastructure when long-lived predictable demand, physical control, specialized hardware, existing facilities, or regulatory constraints make ownership more sensible. Use a hybrid model when the organization has real reasons to keep some systems close while still using cloud capacity for burst, development, analytics, or newer application platforms.

When choosing among providers, start with the service categories rather than the brand names. Ask where the application code runs, where durable data lives, how users reach it, how operators authenticate, how backups work, how cost is tracked, and what happens during failure. Then compare providers on the details that affect those questions. The right answer for a beginner exercise is often whichever provider has the clearest free-tier documentation and lowest risk for learning; the right answer for a company includes contracts, compliance, support, staffing, integration, and exit strategy.

A simple decision framework is to separate reversible decisions from sticky decisions. Creating a temporary VM for a lab is usually reversible because you can delete it and try another provider later. Choosing a proprietary database feature, embedding provider-specific event services throughout an application, or building networking around a complex account structure is stickier because later migration touches code, data, operations, and people. Reversible choices are good places to learn quickly; sticky choices deserve slower review and clearer documentation.

## Did You Know?

- The National Institute of Standards and Technology published Special Publication 800-145 in 2011, and its definition of cloud computing still anchors many formal discussions of on-demand self-service, broad network access, resource pooling, rapid elasticity, and measured service.
- Kubernetes means "helmsman" in Greek, which fits the ship-wheel logo and the idea of steering many containers across a fleet of machines.
- Kubernetes v1.35 is the exam-pinned target for this curriculum. Check the version on a real cluster before relying on a command example.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Treating the cloud as magic instead of physical infrastructure | The interface is software, so beginners forget that real machines, disks, networks, power, and cooling are underneath | Keep mapping every service back to compute, storage, networking, data, or operations responsibilities |
| Assuming cloud is always cheaper | Pay-as-you-go sounds inexpensive, but steady workloads and forgotten resources can cost more than expected | Compare the workload shape, set budgets, shut down temporary systems, and review costs as part of normal operations |
| Choosing a provider only because it is popular | Brand familiarity can hide mismatches in team skills, compliance needs, regions, support, or service limits | Evaluate AWS, Azure, Google Cloud, and alternatives against the actual workload and organization constraints |
| Trying to learn every service at once | Large providers expose hundreds of services, and the catalog can overwhelm the core mental model | Start with compute, storage, networking, identity, and one database option, then add services when a real design needs them |
| Forgetting shared responsibility | Rented infrastructure can feel fully managed, so teams may skip access control, backups, monitoring, or patch decisions | Separate what the provider operates from what your team configures, owns, tests, and reviews |
| Ignoring vendor lock-in until migration hurts | Managed services are convenient, but deep provider-specific design choices can make later moves expensive | Decide deliberately where lock-in is worth it, prefer open interfaces when portability matters, and document the tradeoff |
| Scaling without a cost signal | Automation can add capacity faster than humans notice the bill | Pair scaling rules with budgets, alerts, cleanup jobs, ownership tags, and regular review of unused resources |

## Quiz

<details>
<summary>1. Your team needs a server for a customer demo this week, but purchasing hardware would take weeks. How would you explain why cloud computing is a valid alternative?</summary>

Cloud computing is a valid alternative because it lets the team rent compute, storage, and networking from a provider that has already built the physical infrastructure. The key advantage is not that the computers are mysterious; it is that capacity can be requested quickly through software and paid for as it is used. Buying hardware may still make sense for predictable long-term needs, but it does not match a fast experiment with uncertain demand. A good answer should mention both speed and the responsibility to manage configuration, access, and cost.
</details>

<details>
<summary>2. A retail site needs far more capacity during a holiday sale than during ordinary weeks. Which infrastructure model fits that demand pattern, and what risk must the team still manage?</summary>

The cloud usually fits bursty demand because the team can add capacity for the sale and reduce it afterward instead of buying enough hardware for the annual peak. That changes the budget from a large fixed purchase into a more flexible operating cost. The risk is that resources can remain running, scale too far, or move data in expensive ways if nobody sets controls. The team should pair scaling with budgets, monitoring, cleanup procedures, and a clear owner for cost review.
</details>

<details>
<summary>3. Your company already uses Microsoft identity systems and Windows administration heavily. Does that automatically mean Azure is the correct provider for every new workload?</summary>

Azure should probably receive serious evaluation because existing Microsoft integration can reduce friction for identity, administration, procurement, and support. It is not automatically correct, because the workload may need regions, managed services, pricing, portability, or operational patterns where another provider is stronger. The right decision compares actual requirements rather than choosing by brand familiarity. A mature answer recognizes that provider fit is contextual and must include both technical and organizational constraints.
</details>

<details>
<summary>4. A startup needs to run application code, store uploaded videos, route public traffic, and keep customer account records. How would you map those needs to cloud service categories?</summary>

The application code needs compute, such as virtual machines, containers, or another runtime that provides CPU and memory. Uploaded videos need storage, most likely object storage because large files should not depend on one server's local disk. Public traffic needs networking, including virtual networks, firewall rules, DNS, and possibly a load balancer. Customer account records need a database, and a managed database may be appropriate if the team wants the provider to handle part of the operational burden.
</details>

<details>
<summary>5. An app runs on one cloud server, and every server failure requires a person to move it manually at night. What problem does Kubernetes address in this situation?</summary>

Kubernetes addresses the gap between desired state and actual state across multiple machines. Instead of telling one specific server to run the app forever, the team tells Kubernetes how many copies should exist and lets the control plane place those copies on available nodes. When a node fails, Kubernetes can schedule replacement work elsewhere if enough capacity remains. It does not remove the need for good application design, but it reduces manual placement and recovery work.
</details>

<details>
<summary>6. A team says, "We should move everything to the cloud because cloud is modern." How would you challenge that plan constructively?</summary>

I would ask for the workload shape, cost model, data requirements, compliance constraints, reliability goals, and team skills before accepting the plan. Cloud can be the right choice for speed, elasticity, and managed services, but those benefits are not automatic for every system. Some steady or specialized workloads may be better on owned infrastructure, and some cloud migrations fail because teams do not plan responsibility boundaries. A constructive challenge turns the slogan into an engineering comparison.
</details>

## Hands-On Exercise: Explore Free Cloud Tiers

This exercise is about reading provider documentation like an operator, not signing up for an account. Free-tier programs change over time, and the current rules can depend on account age, region, machine family, service plan, trial credit, or monthly usage limits. Your job is to observe the structure of the offers and connect each offer back to compute, storage, and networking concepts from the lesson.

### Step 1: Visit the current free-tier pages

Open these pages in your browser and treat them as live documentation rather than static promises from this module:

- **AWS Free Tier documentation**: [https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/billing-free-tier.html](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/billing-free-tier.html)
- **Google Cloud Free Program documentation**: [https://cloud.google.com/free/docs/free-cloud-features](https://cloud.google.com/free/docs/free-cloud-features)
- **Azure Free Account FAQ**: [https://azure.microsoft.com/en-us/free/free-account-faq/](https://azure.microsoft.com/en-us/free/free-account-faq/)

Read the pages slowly enough to distinguish trial credit from monthly always-free usage. The distinction matters because a trial credit behaves like a temporary budget, while an always-free allowance is usually tied to ongoing limits and conditions. Do not assume that a headline applies to every region, every account, every VM family, or every storage class.

### Step 2: Look for these specific things

On each page, try to find the same three categories so your notes compare provider offers instead of copying disconnected marketing language:

1. **Free compute**: How much free server time do they offer? Look for EC2 on AWS, Compute Engine on Google Cloud, and Virtual Machines on Azure.
2. **Free storage**: How much free storage do they describe? Look for S3 on AWS, Cloud Storage on Google Cloud, and Blob Storage on Azure.
3. **Eligibility and duration**: Which benefits are trial credit, which are time-limited offers, which are always-free, and what account-date, region, plan, or VM-family conditions apply?

### Step 3: Write down what you found

Create a fresh disposable workspace under your exclusive control. Use a Bash-compatible terminal, including an authorized WSL or lab shell on Windows. Run the whole connected block: `&&` runs the next command only after success, so failed creation or navigation prevents opening the editor. Listings display context and the editor opens automatically. Leave existing names untouched and choose an unused name for later paths; do not use `mkdir -p`. Unexpected contents or uncertain ownership mean exit without saving and start fresh.

```bash
cd ~ &&
mkdir kubedojo-cloud-notes &&
cd kubedojo-cloud-notes &&
pwd &&
ls -a &&
nano cloud-notes.txt
```

Write what you found in a consistent format, using the provider pages as the source of truth for current limits and conditions:

```
My Cloud Research Notes
=======================
Date: <today's date>

AWS Free Tier:
- Compute: record the current EC2 offer, including whether your account creation date changes the eligible VM families
- Storage: record the current S3 allowance and any time limits

GCP Free Tier:
- Compute: record the current Compute Engine offer, including any region restrictions
- Storage: record the current Cloud Storage allowance and whether it is tied to trial credit or always-free usage

Azure Free Tier:
- Compute: record the current VM or credit-based offer, including any signup or plan conditions
- Storage: record the current Blob Storage allowance and whether it comes from credit, a limited-time offer, or an always-free limit

Notes:
- These offers are time-sensitive and full of conditions
- Some benefits depend on account age, region, plan, or eligible machine families
- Always check the current limits, regions, and account eligibility rules
```

Save and exit with `Ctrl + O`, Enter, then `Ctrl + X`. You do not need to create any cloud account for this exercise, and you should not enter payment details just to complete the module. The goal is to practice reading cloud documentation critically and to see how providers present compute, storage, and account eligibility.

### Step 4: Verify your notes

```bash
cat cloud-notes.txt
```

Review your notes and mark whether each provider separated compute, storage, eligibility, and duration clearly. If a page feels confusing, that is useful information rather than a failure. Real cloud work includes reading conditions carefully, checking current provider documentation, and asking what a promise means in the specific region, account, and service you plan to use.

### Success criteria

- [ ] You visited at least one provider free-tier page and identified whether the offer included compute, storage, or both.
- [ ] You recorded at least one condition that affects eligibility, such as account age, region, trial credit, or service family.
- [ ] You mapped one provider-specific service name back to compute, storage, networking, or database categories.
- [ ] You saved `cloud-notes.txt` in your new workspace and verified that same file with `cat`.
- [ ] You can explain why free-tier pages are useful for learning but should not be treated as permanent pricing promises.

## Sources

- [AWS EC2: Stop and start instances, including retained-resource charges](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/how-ec2-instance-stop-start-works.html)
- [AWS EC2 pricing](https://aws.amazon.com/ec2/pricing/on-demand/)
- [Amazon EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/concepts.html), [S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html), [VPC](https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html), and [RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html)
- [Azure Virtual Machines](https://learn.microsoft.com/en-us/azure/virtual-machines/overview), [Blob Storage](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-overview), [Virtual Network](https://learn.microsoft.com/en-us/azure/virtual-network/virtual-networks-overview), and [SQL Database](https://learn.microsoft.com/en-us/azure/azure-sql/database/sql-database-paas-overview)
- [Google Compute Engine](https://cloud.google.com/compute/docs/instances), [Cloud Storage](https://cloud.google.com/storage/docs/introduction), [VPC](https://cloud.google.com/vpc/docs/overview), and [Cloud SQL](https://cloud.google.com/sql/docs/introduction)
- [Kubernetes v1.35 Deployments](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/controllers/deployment/)

- [Kubernetes Project Journey Report](https://www.cncf.io/reports/kubernetes-project-journey-report/)
- [The NIST Definition of Cloud Computing](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-145.pdf)
- [Overview of Amazon Web Services](https://docs.aws.amazon.com/whitepapers/latest/aws-overview/introduction.html)
- [Kubernetes Overview](https://kubernetes.io/docs/concepts/overview/)
- [AWS Free Tier documentation](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/billing-free-tier.html)
- [Google Cloud Free Program documentation](https://cloud.google.com/free/docs/free-cloud-features)
- [Azure Free Account FAQ](https://azure.microsoft.com/en-us/free/free-account-faq/)
- [AWS Shared Responsibility Model](https://docs.aws.amazon.com/whitepapers/latest/aws-risk-and-compliance/shared-responsibility-model.html)
- [Microsoft Azure shared responsibility in the cloud](https://learn.microsoft.com/en-us/azure/security/fundamentals/shared-responsibility)
- [Google Cloud shared responsibility and shared fate](https://cloud.google.com/architecture/framework/security/shared-responsibility-shared-fate)
- [AWS What is Cloud Computing?](https://aws.amazon.com/what-is-cloud-computing/)
- [Google Cloud What is Cloud Computing?](https://cloud.google.com/learn/what-is-cloud-computing)

## Next Module

[Module 0.11: Your First Server](../module-0.11-your-first-server/) continues the capstone path by putting the pieces together: terminal skills, remote machines, files, and cloud thinking become your first deployed website.
