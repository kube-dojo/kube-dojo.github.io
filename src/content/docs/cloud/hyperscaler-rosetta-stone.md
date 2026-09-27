---
title: "The Hyperscaler Rosetta Stone"
sidebar:
  order: 2
---
**Complexity**: `[MEDIUM]` | **Time to Complete**: 2 hours | **Prerequisites**: Cloud Native 101 (containers, Docker basics). After completing this module, you will be able to perform all of the outcomes listed below and defend those architectural decisions during multi-cloud migration reviews:

## What You'll Be Able to Do

- **Compare equivalent services across AWS, GCP, and Azure for compute, storage, networking, and identity domains**
- **Diagnose multi-cloud migration failures caused by architectural differences (regional vs global VPCs, IAM models)**
- **Design multi-cloud architectures that account for fundamental structural differences between hyperscalers**
- **Evaluate cloud provider tradeoffs for specific workload patterns using the service mapping framework**

---

## Why This Module Matters

Hypothetical scenario: In late 2022, a rapidly scaling fintech enterprise decided to adopt a multi-cloud strategy to mitigate vendor lock-in and satisfy regulatory compliance requirements. Their primary infrastructure, built over six years, was heavily entrenched in Amazon Web Services (AWS). They utilized IAM roles, complex regional VPC peering, and an extensive array of ECS services. When the engineering leadership mandated a complete replication of their core transaction processing pipeline in Google Cloud Platform (GCP) and Microsoft Azure, the architecture team assumed the migration would be straightforward. They reasoned that a virtual machine is just a virtual machine, a network is just a network, and a database is just a database.

This assumption led to a catastrophic six-month delay, millions in burned runway, and an architectural disaster that required a complete teardown. The team attempted to map AWS regional VPC models directly to GCP global VPC architecture, resulting in overlapping subnets, complex routing nightmares, and severe performance bottlenecks. They misunderstood how GCP Service Accounts differ from AWS IAM Roles, leading to a sprawling mess of long-lived keys exported across environments, which ultimately triggered a severe security audit failure. In Azure, they attempted to implement resource grouping exactly like AWS tags, ignoring Azure native Resource Group hierarchy, which broke their entire automated deployment pipeline and cost-tracking dashboards.

The fundamental disconnect was not a lack of technical skill because these engineers were senior practitioners who understood their systems intimately. The failure stemmed from a lack of fluency in the specific architectural dialects of the major hyperscalers. They were trying to speak French using Spanish grammar rules, assuming that identical terminology implied identical operational semantics across cloud provider boundaries.

Understanding the translation layer between Amazon Web Services (AWS), Google Cloud Platform (GCP), and Microsoft Azure is not merely about memorizing a glossary of marketing terms. It requires mastering the underlying design philosophies that govern how each platform routes network traffic, isolates failure domains, and enforces security perimeters. By learning this Rosetta Stone of cloud computing, engineers can navigate multi-cloud migrations successfully, design resilient systems that respect native cloud primitives, and evaluate the operational tradeoffs of disparate platforms with quantitative precision. This module provides that translation layer across every core engineering discipline.

---

## 1. Identity and Access Management: The Rosetta Stone of Security

When you strip away the branding, every cloud provider offers the same basic building blocks: a way to run code, a way to grant permissions, and a way to group resources. However, the implementation of Identity and Access Management (IAM) varies wildly and is the source of the most dangerous migration errors. Misinterpreting how security principals authenticate or inherit permissions creates catastrophic security exposures or completely halts automated deployments.

### The Core Philosophies

Think of cloud providers like different operating systems with divergent security models. AWS is highly granular, demanding explicit permissions for every single action, and relies heavily on assuming temporary roles through a default-deny evaluation engine. GCP relies on a cohesive, hierarchical project-based structure where identities are treated as first-class resources that can themselves have permissions assigned to them. Microsoft Azure is deeply integrated with enterprise identity through Microsoft Entra ID (formerly Azure Active Directory) and relies on a strict hierarchical management model spanning tenants, management groups, subscriptions, and resource groups.

```text
Identity Model Comparison

AWS                          GCP                          Azure
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│   AWS Account    │         │  GCP Organization│         │  Entra ID Tenant │
│   (root user)    │         │                  │         │  (Azure AD)      │
│  ┌────────────┐  │         │  ┌────────────┐  │         │  ┌────────────┐  │
│  │ IAM Users  │  │         │  │  Folders    │  │         │  │ Management │  │
│  │ IAM Groups │  │         │  │  (optional) │  │         │  │  Groups    │  │
│  │ IAM Roles  │  │         │  │            │  │         │  │            │  │
│  └────────────┘  │         │  └──────┬─────┘  │         │  └──────┬─────┘  │
│        │         │         │         │        │         │         │        │
│  ┌─────▼──────┐  │         │  ┌──────▼─────┐  │         │  ┌──────▼─────┐  │
│  │  Policies  │  │         │  │  Projects  │  │         │  │Subscriptions│ │
│  │  (JSON)    │  │         │  │ (boundary) │  │         │  │            │  │
│  │  attached  │  │         │  │  roles     │  │         │  │  ┌────────┐│  │
│  │  to role   │  │         │  │  bound at  │  │         │  │  │Resource││  │
│  └────────────┘  │         │  │  this level│  │         │  │  │ Groups ││  │
│                  │         │  └────────────┘  │         │  │  └────────┘│  │
│  Key concept:    │         │  Key concept:    │         │  │  RBAC at   │  │
│  "Assume Role"   │         │  "Bind Role to   │         │  │  any scope │  │
│  via STS tokens  │         │   identity at    │         │  └────────────┘  │
│                  │         │   resource"      │         │  Key concept:    │
│                  │         │                  │         │  "Managed        │
│                  │         │                  │         │   Identities"    │
└──────────────────┘         └──────────────────┘         └──────────────────┘
```

**AWS Identity Philosophy**: AWS uses a strict default-deny authorization engine where any request lacking an explicit allow policy is automatically denied. You create IAM Users for legacy human operators, IAM Groups for organization, and IAM Roles for machine processes. The most critical construct is the **IAM Role**, which does not possess permanent credentials; instead, applications assume roles dynamically via the AWS Security Token Service (STS) to obtain short-lived cryptographic tokens. Permissions are defined through declarative JSON documents that combine statements, actions, and resource Amazon Resource Names (ARNs).

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::my-company-data-bucket/*"
    }
  ]
}
```

```bash
# Create an IAM role for an EC2 instance
aws iam create-role \
    --role-name my-app-role \
    --assume-role-policy-document file://trust-policy.json

# Attach a managed policy
aws iam attach-role-policy \
    --role-name my-app-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Create an instance profile and add the role
aws iam create-instance-profile --instance-profile-name my-app-profile
aws iam add-role-to-instance-profile \
    --instance-profile-name my-app-profile \
    --role-name my-app-role
```

**GCP Identity Philosophy**: GCP separates human users (Google Accounts or Cloud Identity directories) from machine principals, which are represented by **Service Accounts**. A GCP Service Account operates as an independent machine identity identified by an email address, such as `my-app@my-project.iam.gserviceaccount.com`. Rather than attaching policies directly to the identity, GCP binds predefined or custom roles to identities at specific levels of the resource hierarchy, including Organizations, Folders, and Projects. Furthermore, because Service Accounts are resources themselves, other principals can be granted permissions to impersonate them or act on their behalf.

```bash
# Create a service account
gcloud iam service-accounts create my-app-sa \
    --display-name="My Application Service Account"

# Granting a role to a service account on a specific project
gcloud projects add-iam-policy-binding my-gcp-project-id \
    --member="serviceAccount:my-app-sa@my-gcp-project-id.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# Attach the service account to a Compute Engine instance (no keys needed!)
gcloud compute instances create my-vm \
    --service-account=my-app-sa@my-gcp-project-id.iam.gserviceaccount.com \
    --scopes=cloud-platform \
    --zone=us-central1-a
```

**Azure Identity Philosophy**: Azure decouples resource organization from identity governance by anchoring all authentication in Microsoft Entra ID. Access management is implemented through Azure Role-Based Access Control (RBAC), which evaluates role definitions against explicit scopes such as management groups, subscriptions, resource groups, or individual resources. For workload compute instances, Azure provides **Managed Identities**, which automatically create and maintain service principals in Entra ID without requiring developers to manage credentials. When an Azure virtual machine is deprovisioned, its system-assigned managed identity is automatically cleaned up in Entra ID.

```bash
# Create a VM with a system-assigned managed identity
az vm create \
    --resource-group my-rg \
    --name my-vm \
    --image Ubuntu2204 \
    --assign-identity '[system]'

# Assigning a role to a managed identity for a storage account
az role assignment create \
    --assignee-object-id <managed-identity-object-id> \
    --role "Storage Blob Data Reader" \
    --scope /subscriptions/<sub-id>/resourceGroups/<rg-name>/providers/Microsoft.Storage/storageAccounts/<account-name>
```

In AWS environments, policy evaluation follows a deterministic priority order: an explicit deny anywhere immediately terminates evaluation, followed by Service Control Policy (SCP) guardrails, resource-based policies, and identity permissions. In GCP, allow policies inherit down the resource tree from Organization to Folder to Project, while newly introduced IAM Deny Policies override any inherited allow grants. In Azure, role assignments grant permissions cumulatively across parent scopes, while Deny Assignments are enforced to protect managed applications and blueprints from unauthorized modification.

Cross-account and cross-project access patterns require strict boundaries to prevent privilege escalation. In AWS, IAM role chaining permits an identity to assume successive roles, though session durations are bounded and original principal tags can be preserved through session tagging. In GCP, cross-project access is managed by assigning roles on target resources directly to service accounts residing in separate projects, eliminating the need to create secondary proxy identities. In Azure, cross-tenant access relies on Microsoft Entra B2B collaboration or Lighthouse, allowing centralized managed service providers to execute RBAC operations across customer subscriptions with fine-grained scoping.

Understanding instance metadata services is essential for securing workload authentication across hyperscalers. AWS implements IMDSv2, requiring applications to obtain an ephemeral session token via an HTTP PUT request before querying temporary instance credentials. Google Cloud instances access credentials through `http://metadata.google.internal` by supplying the mandatory `Metadata-Flavor: Google` request header. Microsoft Azure provides identity tokens via `http://169.254.169.254/metadata/identity/oauth2/token` with the required `Metadata: true` header. These metadata mechanisms ensure that running processes retrieve short-lived access tokens without storing permanent cryptographic secrets on local disk volumes.

### IAM Translation Table

| Concept | AWS | GCP | Azure |
| :--- | :--- | :--- | :--- |
| Human identity | IAM User | Google Account / Cloud Identity | Entra ID User |
| Machine identity | IAM Role (assumed) | Service Account | Managed Identity |
| Permission grouping | IAM Policy (JSON) | Role (predefined or custom) | Role Definition (RBAC) |
| Temporary credentials | STS AssumeRole | Service Account tokens (auto) | Managed Identity tokens (auto) |
| Federation | SAML / OIDC to IAM | Workload Identity Federation | Entra ID Federation |
| Resource boundary | Account | Project | Subscription |
| Organizational grouping | AWS Organizations + OUs | Organization + Folders | Management Groups |
| Cross-service auth | Instance Profiles | Attached Service Account | System-Assigned Identity |

### Hypothetical scenario: The Long-Lived Key Disaster

A DevOps team migrating an application from AWS to GCP needed their application to read from a cloud storage bucket. In AWS, they were accustomed to attaching an IAM Instance Profile to their EC2 instance. The EC2 instance automatically received temporary credentials from the local instance metadata service, allowing secure access without managing long-lived cryptographic secrets on disk.

When moving to GCP, the engineers could not locate an entity named "Instance Profile" in the console. Instead of reviewing the documentation on how to attach a GCP Service Account to a Compute Engine instance, they created a Service Account, generated a long-lived JSON private key file, and baked that key file directly into their production container image. Three months later, an engineer inadvertently committed that image definition to an open public repository. Because the private key was long-lived and held project-wide editor privileges, unauthorized automated scanners immediately accessed the project and spawned cryptocurrency miners.

The critical lesson from this failure is to translate the core security intent rather than the superficial mechanism. The architectural intent was "temporary, instance-bound credentials refreshed automatically." The correct translation for an AWS IAM Instance Profile is an attached GCP Service Account or an Azure System-Assigned Managed Identity, both of which eliminate long-lived secrets from virtual machine filesystems.

**Pause and predict:** Suppose a security team decides to export a GCP service account JSON key file and upload it into an AWS Secrets Manager secret so that an EC2 worker can write data into a Cloud Storage bucket. What critical architectural failure does this design introduce, and how does Workload Identity Federation solve the credential lifecycle issue cleanly without static keys?

Exporting a static service account key introduces a permanent, non-expiring credential that bypasses instance identity boundaries and creates an ongoing credential rotation burden. If that key is ever leaked or exfiltrated, any external party can impersonate the service account until the key is manually revoked. By implementing Workload Identity Federation instead, the GCP project trusts the AWS STS token issuer directly; the EC2 instance exchanges its local AWS identity token for a temporary, short-lived GCP access token on the fly, eliminating static credentials entirely across cloud boundaries.

---

## 2. The Network: Connecting the Pieces

Networking is the domain where the most subtle and dangerous multi-cloud architectural failures take place. Engineers who attempt to build a Google Cloud Platform network using Amazon Web Services patterns inevitably introduce unnecessary routing complexity and artificial bandwidth bottlenecks. Understanding the structural boundary of the virtual private network is the primary prerequisite for building resilient cross-cloud topologies.

### The Virtual Private Cloud (VPC) Paradigms

The Virtual Private Cloud (VPC) represents an isolated software-defined network boundary inside the cloud provider infrastructure. While every cloud offers private networking, their foundational routing scopes differ dramatically between regional isolation and global connectivity.

**AWS VPC (The Regional Fortress)**: AWS VPCs are strictly **regional** constructs bound to a single geographic region such as `us-east-1`. Subnets created inside an AWS VPC are further constrained because each subnet is bound to a single Availability Zone (AZ). If an enterprise provisions a VPC in `us-east-1` and another VPC in `eu-west-1`, the two networks are completely isolated from each other. Connecting these environments requires establishing explicit VPC Peering connections, configuring AWS Transit Gateways, or deploying IPSec VPN tunnels across public internet gateways.

```text
+-------------------------------------------------------------+
| AWS Regional Architecture                                   |
|                                                             |
|  [VPC us-east-1 (10.0.0.0/16)]                              |
|   |-- [Subnet AZ-a (10.0.1.0/24)]                           |
|   |-- [Subnet AZ-b (10.0.2.0/24)]                           |
|                                                             |
|          ^                                                  |
|          | (Requires explicit Peering or Transit Gateway)   |
|          v                                                  |
|                                                             |
|  [VPC eu-west-1 (10.1.0.0/16)]                              |
|   |-- [Subnet AZ-a (10.1.1.0/24)]                           |
+-------------------------------------------------------------+
```

```bash
# Create a VPC in AWS
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --region us-east-1

# Create subnets in specific AZs
aws ec2 create-subnet \
    --vpc-id vpc-abc123 \
    --cidr-block 10.0.1.0/24 \
    --availability-zone us-east-1a

aws ec2 create-subnet \
    --vpc-id vpc-abc123 \
    --cidr-block 10.0.2.0/24 \
    --availability-zone us-east-1b

# Peer two VPCs (even in the same region, it's explicit)
aws ec2 create-vpc-peering-connection \
    --vpc-id vpc-abc123 \
    --peer-vpc-id vpc-def456 \
    --peer-region eu-west-1
```

**GCP VPC (The Global Backbone)**: In stark contrast to AWS, GCP VPCs are inherently **global** resources that span every Google Cloud region worldwide by default. Subnets inside a GCP VPC are regional entities, which means a single subnet encompasses all zones within that region. Because the VPC itself is global, a Compute Engine instance in Tokyo can communicate directly with an instance in Frankfurt using private RFC 1918 IP addresses over Google private global fiber backbone without configuring VPN tunnels, peering connections, or external gateways.

```text
+-------------------------------------------------------------+
| GCP Global Architecture                                     |
|                                                             |
|  [Global VPC (default)]                                     |
|   |                                                         |
|   |-- [Subnet us-central1 (10.128.0.0/20)]                  |
|   |      (VM A: 10.128.0.2)                                 |
|   |                                                         |
|   |-- [Subnet europe-west1 (10.132.0.0/20)]                 |
|          (VM B: 10.132.0.2)                                 |
|                                                             |
|  * VM A and VM B route directly to each other internally.   |
+-------------------------------------------------------------+
```

```bash
# Create a custom VPC (it's automatically global)
gcloud compute networks create my-vpc --subnet-mode=custom

# Create subnets in different regions — same VPC
gcloud compute networks subnets create us-subnet \
    --network=my-vpc \
    --region=us-central1 \
    --range=10.0.1.0/24

gcloud compute networks subnets create eu-subnet \
    --network=my-vpc \
    --region=europe-west1 \
    --range=10.0.2.0/24

# No peering needed! VMs in us-subnet and eu-subnet
# can talk to each other over private IPs immediately.
```

**Azure VNet (The Regional Network)**: Azure Virtual Networks (VNets) operate on a regional paradigm similar to AWS. An Azure VNet is deployed into a specific geographic region such as `East US`, and subnets created within that VNet span all Availability Zones within that region by default. To connect two disparate VNets, platform engineers must establish VNet Peering connections or deploy Azure Virtual WAN to coordinate enterprise routing topologies.

```bash
# Create a VNet in Azure
az network vnet create \
    --resource-group my-rg \
    --name my-vnet \
    --address-prefix 10.0.0.0/16 \
    --location eastus

# Create subnets (not AZ-specific by default)
az network vnet subnet create \
    --resource-group my-rg \
    --vnet-name my-vnet \
    --name web-subnet \
    --address-prefixes 10.0.1.0/24

# Peer two VNets
az network vnet peering create \
    --resource-group my-rg \
    --name vnet1-to-vnet2 \
    --vnet-name my-vnet \
    --remote-vnet /subscriptions/<sub>/resourceGroups/rg2/providers/Microsoft.Network/virtualNetworks/vnet2 \
    --allow-vnet-access
```

Network routing semantics exhibit significant behavioral differences that impact packet flow and firewall enforcement across cloud providers. In AWS, route tables are explicitly associated with subnets, containing static CIDR routes alongside target gateways such as Internet Gateways or NAT Gateways. In GCP, routing tables are properties of the global VPC itself; routes apply globally across all subnets unless constrained by instance network tags. In Azure, system routes automatically route traffic between subnets and to the internet, but administrators override these defaults using User Defined Routes (UDRs) associated with subnets.

Private service connectivity mechanisms also reflect these architectural philosophies. AWS provides AWS PrivateLink, which deploys Interface VPC Endpoints backed by Elastic Network Interfaces (ENIs) inside consumer subnets. GCP implements Private Service Connect (PSC), which maps producer services to consumer forwarding rules and internal IP endpoints without IP address overlap. Azure delivers Azure Private Link, exposing managed PaaS offerings or custom services through private endpoints within virtual network subnets. These mechanisms permit applications to consume managed services without traversing the public internet.

Security perimeter enforcement differs substantially across provider firewalls. AWS relies on stateful Security Groups applied at the network interface level, supplemented by stateless Network Access Control Lists (NACLs) evaluated at subnet boundaries. GCP enforces stateful VPC Firewall Rules at the network level, utilizing network tags, IP ranges, or service accounts to target specific compute instances. Azure employs Network Security Groups (NSGs) containing prioritized stateful rules applied to subnets or network interfaces, alongside Application Security Groups (ASGs) for workload categorization.

Maximum Transmission Unit (MTU) sizing introduces unexpected packet fragmentation and throughput degradation during multi-cloud migrations. AWS VPC supports jumbo frames with an MTU of 9001 bytes for traffic between EC2 instances within the same region, though traffic leaving the VPC drops to standard 1500 bytes. Google Cloud VPC defaults to an MTU of 1460 bytes to accommodate internal SDN encapsulation headers, although custom VPCs can be configured for 1500 or 8896 bytes. Microsoft Azure VNets enforce a standard 1500-byte MTU. When routing traffic across cross-cloud IPSec VPN tunnels or direct interconnects, architects must configure Maximum Segment Size (MSS) clamping to prevent silent packet drops caused by MTU mismatches.

### Networking Quick-Reference Table

| Concept | AWS | GCP | Azure |
| :--- | :--- | :--- | :--- |
| Private network | VPC (regional) | VPC (global) | VNet (regional) |
| Subnet scope | Per Availability Zone | Per Region | Per VNet (not AZ-bound) |
| Cross-region private | VPC Peering / Transit GW | Automatic (same VPC) | VNet Peering / vWAN |
| Firewall rules | Security Groups + NACLs | Firewall Rules (on VPC) | NSGs + Azure Firewall |
| Private DNS | Route 53 Private Zones | Cloud DNS Private Zones | Azure Private DNS |
| VPN gateway | VPN Gateway | Cloud VPN | VPN Gateway |
| Direct connect | Direct Connect | Cloud Interconnect | ExpressRoute |

### Traffic Management and Load Balancing

Directing client internet traffic to internal compute nodes requires coordinating authoritative DNS systems with Layer 4 and Layer 7 load balancers.

*   **AWS**: Route 53 delivers managed authoritative DNS with weighted, latency, and failover routing policies. Layer 7 HTTP/HTTPS traffic is handled by regional Application Load Balancers (ALBs). To achieve multi-region global distribution on AWS, architects must front regional ALBs with AWS Global Accelerator or CloudFront distributions.
*   **GCP**: Cloud DNS manages zone records. Google Cloud Load Balancing delivers an architectural advantage through its Global External HTTP(S) Load Balancer, which advertises a single Anycast IP address across Google global edge network, terminating connections near users and routing to backends worldwide.
*   **Azure**: Azure DNS manages public and private zones. Azure Application Gateway delivers regional Layer 7 load balancing with optional Web Application Firewall (WAF) capabilities, while Azure Front Door provides a global Anycast Layer 7 reverse proxy, content delivery network, and global routing layer.

| Load Balancing Feature | AWS | GCP | Azure |
| :--- | :--- | :--- | :--- |
| Regional L7 (HTTP) | ALB | Regional HTTP(S) LB | Application Gateway |
| Global L7 (HTTP) | CloudFront + ALB | Global HTTP(S) LB | Front Door |
| Regional L4 (TCP/UDP) | NLB | Regional TCP/UDP LB | Load Balancer (Standard) |
| Global L4 (TCP/UDP) | Global Accelerator | Global TCP Proxy LB | Front Door / Traffic Manager |
| DNS-based routing | Route 53 | Cloud DNS (limited) | Traffic Manager |
| CDN | CloudFront | Cloud CDN | Azure CDN / Front Door |
| Single global IP? | No (multi-region = multi-IP) | Yes (Anycast) | Yes (Front Door) |

**Pause and predict:** An engineering team plans to migrate a microservices architecture from AWS to GCP by creating three separate VPCs representing production, staging, and development in identical CIDR ranges (10.0.0.0/16). What routing constraint will they encounter if they later attempt to connect these networks via VPC Network Peering, and how does GCP Shared VPC offer a superior multi-project topology?

VPC Network Peering in Google Cloud forbids any overlapping IP address ranges between peered networks; attempting to peer VPCs with identical 10.0.0.0/16 subnets will fail completely at creation time. Instead of creating disconnected VPCs with colliding IP allocations, the team should implement GCP Shared VPC, where a centralized host project defines a non-overlapping global network and delegates regional subnets to separate service projects for production, staging, and development.

---

## 3. Compute Primitives: From Bare Metal to Auto Scaling

Before container orchestration and serverless architectures dominated cloud platforms, raw virtual machines served as the core foundation of scalable infrastructure. Understanding basic compute primitives remains vital for operating stateful databases, legacy monoliths, and specialized machine learning workloads that demand bare-metal hardware access.

### Virtual Machines

The baseline virtual machine nomenclature across the hyperscalers is widely recognized: Elastic Compute Cloud (EC2) on AWS, Google Compute Engine (GCE) on GCP, and Azure Virtual Machines on Microsoft Azure. Each service provisions virtualized hardware slices backed by hypervisors, but machine image distribution and instance lifecycle mechanisms diverge significantly across platforms.

Amazon Machine Images (AMIs) in AWS are strictly regional assets; an AMI created in `us-east-1` must be explicitly replicated to `us-west-2` before any virtual machines can launch in that target region. In contrast, GCP Custom Images are global resources that are immediately accessible across every Google Cloud region without manual replication. Microsoft Azure provides the Azure Compute Gallery to automate multi-region image replication, version tracking, and deployment sharing across subscriptions.

```bash
# AWS: Launch an EC2 instance
aws ec2 run-instances \
    --image-id ami-0abcdef1234567890 \
    --instance-type t3.medium \
    --key-name my-key \
    --subnet-id subnet-abc123 \
    --security-group-ids sg-abc123

# GCP: Launch a Compute Engine instance
gcloud compute instances create my-vm \
    --machine-type=e2-medium \
    --zone=us-central1-a \
    --image-family=debian-12 \
    --image-project=debian-cloud

# Azure: Launch a Virtual Machine
az vm create \
    --resource-group my-rg \
    --name my-vm \
    --image Ubuntu2204 \
    --size Standard_B2s \
    --admin-username azureuser \
    --generate-ssh-keys
```

### Instance Type Naming: The Hidden Complexity

Every hyperscaler adopts a proprietary alphanumeric naming convention for virtual machine instance families. Deciphering these naming schemes is critical for right-sizing workloads and preventing expensive hardware over-allocation during migrations.

| AWS (example) | GCP (example) | Azure (example) | Rough Equivalent |
| :--- | :--- | :--- | :--- |
| `t3.micro` | `e2-micro` | `Standard_B1s` | Burstable, 1 vCPU, ~1 GB |
| `t3.medium` | `e2-medium` | `Standard_B2s` | Burstable, 2 vCPU, ~4 GB |
| `m5.xlarge` | `n2-standard-4` | `Standard_D4s_v5` | General purpose, 4 vCPU, ~16 GB |
| `c5.2xlarge` | `c2-standard-8` | `Standard_F8s_v2` | Compute-optimized, 8 vCPU |
| `r5.large` | `n2-highmem-2` | `Standard_E2s_v5` | Memory-optimized, 2 vCPU |
| `p3.2xlarge` | `a2-highgpu-1g` | `Standard_NC6s_v3` | GPU instance, 1 GPU |

Modern hyperscaler compute fleets feature custom silicon and proprietary hardware virtualization offloading engines. AWS deploys the Nitro System, offloading storage, networking, and security management to dedicated ASIC cards while offering custom ARM-based Graviton processors that reduce price-performance costs. Google Cloud leverages Titan security chips and offers both standard x86 architectures and custom Tau T2A and Axion ARM processors for scale-out container workloads. Microsoft Azure implements Azure Boost to offload virtualization processes directly to dedicated hardware, pairing with custom Cobalt ARM silicon. Sizing multi-cloud workloads requires benchmarking native instruction sets and compiler optimizations rather than assuming identical throughput across vCPU allocations.

### Auto Scaling and Instance Groups

High-availability production architectures avoid running standalone virtual machines in favor of auto-scaling groups that dynamically adjust capacity and automatically replace unhealthy nodes when failures occur.

*   **AWS: Auto Scaling Groups (ASG)**. Engineers define a Launch Template specifying AMI ID, instance size, and IAM instance profiles, and deploy an ASG that distributes instances across multiple Availability Zones within a region.
*   **GCP: Managed Instance Groups (MIG)**. Engineers configure an Instance Template. MIGs can be deployed as Zonal groups within a single zone or Regional groups that distribute instances evenly across multiple zones for elevated resilience.
*   **Azure: Virtual Machine Scale Sets (VMSS)**. Azure VMSS manages fleets of identical, load-balanced virtual machines, integrating with Azure Monitor to scale capacity based on performance telemetry or schedules.

Spot and preemptible virtual machine offerings allow enterprises to acquire surplus compute capacity at discounts of up to ninety percent. However, interruption handling procedures differ significantly across hyperscalers. AWS emits a two-minute warning prior to terminating an EC2 Spot Instance via CloudWatch Events and the local metadata service. In contrast, GCP delivers a thirty-second ACPI shutdown notification before preemption, and Azure issues a thirty-second Scheduled Event alert. Systems operating on Spot capacity must automate graceful connection draining and checkpointing within these constrained shutdown windows.

### Hypothetical scenario: The Unhealthy Health Check

An engineering group translated an AWS web tier architecture to Microsoft Azure. In AWS, an Application Load Balancer routed traffic to an Auto Scaling Group. The ASG was configured with ELB health checks; whenever an EC2 instance failed its HTTP `/healthz` check, the ASG automatically terminated that unhealthy instance and provisioned a fresh replacement.

When rebuilding the system in Azure, the team configured an Azure Load Balancer in front of a Virtual Machine Scale Set. They set up the load balancer health probe to inspect `/healthz`. During an unexpected memory leak under heavy traffic, the load balancer correctly stopped routing requests to failing instances. However, the unhealthy virtual machines remained running indefinitely and were never replaced, causing the cluster to run out of healthy capacity and drop customer traffic.

The team failed to recognize that in Microsoft Azure, load balancer health probes govern traffic routing exclusively. Unlike AWS ASGs, an Azure Load Balancer does not possess permission to terminate or recreate virtual machines in a VMSS. To achieve automated instance replacement, the engineers needed to configure the Application Health Extension directly on the VMSS definition, which bridges application health status to the VMSS auto-healing engine.

**Pause and predict:** A platform team configures an Azure Virtual Machine Scale Set behind an Azure Load Balancer with an HTTP health probe on port 8080. If an application process crashes and starts returning HTTP 500 status codes, will the Azure Load Balancer replace the failing virtual machine instance automatically?

The Azure Load Balancer will merely stop forwarding new network connections to the failing instance, leaving the unhealthy virtual machine running in place indefinitely. Automatic instance replacement requires enabling the Application Health Extension or configuring an auto-repair policy on the VMSS itself, which actively monitors guest health and triggers node recreation when failures occur.

---

## 4. The Container Ecosystem: Standalone, Managed K8s, and Serverless

Modern cloud-native architectures rarely deploy applications directly onto bare virtual machine operating systems. Instead, workloads run packaged inside OCI-compliant container images managed by standalone serverless platforms or enterprise Kubernetes orchestrators. Hyperscalers offer several distinct abstraction tiers for running containerized microservices.

### Standalone Containers (Containers as a Service)

When an engineering team wants to run a containerized microservice without the administrative burden of operating a Kubernetes cluster, hyperscalers provide Containers-as-a-Service (CaaS) platforms:

*   **AWS: ECS with Fargate**. Elastic Container Service (ECS) is Amazon proprietary container orchestrator, while AWS Fargate provides the underlying serverless compute engine. Engineers create Task Definitions specifying CPU, memory, and container images, and AWS schedules and executes the tasks without exposing virtual machines. However, Fargate does not scale to zero; at least one task must remain active.
*   **GCP: Cloud Run**. Cloud Run is built on open Knative standards and executes stateless HTTP containers. Its primary competitive advantage is native scale-to-zero capability; when no incoming requests exist, Cloud Run scales active instances to zero, reducing compute billing to absolute zero during idle periods.
*   **Azure: Azure Container Instances (ACI) or Azure Container Apps (ACA)**. ACI provides lightweight single-container execution ideal for quick batch jobs. Azure Container Apps is a serverless application platform built on Kubernetes and KEDA (Kubernetes Event-driven Autoscaling), delivering scale-to-zero, microservice traffic splitting, and background queue workers.

```bash
# AWS: Deploy a container to ECS Fargate (simplified)
aws ecs create-service \
    --cluster my-cluster \
    --service-name my-service \
    --task-definition my-task:1 \
    --desired-count 2 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-abc],securityGroups=[sg-abc]}"

# GCP: Deploy a container to Cloud Run (one command!)
gcloud run deploy my-service \
    --image=gcr.io/my-project/my-app:latest \
    --platform=managed \
    --region=us-central1 \
    --allow-unauthenticated

# Azure: Deploy a container to Azure Container Apps
az containerapp create \
    --name my-app \
    --resource-group my-rg \
    --environment my-env \
    --image myregistry.azurecr.io/my-app:latest \
    --target-port 8080 \
    --ingress external
```

### Serverless Container Comparison

| Feature | AWS ECS Fargate | GCP Cloud Run | Azure Container Apps |
| :--- | :--- | :--- | :--- |
| Scale to zero | No (minimum 1 task) | Yes | Yes |
| Max request timeout | No limit (long-running) | 60 min (HTTP) | 30 min |
| GPU support | Yes | Yes | Yes |
| Built on | Proprietary (ECS) | Knative | Kubernetes + KEDA |
| Min billing unit | 1 second | 100ms | 1 second |
| Max vCPU per instance | 16 | 8 | 4 |
| Max memory per instance | 120 GB | 32 GB | 16 GB |
| VPC integration | Native | VPC Connector | VNet integration |
| Sidecar containers | Yes | Yes | Yes |

### Managed Kubernetes: The Great Equalizer

Kubernetes serves as the universal operating system of modern cloud computing. Because Kubernetes APIs are standardized by the Cloud Native Computing Foundation (CNCF), a declarative Deployment manifest behaves identically whether applied to Amazon EKS, Google GKE, or Azure AKS. Platform teams interact with these managed clusters using standard `kubectl` tooling. Production clusters should target modern versions like Kubernetes 1.35+ to benefit from updated Gateway API capabilities and security hardening.

```text
Managed Kubernetes Architecture Comparison

AWS EKS                      GCP GKE                      Azure AKS
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│  Control Plane   │         │  Control Plane   │         │  Control Plane   │
│  (AWS-managed)   │         │  (Google-managed) │         │  (Azure-managed) │
│  ┌────────────┐  │         │  ┌────────────┐  │         │  ┌────────────┐  │
│  │ API Server │  │         │  │ API Server │  │         │  │ API Server │  │
│  │ etcd       │  │         │  │ etcd       │  │         │  │ etcd       │  │
│  │ scheduler  │  │         │  │ scheduler  │  │         │  │ scheduler  │  │
│  │ controller │  │         │  │ controller │  │         │  │ controller │  │
│  └────────────┘  │         │  └────────────┘  │         │  └────────────┘  │
│  Cost: ~$73/mo   │         │  Cost: $0 (std)  │         │  Cost: $0 (free) │
│                  │         │  $73/mo (autoplt) │         │  $73/mo (std)    │
└────────┬─────────┘         └────────┬─────────┘         └────────┬─────────┘
         │                            │                            │
┌────────▼─────────┐         ┌────────▼─────────┐         ┌────────▼─────────┐
│  Worker Nodes    │         │  Worker Nodes    │         │  Worker Nodes    │
│  ┌────────────┐  │         │  ┌────────────┐  │         │  ┌────────────┐  │
│  │ Managed    │  │         │  │ Standard:  │  │         │  │ Node Pools │  │
│  │ Node Groups│  │         │  │  Node Pools│  │         │  │ (VMSS-     │  │
│  │ (EC2-based)│  │         │  │ Autopilot: │  │         │  │  backed)   │  │
│  │            │  │         │  │  No nodes  │  │         │  │            │  │
│  │ YOU manage │  │         │  │  to manage │  │         │  │ YOU manage │  │
│  └────────────┘  │         │  └────────────┘  │         │  └────────────┘  │
│                  │         │                  │         │                  │
│  CNI: VPC CNI    │         │  CNI: Dataplane  │         │  CNI: Azure CNI  │
│  (pod = VPC IP)  │         │  V2 (Cilium/eBPF)│         │  or CNI Overlay  │
│                  │         │                  │         │                  │
│  Auth: IAM +     │         │  Auth: Google    │         │  Auth: Entra ID  │
│  OIDC (complex)  │         │  IAM (native)    │         │  + Azure RBAC    │
└──────────────────┘         └──────────────────┘         └──────────────────┘
```

*   **AWS EKS (Elastic Kubernetes Service)**: Highly flexible and modular, but demands greater operational maintenance from platform teams. Engineers manage node groups, reconcile IAM authenticator mappings with Kubernetes RBAC, and handle core add-on lifecycle updates.
*   **GCP GKE (Google Kubernetes Engine)**: Regarded as the most mature managed Kubernetes implementation in the cloud. GKE Autopilot mode abstracts worker nodes completely, managing cluster scaling, node OS patching, and security hardening while charging strictly for requested pod resources.
*   **Azure AKS (Azure Kubernetes Service)**: Provides tight integration with Microsoft Entra ID authentication and Azure RBAC role assignments, backed by Virtual Machine Scale Sets for worker node execution.

```bash
# AWS: Create an EKS cluster
eksctl create cluster \
    --name my-cluster \
    --region us-east-1 \
    --version 1.35 \
    --nodegroup-name workers \
    --node-type t3.medium \
    --nodes 3

# GCP: Create a GKE Autopilot cluster
gcloud container clusters create-auto my-cluster \
    --region=us-central1 \
    --cluster-version=1.35

# Azure: Create an AKS cluster
az aks create \
    --resource-group my-rg \
    --name my-cluster \
    --kubernetes-version 1.35 \
    --node-count 3 \
    --node-vm-size Standard_B2s \
    --generate-ssh-keys
```

```yaml
# A standard Kubernetes Deployment is the ultimate Rosetta Stone.
# This exact manifest works seamlessly across EKS, GKE, and AKS.
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rosetta-frontend
  labels:
    app: frontend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: web
        image: nginx:1.25-alpine
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 250m
            memory: 256Mi
```

Managing ingress traffic into Kubernetes clusters reveals contrasting integration models across providers. AWS platform teams deploy the AWS Load Balancer Controller to dynamically provision regional ALBs or NLBs based on Ingress or Gateway API declarations. In GKE, Google Cloud provides the native GKE Gateway Controller, enabling multi-cluster routing, edge SSL termination, and Anycast load balancing directly from Kubernetes CRDs. In Azure AKS, ingress is commonly managed via the Application Gateway Ingress Controller (AGIC) or the managed Azure Application Routing add-on, bridging Kubernetes services to Azure Application Gateways.

Worker node autoscaling has also evolved rapidly away from legacy in-tree cluster autoscalers. On AWS and Azure, platform engineering teams increasingly standardize on Karpenter, an open-source, high-velocity node autoscaler that observes pending pods and provisions right-sized virtual machines directly via provider compute APIs. In GCP, GKE Autopilot and Node Auto-Provisioning (NAP) manage underlying compute infrastructure automatically, continuously resizing node pools and packing pods efficiently without requiring cluster administrators to configure external autoscaling daemons.

The Container Network Interface (CNI) configuration dictates pod density and IP exhaustion risks in managed Kubernetes clusters. Under the default AWS VPC CNI, each Kubernetes pod receives a secondary IP address directly from the underlying subnet attached to the node Elastic Network Interface (ENI). This architecture rapidly depletes enterprise RFC 1918 CIDR blocks and restricts the maximum number of pods per node based on instance-type ENI limits, often forcing teams to configure prefix delegation or secondary VPC CIDR ranges. In contrast, GKE Dataplane V2 leverages Cilium eBPF to route pod traffic without iptables overhead, using VPC-native alias IP ranges that avoid consuming primary node interface addresses. Azure offers both traditional Azure CNI, which allocates VNet IPs per pod, and Azure CNI Overlay, which provisions a dedicated private overlay network to preserve scarce enterprise VNet IP space.

### Managed Kubernetes Comparison

| Feature | AWS EKS | GCP GKE | Azure AKS |
| :--- | :--- | :--- | :--- |
| Control plane cost | ~$73/month | Free (Standard), ~$73 (Autopilot/Enterprise) | Free (Free tier), ~$73 (Standard) |
| Serverless nodes | Fargate profiles | Autopilot (fully managed) | Virtual Nodes (ACI-backed) |
| Default CNI | VPC CNI (VPC IPs to pods) | Dataplane V2 (Cilium/eBPF) | Azure CNI / CNI Overlay |
| Node auto-provisioning | Karpenter | Autopilot / NAP | Karpenter (preview) |
| Max nodes per cluster | 5,000 | 15,000 | 5,000 |
| Cluster creation time | ~15 minutes | ~5 minutes (Autopilot) | ~8 minutes |
| Built-in service mesh | App Mesh (deprecated) | Istio (managed) | Istio (managed) |
| Windows node support | Yes | Yes | Yes |
| GPU support | Yes | Yes (with drivers) | Yes |
| Multi-cluster management | None (use Argo/Flux) | Fleet (multi-cluster) | Azure Arc |

### Serverless Functions

For event-driven microservices that run short-lived execution logic triggered by object uploads, database mutations, or HTTP webhooks, serverless function runtimes provide instant compute scaling:

*   **AWS: AWS Lambda**. The serverless industry pioneer. Deeply integrated with AWS event buses like SQS, SNS, EventBridge, and S3 bucket notifications.
*   **GCP: Cloud Functions (2nd gen)**. Built directly on top of Google Cloud Run infrastructure, supporting container images, multi-concurrency, and Eventarc event routing.
*   **Azure: Azure Functions**. Features declarative input and output bindings that connect function execution to Cosmos DB, Storage Queues, or Service Bus without boilerplate connection code, alongside Durable Functions for stateful orchestrations.

### Serverless Functions Comparison

| Feature | AWS Lambda | GCP Cloud Functions | Azure Functions |
| :--- | :--- | :--- | :--- |
| Max execution time | 15 minutes | 60 minutes (2nd gen) | 10 min (Consumption), unlimited (Dedicated) |
| Max memory | 10 GB | 32 GB (2nd gen) | 14 GB (Premium) |
| Languages | Node, Python, Java, Go, .NET, Ruby, custom | Node, Python, Java, Go, .NET, Ruby, PHP | Node, Python, Java, C#, F#, PowerShell, custom |
| Cold start | ~100-500ms | ~100-500ms | ~200ms-2s (Consumption) |
| Provisioned concurrency | Yes | Yes (min instances) | Yes (Premium plan) |
| Container image support | Yes | Yes (2nd gen) | Yes |
| Event sources | 200+ AWS integrations | Eventarc + Pub/Sub | Event Grid + Service Bus |
| Unique feature | Layers, Extensions | Built on Cloud Run | Durable Functions (stateful workflows) |
| Free tier | 1M requests/month | 2M invocations/month | 1M executions/month |

**Pause and predict:** A deployment running on AWS EKS utilizes the default Amazon VPC CNI across three small subnets (/24 prefix each). If the engineering team scales the deployment to four hundred pods, what specific networking failure will occur, and why does GKE Dataplane V2 or Azure CNI Overlay avoid this address space exhaustion?

The Amazon VPC CNI assigns native VPC IP addresses directly to every pod, which will completely exhaust the available IP addresses in those small subnets and cause new pod scheduling to fail with address allocation errors. In contrast, GKE Dataplane V2 and Azure CNI Overlay utilize private overlay networks or secondary CIDR alias ranges for pods, allowing high pod density without exhausting the primary subnet IP allocations of the underlying virtual private cloud.

---

## 5. Storage, Databases, and Observability

Operating enterprise workloads reliably requires persistent data storage, transactional database management, and comprehensive observability pipelines. Translating storage and telemetry architectures between hyperscalers demands evaluating latency requirements, consistency models, and operational overhead.

### Storage Paradigms

Object storage provides durable, highly available unstructured data storage for media assets, data lakes, and automated backups across all three cloud providers.

*   **AWS: Amazon S3 (Simple Storage Service)**. The foundational cloud object storage standard. Data is organized into globally unique bucket names constrained to a specific chosen region.
*   **GCP: Cloud Storage (GCS)**. Functionally equivalent to S3, offering regional, dual-region, and multi-region bucket configurations with strong global consistency.
*   **Azure: Azure Blob Storage**. Contained within an Azure Storage Account. Engineers provision containers, inside of which individual block, append, or page blobs reside.

```bash
# AWS: Upload a file to S3
aws s3 cp my-file.tar.gz s3://my-bucket/backups/

# GCP: Upload a file to Cloud Storage
gcloud storage cp my-file.tar.gz gs://my-bucket/backups/

# Azure: Upload a file to Blob Storage
az storage blob upload \
    --account-name mystorageaccount \
    --container-name backups \
    --file my-file.tar.gz \
    --name my-file.tar.gz
```

### Storage Tiers Comparison

All three providers implement tiered storage classes to balance access latency against long-term storage economics. Hot tiers support frequent access with lower per-operation fees, whereas archival cold tiers drastically reduce per-gigabyte monthly costs in exchange for retrieval fees and minimum retention durations.

| Access Pattern | AWS S3 | GCP Cloud Storage | Azure Blob Storage |
| :--- | :--- | :--- | :--- |
| Frequently accessed | S3 Standard | Standard | Hot |
| Infrequent access | S3 Standard-IA | Nearline (30-day min) | Cool (30-day min) |
| Archival | S3 Glacier Instant Retrieval | Coldline (90-day min) | Cold (90-day min) |
| Deep archive | S3 Glacier Deep Archive | Archive (365-day min) | Archive (180-day min) |
| Intelligent tiering | S3 Intelligent-Tiering | Autoclass | Access tier change (manual/policy) |
| ~Cost per GB/month (hot) | $0.023 | $0.020 | $0.018 |
| ~Cost per GB/month (cold) | $0.004 (Glacier IR) | $0.004 (Coldline) | $0.002 (Cold) |
| Minimum storage duration | None (Standard) | None (Standard) | None (Hot) |

All three hyperscalers now deliver strong read-after-write consistency for PUT and DELETE operations on object storage. Data lifecycle policies automate the transition of objects between access tiers based on prefix rules or object age, ensuring that aging backups automatically flow from expensive hot storage into deep archival tiers. Pre-signed URLs in AWS S3 and signed URLs in GCP grant time-bounded read or write access to external clients without exposing cloud credentials, while Azure Shared Access Signatures (SAS) deliver granular policy controls governing IP restrictions, protocols, and specific CRUD actions.

Block storage delivers persistent, high-IOPS virtual disks attached directly to virtual machines: Elastic Block Store (EBS) on AWS, Persistent Disks on GCP, and Azure Managed Disks on Microsoft Azure. EBS volumes support general-purpose SSDs (gp3) alongside provisioned IOPS volumes (io2 Block Express) designed for mission-critical relational databases. GCP offers balanced persistent disks and Hyperdisk options with independently provisioned IOPS and throughput. Azure provides Premium SSD and Ultra Disk options capable of achieving sub-millisecond latencies for demanding transaction processing systems.

### Relational Databases

Managed relational database services automate hardware provisioning, database engine patching, point-in-time backups, and multi-availability-zone failover across all three major cloud providers:

*   **AWS**: Amazon RDS supports standard PostgreSQL, MySQL, MariaDB, and commercial engines. Amazon Aurora provides a proprietary distributed cloud-native storage engine with six-way replication across three AZs for extreme performance.
*   **GCP**: Cloud SQL provides managed PostgreSQL and MySQL instances. Cloud Spanner delivers horizontally scalable, globally distributed relational transactions with external consistency backed by atomic clocks (TrueTime API).
*   **Azure**: Azure Database for PostgreSQL and MySQL deliver fully managed open-source database engines. Azure Cosmos DB provides a multi-model globally distributed NoSQL database with relational APIs.

Distributed database consistency models represent a critical architectural fork in multi-cloud system design. Google Cloud Spanner leverages proprietary TrueTime hardware clocks to guarantee external consistency (linearizability) across global regions without locking bottlenecks. Amazon Aurora decouples SQL execution nodes from a distributed storage volume that replicates write operations across three Availability Zones. Azure Cosmos DB allows architects to configure five distinct consistency levels ranging from Strong to Eventual consistency, trading consistency guarantees against latency and availability based on specific application requirements.

Relational database connection pooling and failover orchestration require distinct architectural patterns across cloud providers. High-concurrency serverless microservices connecting to PostgreSQL instances can easily exhaust database connection pools. AWS addresses this challenge with Amazon RDS Proxy, a fully managed, highly available database proxy that pools and shares connections while preserving application state during automated multi-AZ failovers. Google Cloud relies on the Cloud SQL Auth Proxy or serverless VPC access connectors to securely tunnel connections and manage IAM-based database authentication. Microsoft Azure provides built-in PgBouncer integration directly inside Azure Database for PostgreSQL Flexible Server, allowing engineering teams to handle connection spikes without provisioning separate intermediate compute instances.

### Database Service Translation Table

| Database Type | AWS | GCP | Azure |
| :--- | :--- | :--- | :--- |
| Managed PostgreSQL/MySQL | RDS | Cloud SQL | Database for PostgreSQL/MySQL |
| High-perf relational | Aurora | AlloyDB | Hyperscale (Citus) |
| Global relational | Aurora Global DB | Cloud Spanner | Cosmos DB (relational API) |
| Key-value / NoSQL | DynamoDB | Firestore / Bigtable | Cosmos DB |
| In-memory cache | ElastiCache (Redis) | Memorystore | Azure Cache for Redis |
| Document database | DocumentDB | Firestore | Cosmos DB (MongoDB API) |
| Data warehouse | Redshift | BigQuery | Synapse Analytics |
| Search | OpenSearch Service | (Elastic on GCP) | Azure AI Search |

### Observability and Telemetry

Diagnosing distributed system degradation across multi-cloud topologies requires collecting application logs, runtime performance metrics, and distributed request traces into cohesive telemetry backends:

*   **AWS**: Amazon CloudWatch collects metrics and application logs. AWS X-Ray captures distributed traces across services. AWS observability tooling can feel fragmented across consoles, frequently driving engineering teams to deploy centralized OpenSearch or Prometheus solutions.
*   **GCP**: Google Cloud Operations Suite (formerly Stackdriver) delivers a unified observability platform. Logs, metrics, distributed traces (Cloud Trace), and CPU/memory profiling (Cloud Profiler) share a tightly integrated user interface and querying structure.
*   **Azure**: Azure Monitor serves as the central observability hub. Log Analytics workspaces provide high-performance log querying using the Kusto Query Language (KQL), while Application Insights delivers deep code-level tracing and application performance monitoring.

Telemetry ingestion costs and log retention policies represent significant operational expenses across all three platforms. In AWS, CloudWatch Logs charges for ingestion volume and archival storage, often incentivizing teams to export logs to S3 for cost optimization. Google Cloud Logging includes a generous monthly free ingestion allocation per project, routing logs through log sinks to BigQuery or Cloud Storage for long-term analytical queries. Azure Log Analytics bills per gigabyte ingested, allowing teams to designate low-cost Basic Logs for high-volume debug data that does not require real-time alerting.

| Observability Pillar | AWS | GCP | Azure |
| :--- | :--- | :--- | :--- |
| Metrics | CloudWatch Metrics | Cloud Monitoring | Azure Monitor Metrics |
| Logs | CloudWatch Logs | Cloud Logging | Log Analytics |
| Tracing | X-Ray | Cloud Trace | Application Insights |
| Dashboards | CloudWatch Dashboards | Cloud Monitoring Dashboards | Azure Dashboards / Grafana |
| Alerting | CloudWatch Alarms + SNS | Cloud Alerting | Azure Monitor Alerts |
| APM | X-Ray + CloudWatch | Cloud Profiler + Trace | Application Insights |
| Unified experience? | No (fragmented) | Yes (Cloud Operations suite) | Mostly (Monitor as hub) |

---

## 6. CI/CD: Building and Deploying Across Clouds

Every major cloud provider maintains a native Continuous Integration and Continuous Deployment (CI/CD) ecosystem. While many platform teams adopt third-party orchestrators such as GitHub Actions, understanding the native delivery pipelines of each hyperscaler is essential because native tools integrate seamlessly with cloud IAM, private artifact registries, and deployment targets.

### CI/CD Service Mapping

| CI/CD Capability | AWS | GCP | Azure |
| :--- | :--- | :--- | :--- |
| Source control | CodeCommit (deprecated) | Cloud Source Repos (deprecated) | Azure Repos |
| Build service | CodeBuild | Cloud Build | Azure Pipelines |
| Pipeline orchestration | CodePipeline | Cloud Build (triggers + steps) | Azure Pipelines (multi-stage) |
| Artifact registry | ECR (containers), CodeArtifact (packages) | Artifact Registry | Azure Container Registry, Azure Artifacts |
| Deployment service | CodeDeploy | Cloud Deploy | Azure Pipelines (release) |
| IaC deployment | CloudFormation | Deployment Manager (deprecated) / Terraform | ARM Templates / Bicep |

### The Philosophical Difference

AWS CodePipeline operates as a rigid, stage-based workflow orchestrator where discrete stages (Source, Build, Test, Deploy) pass versioned S3 artifacts between actions. GCP Cloud Build functions as a containerized step-based builder, executing sequential container actions defined in YAML to produce artifacts that Google Cloud Deploy promotes across environments. Azure DevOps Pipelines provides a comprehensive enterprise suite, featuring multi-stage YAML pipelines that natively manage environments, manual approval gates, and progressive release strategies such as canary and blue-green rollouts.

```yaml
# AWS CodeBuild buildspec.yml
version: 0.2
phases:
  install:
    commands:
      - echo Installing dependencies...
  build:
    commands:
      - echo Building the app...
      - docker build -t my-app .
  post_build:
    commands:
      - docker push $ECR_REPO:$CODEBUILD_RESOLVED_SOURCE_VERSION
```

```yaml
# GCP Cloud Build cloudbuild.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'us-central1-docker.pkg.dev/$PROJECT_ID/my-repo/my-app:$COMMIT_SHA', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'us-central1-docker.pkg.dev/$PROJECT_ID/my-repo/my-app:$COMMIT_SHA']
images:
  - 'us-central1-docker.pkg.dev/$PROJECT_ID/my-repo/my-app:$COMMIT_SHA'
```

```yaml
# Azure Pipelines azure-pipelines.yml
trigger:
  - main
pool:
  vmImage: 'ubuntu-latest'
steps:
  - task: Docker@2
    inputs:
      command: buildAndPush
      repository: my-app
      containerRegistry: myACRConnection
      tags: $(Build.SourceVersion)
```

Modern CI/CD pipelines across all three cloud providers eliminate static credentials by implementing OpenID Connect (OIDC) identity federation. When a GitHub Actions runner executes a deployment job, it requests a short-lived OIDC JSON Web Token (JWT) from GitHub. The runner exchanges this token with AWS STS, GCP Security Token Service, or Microsoft Entra ID to receive short-lived cloud credentials, completely eliminating the need to store long-lived access keys in pipeline secrets.

Progressive delivery patterns require tight integration with cloud monitoring telemetry to automate rollbacks when releases introduce errors. Azure Pipelines natively supports deployment gates that query Azure Monitor alert states before proceeding to subsequent production stages. In GCP, Cloud Deploy integrates with automated canary strategies and verification metrics to pause rollouts when error budgets are exceeded. In AWS, CodeDeploy manages automated traffic shifting over ALB target groups, evaluating CloudWatch alarms to trigger instantaneous rollbacks if 5xx error thresholds spike.

---

## 7. Infrastructure as Code: Native Tools

While third-party tools such as Terraform and OpenTofu represent the universal industry standard for multi-cloud provisioning, each hyperscaler maintains a proprietary Infrastructure as Code (IaC) toolchain optimized for its native resource APIs.

| Characteristic | AWS CloudFormation | GCP Deployment Manager | Azure ARM / Bicep |
| :--- | :--- | :--- | :--- |
| Language | JSON or YAML | YAML + Jinja2/Python | JSON (ARM) or Bicep (DSL) |
| State management | AWS-managed (stack state) | GCP-managed | Azure-managed |
| Rollback on failure | Automatic | Manual | Automatic |
| Preview changes | Change Sets | Preview | What-if |
| Multi-region | StackSets | Manual | Deployment Stacks |
| Community adoption | High (legacy) | Low (deprecated) | Growing (Bicep) |
| Recommendation | Use for AWS-only shops | Use Terraform/OpenTofu | Use Bicep for Azure-only |

GCP Deployment Manager is functionally deprecated in modern cloud practice; Google officially partners with HashiCorp to recommend Terraform as the primary IaC engine for GCP infrastructure. In contrast, AWS CloudFormation remains a deeply supported native tool within the AWS ecosystem, providing managed state storage and automated rollbacks. In the Microsoft ecosystem, Azure Bicep offers a modern, transparent domain-specific language that transpiles directly into Azure Resource Manager (ARM) templates, providing immediate zero-day support for newly released Azure resource provider APIs.

State storage represents another key architectural divergence between native tools and multi-cloud frameworks. Native tools store deployment state entirely within the provider managed control plane, eliminating external state locking dependencies. When utilizing Terraform or OpenTofu, engineering teams must configure secure remote state backends: an S3 bucket with DynamoDB state locking on AWS, a GCS bucket with native object locking on GCP, or an Azure Blob Storage container with native lease management on Microsoft Azure.

When teams design multi-cloud architectures, they must avoid the naive assumption that Terraform abstracts away hyperscaler differences. While Terraform delivers a uniform syntax and state management workflow across providers, an `aws_vpc` resource remains architecturally distinct from a `google_compute_network` or an `azurerm_virtual_network`. Attempting to write a single generic module that wraps disparate cloud resources introduces brittle abstractions that fail in production. Platform engineering teams achieve far greater velocity by building separate provider-specific modules that adhere strictly to native cloud patterns.

---

## 8. Pricing Models: The Most Dangerous Translation

The most expensive errors in multi-cloud engineering are frequently financial rather than architectural. While headline compute prices appear nearly identical across providers, underlying commitment structures, billing increments, and data egress fees diverge substantially.

### On-Demand Pricing (Pay-as-you-go)

All three hyperscalers charge for on-demand virtual machine compute capacity based on elapsed execution seconds. The hourly list prices for general-purpose instances with four virtual CPUs and sixteen gigabytes of memory are remarkably consistent across providers.

| Instance (~4 vCPU, 16 GB) | AWS | GCP | Azure |
| :--- | :--- | :--- | :--- |
| Instance type name | m5.xlarge | n2-standard-4 | Standard_D4s_v5 |
| On-demand (US, Linux, /hr) | ~$0.192 | ~$0.194 | ~$0.192 |
| Monthly (730 hrs) | ~$140 | ~$142 | ~$140 |

Because base compute rates are nearly indistinguishable, enterprise cost optimization depends on understanding commitment discount mechanisms, automated discount tiers, and network egress charging policies.

### Discount Mechanisms

| Discount Type | AWS | GCP | Azure |
| :--- | :--- | :--- | :--- |
| Commitment (1-3 yr) | Reserved Instances / Savings Plans | Committed Use Discounts (CUDs) | Reserved VM Instances |
| Typical 1-year savings | 30-40% | 28-37% | 30-40% |
| Typical 3-year savings | 50-60% | 52-57% | 55-65% |
| Automatic discounts | None | Sustained Use Discounts (up to 30%) | None |
| Preemptible / Spot | Spot Instances (up to 90% off) | Spot VMs (up to 91% off) | Spot VMs (up to 90% off) |
| Spot termination notice | 2 minutes | 30 seconds | 30 seconds |
| Free tier | 750 hrs/mo t2.micro (12 mo) | e2-micro always-free | 750 hrs/mo B1s (12 mo) |

Commitment discount architectures require careful financial planning. AWS Savings Plans offer flexibility by committing to a specific hourly spend across instance families and regions, whereas traditional Reserved Instances bind discounts to specific instance types. GCP Committed Use Discounts (CUDs) allow teams to commit to aggregate CPU and memory allocations across an entire project, decoupling discounts from specific machine types. Azure Reserved Virtual Machine Instances provide exchangeability policies that permit swapping reserved instance families when architectural needs shift.

### The GCP Sustained Use Discount Advantage

Google Cloud Platform distinguishes itself from competitors by automatically applying **Sustained Use Discounts (SUDs)** to steady-state workloads. If an uncommitted Compute Engine instance executes for more than twenty-five percent of a billing month, GCP incrementally reduces the hourly rate, delivering up to a thirty percent discount by month end without requiring upfront contractual commitments. On AWS and Azure, workloads run at full on-demand rates unless teams explicitly purchase Reserved Instances or Savings Plans.

### Data Egress: The Hidden Cost

Network data transfer represents the single greatest source of unexpected expenditure in multi-cloud architectures, where cross-provider bandwidth pricing compounds rapidly across distributed microservice deployments.

| Transfer Type | AWS | GCP | Azure |
| :--- | :--- | :--- | :--- |
| Ingress (data in) | Free | Free | Free |
| Same-zone traffic | Free | Free | Free |
| Cross-zone (same region) | ~$0.01/GB | Free | Free |
| Cross-region (same provider) | $0.01-0.02/GB | $0.01-0.08/GB | $0.02-0.05/GB |
| Egress to internet (first 10 TB) | ~$0.09/GB | ~$0.12/GB | ~$0.087/GB |

A critical architectural distinction is that **AWS charges for cross-Availability Zone traffic** within the same geographic region ($0.01 per GB in each direction). If a microservice distributed across two AZs for high availability transmits fifty terabytes of internal RPC traffic, the AWS network bill will include one thousand dollars in unexpected cross-zone fees. In contrast, GCP and Azure do not charge for internal cross-zone data transfer within the same region when using private IP addresses.

Network egress to the public internet represents a substantial financial burden when transferring large data sets between cloud providers. Replicating multi-terabyte database snapshots or streaming high-resolution media across clouds incurs continuous egress fees ranging from eight to twelve cents per gigabyte. Multi-cloud architectures must minimize cross-cloud data transfers by processing data locally within the originating cloud and synchronizing only compressed metadata summaries across provider boundaries.

Managed NAT gateways introduce another hidden operational cost that compounds in multi-cloud deployments. AWS charges an hourly rate of four and a half cents per NAT Gateway plus four and a half cents per gigabyte of processed data. Routing high-throughput internal traffic through a NAT Gateway instead of private VPC endpoints causes network bills to escalate dramatically. Google Cloud NAT and Azure NAT Gateway apply similar hourly and processing meters, emphasizing the architectural requirement to enforce private endpoints for internal service communication.

Establishing financial operations (FinOps) governance across disparate cloud providers requires normalizing cost allocation tags and billing telemetry. AWS provides Cost Allocation Tags that activate within AWS Cost Explorer and Cost and Usage Reports (CUR). GCP utilizes Resource Labels that export directly to BigQuery for SQL-based cost analysis, while Azure implements Resource Tags integrated with Microsoft Cost Management. Because each provider applies unique tag inheritance rules and enforces distinct character limits, multi-cloud platform teams must deploy automated policy guardrails using AWS Organizations Service Control Policies, Google Cloud Organization Policies, or Azure Policy to enforce mandatory billing metadata at resource creation time.

---

## Did You Know?

1. Google Cloud global software-defined network routes internal traffic across private transoceanic fiber-optic cables before packets ever touch the public internet, allowing its global VPC to route cross-region traffic without public gateway hops.
2. Amazon S3 was launched in 2006 as one of the earliest commercial cloud primitives and now stores more than one hundred trillion individual objects, routinely handling tens of millions of incoming requests per second worldwide.
3. Microsoft Entra ID processes more than thirty billion daily authentication requests across corporate enterprises, establishing Microsoft identity architecture as the primary authentication directory for the majority of the Fortune 500.
4. Managed Kubernetes Container Network Interface (CNI) plugins differ fundamentally between clouds: AWS VPC CNI assigns native VPC IP addresses directly to pods, while GCP Dataplane V2 and Azure CNI Overlay utilize overlay networks to prevent subnet IP address exhaustion.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
| :--- | :--- | :--- |
| **Applying AWS regional VPC logic to GCP** | Engineers assume VPCs must be explicitly peered across regions to communicate, leading to complex management. | Utilize GCP's global VPC by default. Place subnets in different regions within the exact same VPC for seamless, private connectivity. |
| **Misunderstanding IAM Roles vs Service Accounts** | Trying to attach a GCP Service Account to a resource exactly like an AWS IAM Role profile, or generating long-lived keys. | Treat GCP Service Accounts as resource identities. Use Workload Identity Federation for cross-platform access, and attach Service Accounts directly to VMs without exporting keys. |
| **Ignoring CNI differences in Managed K8s** | Assuming pod IP address exhaustion works exactly the same in EKS as it does in standard GKE. | The AWS EKS VPC CNI assigns native VPC IPs to individual pods. You must plan subnet CIDR blocks much larger in AWS than in GCP's default overlay network setup to avoid IP exhaustion. |
| **Blindly lifting and shifting CI/CD pipelines** | Translating AWS CodePipeline steps perfectly 1:1 to GitHub Actions or Azure DevOps without leveraging native features. | Redesign the pipeline around the target platform's strengths, such as utilizing Azure DevOps multi-stage release pipelines instead of rigid, single-path CodePipelines. |
| **Overlooking regional data egress costs** | Assuming data transfer between regions, or data out to the internet, costs the exact same everywhere. | Architect systems to keep high-bandwidth, chatty traffic within the exact same availability zone or region whenever possible, regardless of the cloud provider. |
| **Assuming 'Serverless' implies identical limits** | AWS Lambda has specific execution time maximums and payload limits that differ entirely from Azure Functions. | Rigorously validate payload sizes, maximum execution timeouts, and concurrent invocation limits when migrating serverless architectures. |
| **Translating AWS Tags directly to Azure Resource Groups** | AWS uses flat tags for everything. Azure relies on Resource Groups as mandatory deployment boundaries. | Do not use Azure Resource Groups just for tagging. Use them to group resources that share identical lifecycles, and use Azure Tags for billing categorizations. |
| **Ignoring cross-AZ data transfer costs on AWS** | On GCP and Azure, cross-zone traffic is free. Engineers assume the same on AWS and get surprised by bills. | On AWS, cross-AZ traffic costs ~$0.01/GB in each direction. Design services to prefer same-AZ communication for high-throughput internal calls, or accept the cost for HA. |

---

## Quiz

<details>
<summary>Question 1: When you compare equivalent services across AWS, GCP, and Azure for networking, which architectural model explains why GCP subnets route privately across regions without explicit peering connections?</summary>
When teams compare equivalent services across AWS, GCP, and Azure for networking, Google Cloud Platform (GCP) distinguishes itself because its Virtual Private Cloud (VPC) is a global construct by default. In AWS and Azure, VPCs and VNets are strictly regional entities requiring explicit peering connections, virtual network gateways, or transit routers to bridge traffic across geographies. In GCP, subnets in disparate geographic regions exist within the identical global VPC, allowing compute instances to communicate privately over Google global fiber backbone without extra peering configuration or overlay networking.
</details>

<details>
<summary>Question 2: How can engineering teams diagnose multi-cloud migration failures caused by architectural differences between AWS regional VPCs and GCP global VPCs?</summary>
To diagnose multi-cloud migration failures caused by architectural differences, architects must evaluate how IP subnetting and routing boundaries operate across cloud environments. Teams accustomed to AWS often attempt to recreate duplicate regional CIDR blocks across multiple VPCs and connect them with complex peering meshes. In GCP, because a VPC is global, subnets across all regions must possess non-overlapping IP address ranges within that single network. Diagnosing these migration failures involves checking for IP collisions, unnecessary VPC peering loops, and incorrect routing table assumptions.
</details>

<details>
<summary>Question 3: How should systems engineers design multi-cloud architectures that account for fundamental structural differences in compute instance healing between AWS and Azure?</summary>
When teams design multi-cloud architectures that account for fundamental structural differences, they must recognize that instance lifecycle management is decoupled from load balancer health probes in Azure. In AWS, an Auto Scaling Group (ASG) automatically terminates and replaces an EC2 instance if the Application Load Balancer health check reports unhealthy status. In Microsoft Azure, an Azure Load Balancer health probe merely withdraws an unhealthy VM from traffic distribution; it never initiates automatic VM destruction. Architects must explicitly configure the Application Health Extension directly on the Virtual Machine Scale Set (VMSS) to trigger automatic node replacement.
</details>

<details>
<summary>Question 4: When you evaluate cloud provider tradeoffs for specific workload patterns using the service mapping framework, which hyperscaler model offers automatic cost reductions for sustained execution without upfront financial commitments?</summary>
When engineers evaluate cloud provider tradeoffs for specific workload patterns using the service mapping framework, Google Cloud Platform stands out by providing automatic Sustained Use Discounts (SUDs). Workloads that execute continuously for more than twenty-five percent of a billing month automatically receive tiered pricing reductions of up to thirty percent on Compute Engine instances. On AWS and Microsoft Azure, securing comparable discounts requires teams to evaluate tradeoffs and commit in advance to one-year or three-year Reserved Instances or Savings Plans.
</details>

<details>
<summary>Question 5: In AWS, you assign permissions to an EC2 instance by attaching an IAM Role via an Instance Profile. How is the exact equivalent outcome achieved securely in GCP for a Compute Engine instance?</summary>
You attach a Service Account directly to the Compute Engine instance during creation or update. The virtual machine then authenticates to GCP APIs using the short-lived credentials of that specific Service Account retrieved from the local instance metadata server. This mechanism acts as the trusted machine identity of the compute resource without storing static keys on disk.
</details>

<details>
<summary>Question 6: An enterprise running Kubernetes clusters on version 1.35 demands that worker node infrastructure and operating system updates be managed entirely by the cloud provider while paying strictly for pod resource allocations. Which hyperscaler service mode satisfies this requirement?</summary>
GKE Autopilot satisfies this requirement directly. In GKE Autopilot, Google provisions, secures, and automatically scales the underlying worker node infrastructure based entirely on pod resource requests. Teams interact with the standard Kubernetes API without managing virtual machine node pools, operating system patches, or node scaling mechanics, paying strictly for the CPU, memory, and storage reserved by running pods.
</details>

<details>
<summary>Question 7: A developer hardcodes static cloud access credentials into an application to read object storage blobs. What native identity feature in Microsoft Azure eliminates static credentials for an application running on an Azure Virtual Machine?</summary>
System-Assigned Managed Identities in Microsoft Azure eliminate static credentials. By enabling a managed identity on the virtual machine, Azure automatically registers a service principal in Microsoft Entra ID and injects temporary OAuth tokens through the local metadata endpoint. Role-Based Access Control (RBAC) role assignments can then grant the managed identity granular permissions directly on the target storage account.
</details>

<details>
<summary>Question 8: An application deployed on AWS utilizes an Application Load Balancer (ALB) to distribute HTTP traffic across multiple regional instances. What GCP service allows an identical HTTP workload to terminate traffic globally on a single Anycast IP address across multiple regions?</summary>
GCP Global External HTTP(S) Load Balancer provides this capability. Unlike an AWS ALB, which is bound to a single region and relies on regional DNS resolution, Google Cloud global load balancing infrastructure terminates client TCP and SSL connections at hundreds of worldwide edge points of presence on a single Anycast IP address, routing traffic across Google private network directly to the nearest healthy backend region.
</details>

---

## Hands-On Exercise

Scenario: You are a Lead Cloud Architect consulting for an enterprise media organization that is expanding its primary video streaming delivery platform from AWS into both Google Cloud Platform and Microsoft Azure. The engineering leadership mandates multi-cloud resiliency to ensure uninterrupted operations during major global streaming broadcasts. Your core objective is to translate this monolithic architecture into functional equivalents across GCP and Azure while documenting the essential structural compromises and networking realities of each cloud provider.

The baseline deployment for the target organization is currently hosted within AWS and comprises the following structural components:
*   **Network**: A single VPC in `us-east-1` with public and private subnets distributed across two Availability Zones for high availability.
*   **Compute**: A fleet of EC2 instances running a monolithic video processing application, managed entirely by an Auto Scaling Group (ASG).
*   **Traffic Management**: An Application Load Balancer (ALB) routing HTTP/HTTPS traffic from the public internet down to the ASG instances.
*   **Storage**: An S3 bucket storing user-uploaded raw media files and processed thumbnails.
*   **Database**: Amazon RDS for PostgreSQL handling user metadata and transaction history.
*   **Observability**: CloudWatch utilized for custom application metrics and centralized log aggregation.

Review the practical tasks detailed below and complete the architectural translations across each cloud provider to validate migration feasibility:

- [ ] **Task 1: Architect the Google Cloud Platform (GCP) Translation**
    Map the AWS services to their GCP counterparts. Pay special attention to how the VPC structure will differ and how the compute instances are grouped.

<details>
<summary>Solution for Task 1</summary>

*   **Network**: A single Global VPC. Instead of tying subnets strictly to Availability Zones, you create a regional subnet in `us-east4`. The VPC spans the entire globe, but the IP space of the subnet is constrained to that region.
*   **Compute**: Google Compute Engine (GCE) instances deployed and managed by a Regional Managed Instance Group (MIG).
*   **Traffic Management**: Cloud Load Balancing (specifically, an External Global HTTP(S) Load Balancer). A major difference here is that the GCP Load Balancer provides a single global Anycast IP address by default, unlike the regional DNS name provided by an AWS ALB.
*   **Storage**: Cloud Storage (GCS) bucket for the media files.
*   **Database**: Cloud SQL for PostgreSQL for the metadata.
*   **Observability**: Cloud Operations (formerly Stackdriver) for comprehensive logging and metrics.
</details>

- [ ] **Task 2: Architect the Microsoft Azure Translation**
    Map the exact same baseline AWS services to their native Microsoft Azure counterparts, focusing on the terminology used for grouping and load balancing.

<details>
<summary>Solution for Task 2</summary>

*   **Network**: An Azure Virtual Network (VNet) deployed in a specific region, such as `East US`. Subnets are subsequently created within the boundaries of that VNet.
*   **Compute**: Azure Virtual Machines continuously managed and scaled by Virtual Machine Scale Sets (VMSS).
*   **Traffic Management**: Azure Application Gateway. This provides regional layer 7 HTTP/HTTPS routing, which is the closest direct equivalent to the AWS ALB. If global routing was required, Azure Front Door would be the alternative.
*   **Storage**: Azure Blob Storage provisioned within an Azure Storage Account.
*   **Database**: Azure Database for PostgreSQL.
*   **Observability**: Azure Monitor to collect platform telemetry, and Application Insights configured for deep application-level tracing.
</details>

- [ ] **Task 3: Implement Identity Security Translation**
    The legacy AWS EC2 instances currently utilize an IAM Instance Profile to securely authenticate and read from the S3 bucket without relying on any hardcoded credentials. Describe the exact mechanism to achieve this identical security posture in both GCP and Azure.

<details>
<summary>Solution for Task 3</summary>

*   **GCP Translation**: You must create a dedicated Service Account. You then grant this Service Account the explicit `roles/storage.objectViewer` role bound to the specific GCS bucket. Finally, you attach that Service Account directly to the Compute Engine instances via the Instance Template used by the MIG.
*   **Azure Translation**: You navigate to the Virtual Machine Scale Set and enable a "System-Assigned Managed Identity". Once enabled, you use Azure RBAC to grant this specific identity the `Storage Blob Data Reader` role, strictly scoping the permission to the specific Blob Storage container where the media files reside.
</details>

- [ ] **Task 4: Execute the Managed Kubernetes Translation**
    The engineering director decides to modernize the stack and migrate the entire monolithic application to managed Kubernetes (requiring version 1.35+). They demand the use of each hyperscaler's native service. List the specific service names and identify the default native Container Network Interface (CNI) plugin each platform utilizes.

<details>
<summary>Solution for Task 4</summary>

*   **AWS Platform**: Amazon EKS (Elastic Kubernetes Service). Default CNI: Amazon VPC CNI (which assigns actual VPC IPs to individual pods).
*   **GCP Platform**: Google GKE (Google Kubernetes Engine). Default CNI: GKE Dataplane V2 (an advanced eBPF-based networking plane powered by Cilium) or natively integrated VPC routing using alias IPs.
*   **Azure Platform**: Azure AKS (Azure Kubernetes Service). Default CNI: Azure CNI (which assigns VNet IPs to pods) or Azure CNI Overlay (which uses an internal network to conserve VNet IP space).
</details>

- [ ] **Task 5: Serverless Event Translation**
    A new microservice needs to execute a lightweight data transformation script every time a new image is uploaded to object storage. Map this event-driven, serverless execution flow across all three providers.

<details>
<summary>Solution for Task 5</summary>

*   **AWS**: An S3 bucket event triggers an AWS Lambda function.
*   **GCP**: A Cloud Storage event (via Eventarc) triggers a Google Cloud Function.
*   **Azure**: An Azure Event Grid notification from Blob Storage triggers an Azure Function (using an Azure Blob Storage trigger binding).
</details>

- [ ] **Task 6: Cost Comparison Exercise**
    The media company expects to run 10 instances of a 4-vCPU, 16-GB machine 24/7 for the video processing fleet. Calculate the approximate monthly on-demand cost on all three providers. Then determine how much they would save with a 1-year commitment on each.

<details>
<summary>Solution for Task 6</summary>

**On-demand monthly cost (approximate, US region, Linux):**

*   **AWS** (m5.xlarge): ~$0.192/hr x 730 hrs x 10 = ~$1,402/month
*   **GCP** (n2-standard-4): ~$0.194/hr x 730 hrs x 10 = ~$1,416/month (but with Sustained Use Discounts automatically applied for full-month usage, effective rate drops to ~$0.136/hr = ~$993/month)
*   **Azure** (Standard_D4s_v5): ~$0.192/hr x 730 hrs x 10 = ~$1,402/month

**With 1-year commitment (approximate):**

*   **AWS** (1-yr Reserved, all upfront): ~35% savings = ~$911/month
*   **GCP** (1-yr CUD): ~28% savings = ~$715/month (combined with SUDs already applied)
*   **Azure** (1-yr Reserved): ~35% savings = ~$911/month

Key insight: GCP's Sustained Use Discounts make it the cheapest for steady-state workloads even without commitments. AWS and Azure require purchasing reservations to compete on price.
</details>

---

## Sources

- [VPC CIDR Blocks](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-cidr-blocks.html) — AWS VPC documentation explicitly defines the allowed IPv4 CIDR range and secondary CIDR association behavior.
- [Configure Subnets](https://docs.aws.amazon.com/vpc/latest/userguide/configure-subnets.html) — AWS documents subnet scope as AZ-local and non-spanning across availability zones.
- [Subnet Sizing](https://docs.aws.amazon.com/vpc/latest/userguide/subnet-sizing.html) — AWS subnet sizing documentation lists reserved addresses and explains base-plus-two DNS reservation.
- [IAM Policy Versioning](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_managed-versioning.html) — AWS managed-policy versioning documentation explicitly states the five-version limit and rollback behavior.
- [AWS PrivateLink](https://docs.aws.amazon.com/vpc/latest/privatelink/privatelink-access-aws-services.html) — AWS PrivateLink documentation describes reaching AWS services privately through interface endpoints without an internet or NAT path.
- [IAM Overview](https://cloud.google.com/iam/docs/overview) — Google Cloud documentation covering permissions, roles, principals, and allow policy inheritance on the resource hierarchy.
- [Create and Manage Service Accounts](https://cloud.google.com/iam/docs/service-accounts-create) — Google Cloud guidance on user-managed versus default service accounts and key security best practices.
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation) — Google Cloud authentication for external OIDC and SAML workloads without service account keys.
- [VPC Networks](https://docs.cloud.google.com/vpc/docs/vpc) — Google Cloud primary reference for global VPC behavior, subnet scope, secondary ranges, and custom mode networking.
- [Cloud Load Balancing Overview](https://cloud.google.com/load-balancing/docs/load-balancing-overview) — Google Cloud documentation on global Anycast architecture, backend services, health checking, and traffic distribution.
- [What is Azure Container Registry?](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-intro) — Microsoft documentation for managed private container registries in Azure.
- [Azure Container Instances Overview](https://learn.microsoft.com/en-us/azure/container-instances/container-instances-overview) — Microsoft documentation detailing the serverless container primitive and per-second billing model.
- [Azure Functions Hosting Options](https://learn.microsoft.com/en-us/azure/azure-functions/functions-scale) — Microsoft reference for Consumption, Flex Consumption, Premium, and Dedicated hosting plans.
- [Azure Key Vault Developers Guide](https://learn.microsoft.com/en-us/azure/key-vault/general/developers-guide) — Microsoft Key Vault documentation detailing secure storage for cryptographic keys, secrets, and certificates.

---

## Next Module

Ready to dive deep into Amazon's ecosystem and master the specific tools of the most widely used cloud provider? Continue to the [AWS DevOps Essentials](/cloud/aws-essentials/).
