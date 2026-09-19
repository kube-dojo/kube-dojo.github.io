---
title: "Module 1.1: AWS Identity & Access Management (IAM) Deep Dive"
slug: cloud/aws-essentials/module-1.1-iam
sidebar:
  order: 2
---
**Complexity**: `[MEDIUM]` | **Time to Complete**: 2h | **Prerequisites**: Cloud Native 101. After completing this module, you will be able to perform all of the outcomes listed below and defend those choices during an incident review:

## What You'll Be Able to Do

- **Configure least-privilege IAM policies using conditions, permission boundaries, and service control policies**
- **Design cross-account access patterns using IAM roles and trust policies for multi-account AWS environments**
- **Diagnose policy evaluation failures by tracing the Allow/Deny logic across identity, resource, and SCP policies**
- **Eliminate long-lived access keys across infrastructure by adopting temporary credentials through AWS STS roles**

---

## Why This Module Matters

**Hypothetical scenario:** A misconfigured web application firewall allows a server-side request forgery (SSRF) attack. The SSRF lets an attacker query the AWS EC2 instance metadata service and retrieve the credentials of an over-permissive IAM role attached to the instance. Because that role grants broad S3 read access, the attacker exfiltrates customer data from multiple sensitive buckets. The breach illustrates how identity misconfiguration—not exotic malware—can turn a single application flaw into large-scale data loss.

This incident underscores a fundamental truth about cloud security: **identity is the new perimeter**. In a traditional on-premises data center, security often meant building a strong network perimeter with firewalls and intrusion detection systems. Once inside the network, lateral movement was relatively easy. In AWS, the network perimeter still matters, but it is secondary to the identity perimeter. In AWS, most authenticated control-plane requests and many service-to-service actions are evaluated through IAM policies and related authorization mechanisms.

If you get IAM wrong, nothing else matters. You can build the most secure Virtual Private Cloud (VPC) with locked-down security groups and private subnets, but if an attacker compromises an IAM key with administrative privileges, they can bypass all of those network controls with a single API call. In this module, you will learn the mechanics of AWS IAM, moving beyond basic users and groups to understand the power of roles, the nuance of policy evaluation, and the critical importance of least privilege. You will learn how to design access control for complex, multi-account environments, ensuring that both human operators and machine identities have exactly the permissions they need---and absolutely nothing more.

---

## The Architecture of IAM: Principals and Policies

At its core, IAM is about answering a single question: *Who* can do *what* to *which resources* under *what conditions*? In practice, every secure AWS platform is built on this access-control contract, and you can think of IAM as the policy compiler that evaluates that contract hundreds of millions of times a day. To answer this, AWS uses two primary concepts: **Principals** (the "who") and **Policies** (the rules defining the "what," "which," and "what conditions"), and treating them as separate mental objects prevents common design mistakes later when requests cross account boundaries or service boundaries.

### Principals: Users, Groups, and Roles

A principal is an entity that can make a request for an action or operation on an AWS resource. Understanding the differences between the three principal types is essential because they are not interchangeable and the wrong choice can create serious security and operational problems.

1.  **IAM Users**: Think of a user as a specific person or an application that needs long-term credentials. Users have a name, a password (for console access), and access keys (for programmatic access via CLI/SDK). However, [creating long-term IAM users for human operators is increasingly considered an anti-pattern. Access keys leak. Passwords get reused. AWS itself now recommends IAM Identity Center for all human access.](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
2.  **IAM Groups**: A collection of IAM users. Groups simplify administration. Instead of attaching a policy to ten individual developers, you attach the policy to the "Developers" group and add the users to the group. Note: [A group is *not* a principal; it cannot make requests itself. It is purely an administrative grouping. You cannot reference a group in a `Principal` block of a resource policy.](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_principal.html)
3.  **IAM Roles**: This is the most powerful and important concept in IAM. A role is similar to a user, in that it is an identity with permission policies that determine what the identity can and cannot do. However, instead of being uniquely associated with one person, a role is intended to be assumable by anyone (or any service) that needs it. [Roles do *not* have standard long-term credentials (passwords or access keys). Instead, when you assume a role, AWS provides you with temporary security credentials for your role session.](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles.html)

#### Comparison: IAM Users vs Roles vs Service-Linked Roles

| Feature | IAM User | IAM Role | Service-Linked Role |
| :--- | :--- | :--- | :--- |
| **Credentials** | Long-term (password, access keys) | [Temporary (STS tokens, 1-12 hrs)](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html) | Temporary (managed by AWS) |
| **Who uses it** | Humans, legacy apps | EC2, Lambda, cross-account, federation | AWS services (e.g., ELB, RDS) |
| **Created by** | You (admin) | You (admin) | AWS (automatically or on demand) |
| **Trust policy** | N/A | You define who can assume it | Predefined by AWS, immutable |
| **Can be assumed** | No | Yes, via `sts:AssumeRole` | Only by the linked AWS service |
| **Recommended for humans** | No (use Identity Center) | Yes (via federation) | N/A |
| **Rotation required** | Yes (keys, passwords) | No (auto-rotated by STS) | No (managed by AWS) |
| **Max session duration** | Indefinite | 1-12 hours (configurable) | Service-dependent |

**Service-Linked Roles** deserve special attention. These are roles that AWS services create in your account to perform actions on your behalf. For example, when you create an Application Load Balancer, [AWS automatically creates a service-linked role (`AWSServiceRoleForElasticLoadBalancing`) that lets the ELB service manage ENIs and security groups in your VPC. You cannot modify their permissions policy or trust policy---both are predefined and controlled by AWS.](https://docs.aws.amazon.com/elasticloadbalancing/latest/userguide/elb-service-linked-roles.html) To list them:

```bash
# List all service-linked roles in your account
aws iam list-roles --query 'Roles[?starts_with(Path, `/aws-service-role/`)].[RoleName,Arn]' --output table

# Inspect a specific service-linked role
aws iam get-role --role-name AWSServiceRoleForElasticLoadBalancing
```

> **Pause and predict:** If an IAM user has `AdministratorAccess`, can they directly perform actions as a service-linked role? Consider why AWS deliberately restricts this delegation pattern across service boundaries.

<details>
<summary>Check your prediction</summary>

No. Service-linked roles are intended strictly for AWS services like Elastic Load Balancing, not human or machine administrators. Even with `AdministratorAccess`, you cannot assume or run commands directly as a service-linked role because their trust policy trusts only the linked AWS service principal. This restriction prevents administrators from circumventing IAM governance by delegating privileged operations through immutable, service-owned identities.

</details>

### The Mechanism of Assuming a Role (STS)

The AWS Security Token Service (STS) is the engine behind IAM roles. When an entity (like an EC2 instance or a federated user) needs to assume a role, it makes a call to STS (specifically, `sts:AssumeRole`). This call is the turning point where identity changes: before the call the caller is one principal, and after the call the caller inherits permissions from the role identity and session context. Here is what happens under the hood:

```mermaid
sequenceDiagram
    participant Requester as Requester<br/>(EC2, User, Lambda)
    participant STS as STS Service
    participant Target as Target AWS Service<br/>(S3, EC2)

    Requester->>STS: 1. AssumeRole(RoleARN)
    Note over STS: 2. Check Trust Policy<br/>Is requester allowed?
    STS-->>Requester: 3. Return Temporary Credentials<br/>(AccessKeyId + SecretKey + Token)<br/>Valid for 1-12 hours
    Requester->>Target: 4. Make API calls using temporary credentials
    Note over Target: 5. IAM evaluates the ROLE'S<br/>Permissions Policy<br/>(not the requester's original perms)
```

Step by step, the STS flow follows a predictable sequence that you can use as a troubleshooting checklist:

1.  The requester calls `AssumeRole`, specifying the Amazon Resource Name (ARN) of the role it wants to assume.
2.  [STS checks the target role's **Trust Policy** (also known as the assume role policy). This policy defines *who* is allowed to assume the role.](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_update-role-trust-policy.html) If the requester is not listed in the trust policy, the request is denied.
3.  If the trust policy allows it, STS generates temporary, short-lived credentials (an Access Key ID, a Secret Access Key, and a Session Token).
4.  The requester uses these temporary credentials to make subsequent AWS API calls. These calls are evaluated against the **Permissions Policy** attached to the role, not the requester's original permissions.

```json
// Example Trust Policy: Only EC2 instances can assume this role
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

There are several variants of `AssumeRole` for different federation scenarios. You will choose one of these based on which identity source is driving trust between the application or user and the role:

| STS API Call | Use Case | Credential Source |
| :--- | :--- | :--- |
| `AssumeRole` | Cross-account access, role chaining | Existing AWS credentials |
| `AssumeRoleWithSAML` | SAML 2.0 federation (Okta, Azure AD) | SAML assertion from IdP |
| `AssumeRoleWithWebIdentity` | Web identity federation (Cognito, OIDC) | Token from web IdP |
| `GetSessionToken` | MFA-protected API access | Existing IAM user creds + MFA token |
| `GetFederationToken` | Custom identity broker | Existing IAM user creds |

Let us see this in action from the CLI. Run through these commands end-to-end so you can see where each credential field appears in the response and confirm role context changes before running privileged API calls:

```bash
# Check who you are right now
aws sts get-caller-identity

# Assume a role and capture temporary credentials
CREDS=$(aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/MyRole \
  --role-session-name my-session \
  --duration-seconds 3600 \
  --query 'Credentials')

# Parse and export the temporary credentials
export AWS_ACCESS_KEY_ID=$(echo $CREDS | jq -r '.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo $CREDS | jq -r '.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo $CREDS | jq -r '.SessionToken')

# Verify you are now operating as the assumed role
aws sts get-caller-identity
# Output will show the role ARN and session name

# When done, unset to revert to your original identity
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
```

---

## IAM Policies: The Anatomy of Authorization

Policies are JSON documents that define permissions. When a principal makes a request to AWS, the IAM evaluation engine looks at all applicable policies to determine if the request should be allowed or denied.

### Managed vs. Inline Policies

*   **AWS Managed Policies**: Created and maintained by AWS (e.g., `AdministratorAccess`, `AmazonS3ReadOnlyAccess`). They are convenient but often violate the principle of least privilege because they are designed to cover broad use cases. AWS updates them when new services or actions are released.
*   **Customer Managed Policies**: Standalone policies created and managed by you in your AWS account. You can attach these to multiple users, groups, or roles. This is the recommended approach for reusability and version control. [You can have up to 5 versions of a customer managed policy, allowing you to roll back if a change causes issues.](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_managed-versioning.html)
*   **Inline Policies**: Policies that are embedded directly into a single user, group, or role. They maintain a strict 1-to-1 relationship. Use these only when you want to ensure the policy cannot be accidentally attached to another entity.

```bash
# List all AWS managed policies (there are hundreds)
aws iam list-policies --scope AWS --query 'Policies[].PolicyName' --output table

# List your custom managed policies
aws iam list-policies --scope Local --output table

# View the actual JSON of a managed policy (need version ID)
aws iam get-policy-version \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess \
  --version-id v1

# List inline policies on a role
aws iam list-role-policies --role-name MyRole

# Get the JSON of an inline policy
aws iam get-role-policy --role-name MyRole --policy-name MyInlinePolicy
```

### The Policy Document Structure

Every IAM policy statement requires a few key elements: `Effect`, `Action`, and `Resource`. Together these fields decide whether an operation is allowed, denied, or implicitly denied; they also determine whether your policy is easy to audit when the team grows and permissions overlap.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowS3ReadAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-company-data-bucket",
        "arn:aws:s3:::my-company-data-bucket/*"
      ],
      "Condition": {
        "IpAddress": {
          "aws:SourceIp": "192.0.2.0/24"
        }
      }
    }
  ]
}
```

*   **Version**: [Always use `"2012-10-17"`. This is the current policy language version. The older `"2008-10-17"` version lacks support for policy variables like `${aws:username}` and some condition operators.](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_version.html) There is no reason to use it.
*   **Sid** (Statement ID, optional): A human-readable label for the statement. Useful for debugging when a policy has many statements.
*   **Effect**: Either `Allow` or `Deny`. (Default is Deny).
*   **Action**: The specific API calls being permitted or restricted (e.g., `ec2:StartInstances`, `dynamodb:PutItem`). Wildcards are supported: `s3:Get*` matches all S3 Get actions.
*   **Resource**: The specific AWS entities the action applies to, defined by their ARN. Using `*` (wildcard) here is dangerous---it means "every resource of this type in the account."
*   **Condition** (Optional): Rules determining when the policy is in effect (e.g., only if the request comes from a specific IP, or only if MFA is present).

#### Understanding ARN Format

ARNs (Amazon Resource Names) are how AWS uniquely identifies every resource. Understanding them is critical for writing scoped policies:

```text
arn:partition:service:region:account-id:resource-type/resource-id
```

For an analysis of how identity failures cascade in distributed systems, see [Failure Modes and Effects](../../../platform/foundations/reliability-engineering/module-2.2-failure-modes-and-effects/).

```text
Examples:
arn:aws:s3:::my-bucket                        # S3 bucket (no region/account - global)
arn:aws:s3:::my-bucket/*                     # All objects IN the bucket
arn:aws:ec2:us-east-1:123456789012:instance/i-abc123   # Specific EC2 instance
arn:aws:iam::123456789012:user/alice          # IAM user (no region - global)
arn:aws:lambda:eu-west-1:123456789012:function:my-func  # Lambda function
```

A common mistake: [for S3, you need *two* resource entries---one for the bucket itself (for `ListBucket`) and one for objects within it (for `GetObject`, `PutObject`).](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_examples_s3_rw-bucket.html) The bucket ARN and the object ARN are different resources.

#### Powerful Condition Keys

Conditions are where IAM policies become truly powerful. Here are the most useful condition keys:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RequireMFAForDelete",
      "Effect": "Deny",
      "Action": ["s3:DeleteObject", "s3:DeleteBucket"],
      "Resource": "*",
      "Condition": {
        "BoolIfExists": {
          "aws:MultiFactorAuthPresent": "false"
        }
      }
    },
    {
      "Sid": "RestrictToOrgOnly",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::shared-data/*",
      "Condition": {
        "StringEquals": {
          "aws:PrincipalOrgID": "o-abc123def4"
        }
      }
    },
    {
      "Sid": "EnforceEncryptedTransport",
      "Effect": "Deny",
      "Action": "s3:*",
      "Resource": "arn:aws:s3:::secure-bucket/*",
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    },
    {
      "Sid": "RestrictByTag",
      "Effect": "Allow",
      "Action": "ec2:StopInstances",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "ec2:ResourceTag/Environment": "development"
        }
      }
    }
  ]
}
```

Key condition operators to know when you are reducing risk without blocking legitimate workflows:

| Operator | Use Case |
| :--- | :--- |
| `StringEquals` | Exact string match (case-sensitive) |
| `StringLike` | Wildcard matching (`*`, `?`) |
| `ArnLike` / `ArnEquals` | Match ARN patterns |
| `IpAddress` / `NotIpAddress` | Restrict by source IP range |
| `DateGreaterThan` / `DateLessThan` | Time-based access windows |
| `Bool` | Boolean conditions (`aws:SecureTransport`, `aws:MultiFactorAuthPresent`) |
| `NumericLessThan` | Numeric comparisons (e.g., max session duration) |

> **Pause and predict:** If an IAM principal possesses an identity-based policy granting `s3:GetObject` on `BucketA`, but `BucketA` contains no resource-based bucket policy at all, will the request succeed in the same account? Predict what changes in the evaluation outcome if `BucketA` resides in an entirely different AWS account.

<details>
<summary>Check your prediction</summary>

In the same account, the request succeeds because an explicit allow in either the identity-based policy or the resource-based policy satisfies evaluation when no explicit deny exists. In a cross-account scenario, the request fails with Access Denied because cross-account evaluation requires an explicit allow in both accounts: the caller identity policy must allow the action and the destination bucket policy must explicitly grant access to the external principal.

</details>

### The Policy Evaluation Logic

The IAM evaluation logic is strict and follows a well-defined order for every single API request, and understanding this flow is *essential* for debugging access issues. The evaluator first applies hard guardrails like explicit denies and then evaluates allowed actions, which is why permission failures often look random unless you trace the full chain. In day-to-day operations, using this order as a diagnostic checklist makes incidents easier to reproduce: start at the top, and rule out each gate in sequence before assuming policy data is wrong.

```mermaid
flowchart TD
    Start([API Request arrives]) --> Q1

    Q1{"Explicit DENY<br/>in ANY policy?"}
    Q1 -- "YES" --> Denied1(["DENIED<br/>(final, cannot be overridden)"])
    Q1 -- "NO" --> Q2

    Q2{"SCP allows it?<br/>(if applicable)"}
    Q2 -- "YES (or N/A)" --> Q3

    Q3{"Resource-based<br/>policy allows?"}
    Q3 -- "YES" --> Allowed1(["ALLOWED<br/>(if same-acct & resource pol<br/>has explicit Allow)"])
    Q3 -- "NO" --> Q4

    Q4{"Identity-based<br/>policy allows?"}
    Q4 -- "NO" --> Denied2(["DENIED (implicit)"])
    Q4 -- "YES" --> Q5

    Q5{"Permission<br/>Boundary allows?"}
    Q5 -- "NO" --> Denied3(["DENIED (implicit)"])
    Q5 -- "YES" --> Q6

    Q6{"Session policy<br/>allows?<br/>(if applicable)"}
    Q6 -- "NO" --> Denied4(["DENIED (implicit)"])
    Q6 -- "YES" --> Allowed2(["ALLOWED"])

    style Denied1 fill:#f8d7da,stroke:#dc3545,color:#721c24
    style Denied2 fill:#f8d7da,stroke:#dc3545,color:#721c24
    style Denied3 fill:#f8d7da,stroke:#dc3545,color:#721c24
    style Denied4 fill:#f8d7da,stroke:#dc3545,color:#721c24
    style Allowed1 fill:#d4edda,stroke:#28a745,color:#155724
    style Allowed2 fill:#d4edda,stroke:#28a745,color:#155724
```

The four key rules, checked in this exact order, are worth memorizing for every access issue you debug:

A few practical consequences follow from this design. First, the default is denial, so if no path is explicitly opened, the action cannot proceed. Second, if *any* matching policy entry says `Deny`, the request is immediately rejected and cannot be overridden. Third, an `Allow` only succeeds when every required policy layer allows it; it is never a free pass. Finally, if the engine cannot find a matching explicit allow at the end of all checks, it falls back to deny, which is why missing conditions and forgotten permissions often present as the same AccessDenied message.

A permissions problem that looks local to a role or bucket can actually be caused by an organization-level guardrail such as an SCP, so IAM troubleshooting must include higher-level policy controls.

#### Cross-Account Evaluation: A Different Beast

When the requester and the resource are in *different* AWS accounts, the evaluation logic changes because permission is no longer judged only from one side, so both account contexts must agree. In a cross-account request, both sides must grant access:

- The **identity-based policy** in the requester's account must allow the action.
- The **resource-based policy** on the target resource must also allow the requester's principal.

Think of it like visiting another country: [you need both an exit visa (your account's permission) and an entry visa (the resource owner's permission). If either side says no, access is denied.](https://docs.aws.amazon.com/IAM/latest/UserGuide/intro-structure.html) The most practical debugging tip is to trace identity and resource policies separately before changing anything else, because the failure often comes from the side you are not currently inspecting.

#### Same-Account UNION vs Cross-Account INTERSECTION

The contrast between same-account and cross-account evaluation is one of the most commonly misunderstood IAM mechanics. Getting it wrong leads to false confidence ("the role policy allows it, so it should work") or unnecessary policy sprawl ("we added a bucket policy but nothing changed"). [When an IAM entity in Account A requests access to a resource also in Account A, AWS evaluates identity-based policies and resource-based policies together. The resulting permissions are the **union** of both: if either policy type grants an explicit Allow and neither applies an explicit Deny, the action is permitted.](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html) You do not need a resource-based policy when the identity-based policy alone is sufficient. Quiz Question 1 reflects this: an S3 bucket policy is only required to *not* deny in the same-account case, not to affirmatively allow.

Cross-account access inverts that mental model. [Both the identity-based policy in the requester's account and the resource-based policy on the target resource must grant permission. This is an intersection, not a union.](https://docs.aws.amazon.com/IAM/latest/UserGuide/intro-structure.html) Missing either side produces AccessDenied even when the other side looks perfectly configured. When debugging, ask two questions in parallel. First: does the caller's identity policy permit this action on this resource ARN? Second: does the resource owner's policy permit this principal? Only when both answers are yes---and no explicit Deny or SCP blocks the path---will the request succeed.

This union/intersection split also explains why permission boundaries and SCPs behave differently from resource policies. [Boundaries intersect with identity-based policies. They cap what an identity can ever receive, regardless of how permissive the attached policies appear.](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html) SCPs similarly intersect at the organization level. Resource policies in the same account expand the permission surface through union. Keep four evaluation modes straight: union for same-account identity plus resource, intersection for cross-account, intersection for boundaries, and intersection for SCPs. That framework is the foundation of every access-debugging workflow you will run in production.

#### The `NotAction`, `NotResource`, and `NotPrincipal` Foot-Guns

Advanced policy elements that negate a list (`NotAction`, `NotResource`, `NotPrincipal`) can produce dramatically shorter JSON. They also invert the reader's intuition and are a leading cause of accidental over-provisioning. [`NotAction` with `"Effect": "Allow"` matches every action *except* those listed. All unlisted actions on applicable resources are allowed, which is often far broader than authors expect.](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_notaction.html) A statement like `"Effect": "Allow", "NotAction": "iam:*", "Resource": "*"` grants access to every non-IAM action in every service across the entire account. It does not mean "everything except IAM admin."

[`NotResource` with `"Effect": "Allow"` is equally dangerous when paired with broad actions. AWS explicitly warns never to combine `"Effect": "Allow"`, `"Action": "*"`, and `"NotResource"` pointing at a single bucket.](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_notresource.html) That pattern allows all actions on all resources except the one bucket. It even permits IAM policy changes that could grant access to the excluded bucket anyway. The safer pattern for exclusion is `"Effect": "Deny"` with `NotResource`. That denies everything *except* the listed resources, but you still need separate Allow statements for what you actually want to permit.

`NotPrincipal` appears primarily in resource-based policies and follows the same inversion logic: an Allow with `NotPrincipal` grants access to every principal *except* those named. Teams reach for these elements when policy JSON grows unwieldy, but the maintenance cost shifts from "add a new ARN to the Allow list" to "hope nobody creates a new resource type we forgot to exclude." For production guardrails, prefer explicit Allow lists with condition keys (`aws:PrincipalOrgID`, `aws:PrincipalTag`, `aws:SourceArn`) over Not-prefixed wildcards unless you have automated policy testing that simulates every new resource class before deployment.

```bash
# Example: Bucket policy allowing cross-account access
# (applied on the bucket in Account B)
cat << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCrossAccountRead",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::111111111111:role/AppRole"
      },
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::account-b-bucket",
        "arn:aws:s3:::account-b-bucket/*"
      ]
    }
  ]
}
EOF
```

### Using the IAM Policy Simulator

Before deploying policies to production, always test them. The IAM Policy Simulator lets you check whether a given action would be allowed or denied for a principal:

```bash
# Simulate whether a role can perform s3:GetObject
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/MyAppRole \
  --action-names s3:GetObject \
  --resource-arns arn:aws:s3:::my-bucket/data.csv

# Simulate multiple actions at once
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/MyAppRole \
  --action-names s3:GetObject s3:PutObject s3:DeleteObject \
  --resource-arns "arn:aws:s3:::my-bucket/*"

# Simulate a custom policy document (before attaching it)
aws iam simulate-custom-policy \
  --policy-input-list file://my-new-policy.json \
  --action-names ec2:DescribeInstances ec2:TerminateInstances \
  --resource-arns "*"
```

---

## Modern Identity: IAM Identity Center & Permission Boundaries

As organizations scale, managing individual IAM users across dozens of AWS accounts becomes a security nightmare and an administrative bottleneck, so identity architecture has to shift from static people-first accounts toward centralized identity federation. That shift is where IAM Identity Center becomes important, because it changes where users authenticate without changing what AWS accounts ultimately authorize.

### AWS IAM Identity Center (Formerly AWS SSO)

IAM Identity Center is the modern successor to standard IAM users. Instead of creating users directly in AWS, you connect AWS to an external Identity Provider (IdP) like Okta, Azure AD, or Google Workspace. Users log into a portal using their standard corporate credentials, then select AWS accounts and roles that map to their authorization. [The portal presents the AWS accounts and roles they are authorized to access. Console sign-in uses SAML federation (`sts:AssumeRoleWithSAML`) to drop the user into the AWS Management Console without creating a permanent IAM user.](https://docs.aws.amazon.com/singlesignon/latest/userguide/manage-your-identity-source-idp.html) For the AWS CLI, credentials come through the IAM Identity Center SSO-OIDC flow (`aws sso login` → `GetRoleCredentials`), not `AssumeRoleWithSAML`. This pattern removes long-lived human credentials from the infrastructure surface area while still allowing fine-grained role-based assignments.

Why this matters for Kubernetes engineers: if you are running EKS, Identity Center integrates with `aws eks get-token` to provide short-lived credentials for `kubectl` access. No more shared kubeconfigs with embedded long-term tokens, and no more manual key distribution during role transitions.

### Kubernetes Workload Identity on EKS: IRSA vs EKS Pod Identity

Cloud-native platforms run most application logic inside Pods, and those Pods need AWS API access without inheriting the entire EC2 node's IAM role. AWS offers two first-class mechanisms to map a Kubernetes ServiceAccount to an IAM role: **IAM Roles for Service Accounts (IRSA)**, built on OpenID Connect federation, and **EKS Pod Identity**, a newer agent-based association model. Both deliver temporary credentials through the AWS SDK default credential chain, but they differ in trust mechanics, operational ownership, and scaling characteristics---and choosing the wrong one creates either OIDC-provider sprawl or unnecessary migration churn.

**IRSA (OIDC federation)** requires you to create an IAM OIDC identity provider for each EKS cluster, linking the cluster's OIDC issuer URL to IAM. The ServiceAccount receives a projected OIDC token (a `ProjectedServiceAccountToken`), and the AWS SDK calls `sts:AssumeRoleWithWebIdentity` to exchange that JWT for STS credentials. The role's trust policy must reference the OIDC provider ARN and constrain `sub`/`aud` claims so only the intended ServiceAccount can assume the role:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Federated": "arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE"},
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE:sub": "system:serviceaccount:payments:worker",
        "oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE:aud": "sts.amazonaws.com"
      }
    }
  }]
}
```

Each cluster gets its own OIDC provider principal, so a role reused across ten clusters needs ten trust-policy statements (or ten separate roles). IRSA has been the standard pattern since EKS added OIDC support and remains fully supported on all EKS versions that expose an OIDC issuer.

**EKS Pod Identity** (available on supported EKS platform versions) replaces per-cluster OIDC federation with a single service principal. You create an **association** in the EKS API mapping `(cluster, namespace, serviceAccount) → IAM role`, install the **EKS Pod Identity Agent** as a DaemonSet on worker nodes, and configure the role trust policy once with `"Service": "pods.eks.amazonaws.com"`. The agent injects environment variables into Pods using the associated ServiceAccount, and the SDK retrieves credentials without each Pod calling STS directly---reducing STS API load from "once per Pod" to "once per node per credential refresh." [AWS documents that Pod Identity does not use OIDC identity providers, separates IAM configuration from cluster OIDC setup, and reuses a single IAM principal across clusters.](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)

| Dimension | IRSA | EKS Pod Identity |
| :--- | :--- | :--- |
| **Trust mechanism** | OIDC provider per cluster; `AssumeRoleWithWebIdentity` | `pods.eks.amazonaws.com` service principal; EKS-managed association |
| **Setup owner** | Platform team creates OIDC provider + annotates ServiceAccount | Platform team creates EKS association + installs Pod Identity Agent |
| **Multi-cluster reuse** | Separate OIDC principal per cluster in trust policy | Same role trust policy across clusters (associations per cluster) |
| **Credential path** | Pod SDK → STS directly | Pod SDK → node-local agent → STS |
| **Cross-account target role** | Native via trust policy | Target role ARN in the association (same or cross-account) |
| **Fargate / Windows pods** | Supported where IRSA is supported | Not supported (Linux EC2 nodes only) |

Since June 2025, cross-account access is configurable directly in the EKS Pod Identity association by specifying a target role ARN—you no longer need role chaining as the only path for cross-account Pod credentials.

When should you pick which? For **new clusters on supported EKS versions** with Linux EC2 nodes, Pod Identity reduces operational overhead. The win is largest in multi-cluster fleets where duplicating OIDC trust statements is painful. For **Fargate workloads, Windows nodes, existing IRSA investments, or cross-account roles accessed directly from Pods**, IRSA remains the correct or only choice. Migration from IRSA to Pod Identity is a deliberate project. You replace OIDC trust conditions with EKS associations, redeploy the agent, and validate credential propagation latency. Associations are eventually consistent, so allow time before cutting over production traffic.

Hypothetical scenario: a platform team runs twelve EKS clusters. Each cluster's IRSA roles carry near-identical trust policies with different OIDC issuer ARNs. Consolidating to Pod Identity lets them attach one `pods.eks.amazonaws.com` trust and manage associations through the EKS API. They must confirm no Fargate services depend on the old IRSA annotation path before cutover.

Restrict IMDS access on worker nodes regardless of which mechanism you choose. [Both IRSA and Pod Identity documentation warn that unrestricted EC2 Instance Metadata Service access lets containers reach the node's instance profile credentials.](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html) That undermines credential isolation. Set `HttpPutResponseHopLimit: 1` on node instance metadata options. Use `hostNetwork: true` only when you understand the IMDS exposure implications.

```bash
# Configure AWS CLI to use Identity Center (one-time setup)
aws configure sso
# Follow prompts: SSO start URL, SSO Region, account, role

# Log in and get temporary credentials
aws sso login --profile my-sso-profile

# Use the profile for all subsequent commands
aws s3 ls --profile my-sso-profile
aws eks update-kubeconfig --name my-cluster --profile my-sso-profile
```

### Permission Boundaries

How do you allow developers to create their own IAM roles (to attach to their Lambda functions or EC2 instances) without giving them the power to grant themselves Administrator access? Permission Boundaries solve this privilege escalation problem. A permission boundary is an advanced IAM feature where you use a managed policy to set the *maximum* permissions that an identity-based policy can grant to an IAM entity. Think of it like a fence around a playground: users can operate inside the boundary, but they cannot cross into production databases, billing controls, or IAM admin territory. Imagine a developer wants to create a role for a Lambda function. You grant the developer the `iam:CreateRole` permission, but you enforce a Condition: they *must* attach a specific Permission Boundary policy (e.g., `Boundary-Developer-Max-Access`) to any role they create.

[If `Boundary-Developer-Max-Access` allows S3 and DynamoDB, but denies EC2, then even if the developer attaches `AdministratorAccess` to their new Lambda role, the effective permissions will only be S3 and DynamoDB. The boundary restricts the maximum possible ceiling of access.](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html)

> **Pause and predict:** What happens if a developer creates a role with a permission boundary attached, but does not attach any permissions policy to the role? Predict whether the newly created role will possess any operational permissions before an identity policy is assigned.

<details>
<summary>Check your prediction</summary>

No permissions are granted to the role. A permission boundary defines only the maximum ceiling of allowable permissions that identity policies can grant; it does not grant permissions on its own. Because IAM enforces an implicit deny by default, an attached identity-based policy with an explicit Allow is still required for the principal to perform any action.

</details>

```json
// Policy attached to the developer: they can create roles, but MUST
// attach the boundary. Without the boundary condition, they could
// escalate privileges by creating an admin role.
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCreateRoleWithBoundary",
      "Effect": "Allow",
      "Action": "iam:CreateRole",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "iam:PermissionsBoundary": "arn:aws:iam::123456789012:policy/Boundary-Developer-Max-Access"
        }
      }
    },
    {
      "Sid": "DenyRemovingBoundary",
      "Effect": "Deny",
      "Action": [
        "iam:DeleteRolePermissionsBoundary",
        "iam:PutRolePermissionsBoundary"
      ],
      "Resource": "*"
    }
  ]
}
```

```bash
# Create a role with a permission boundary
aws iam create-role \
  --role-name LambdaDataProcessorRole \
  --assume-role-policy-document file://lambda-trust.json \
  --permissions-boundary arn:aws:iam::123456789012:policy/Boundary-Developer-Max-Access

# Check which boundary is attached to a role
aws iam get-role --role-name LambdaDataProcessorRole \
  --query 'Role.PermissionsBoundary'
```

### Session Policies: Further-Restrict-Only at AssumeRole Time

Session policies are a third layer of restriction applied at the moment a role session is created, not when the role is defined. When you call `AssumeRole`, `AssumeRoleWithSAML`, or `AssumeRoleWithWebIdentity`, you can pass an inline JSON policy via the `Policy` parameter or up to ten managed policy ARNs via `PolicyArns`. [The resulting session permissions are the **intersection** of the role's identity-based policies and the session policy---session policies can only **shrink** permissions, never expand them beyond what the role already grants.](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html) If the role allows `s3:*` but your session policy allows only `s3:GetObject` on one prefix, the session can read that prefix and nothing else.

This further-restrict-only property makes session policies ideal for delegation scenarios where you hand temporary credentials to another party but do not trust them with the role's full permission set. A CI pipeline might assume a deployment role with broad EC2 and S3 permissions, but the orchestrator passes a session policy limiting the run to `s3:PutObject` on a single artifact prefix. A security vendor integration might receive credentials scoped to read-only actions even though the underlying audit role could write findings. Session policies also appear in IAM Roles Anywhere profiles (covered below) and in `GetFederationToken` flows for custom identity brokers.

Session policies sit in the evaluation chain alongside permission boundaries and SCPs, but at a different lifecycle point. Boundaries cap the role identity itself. SCPs cap the account. Session policies cap *this specific invocation*. [AWS evaluates session policies after identity-based allows are found, intersecting them with the role's effective permissions.](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_control-access_assumerole.html) An explicit Deny anywhere---including in a session policy---still wins. The plaintext for inline and managed session policies combined cannot exceed 2,048 characters. Complex scoping may require multiple managed session policy ARNs rather than one monolithic inline document. Teams often combine session policies with CloudTrail `roleSessionName` conventions so every delegated credential session is traceable to a human initiator or CI job ID in audit logs.

```bash
# Assume a role but restrict the session to read-only S3 on one prefix
aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/DeployRole \
  --role-session-name ci-pipeline-run-42 \
  --policy '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::artifacts-bucket",
        "arn:aws:s3:::artifacts-bucket/builds/42/*"
      ]
    }]
  }'
```

Hypothetical scenario: an incident-response automation assumes a powerful `IR-SuperRole` but passes a session policy permitting only `ec2:StopInstances` and `ec2:DescribeInstances` on instances tagged `Incident: active`. Even if the role's identity policy grants `ec2:TerminateInstances` and `iam:*`, the session cannot escalate beyond the session policy ceiling---and CloudTrail records the session name for audit correlation.

### Service Control Policies (SCPs): Guardrails for Organizations

If Permission Boundaries are the fences for individual identities, Service Control Policies (SCPs) are the walls around entire AWS accounts. SCPs are a feature of AWS Organizations and define the *maximum available permissions* for all principals in a member account. In other words, SCPs are not a replacement for identity design, they are the highest-level safety net that keeps all accounts inside a guardrail envelope, especially in multi-team or multi-business-unit environments.

[SCPs do not grant any permissions---they only restrict. Even the root user of a member account is bound by the SCP.](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html)

Common SCP patterns typically encode guardrails such as regional restrictions or role protections, then let your IAM teams focus on least-privilege in daily design instead of repeatedly rebuilding global safeguards.

```json
// Deny all actions outside approved regions
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyNonApprovedRegions",
      "Effect": "Deny",
      "Action": "*",
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": ["us-east-1", "eu-west-1"]
        },
        "ArnNotLike": {
          "aws:PrincipalARN": "arn:aws:iam::*:role/OrganizationAdmin"
        }
      }
    }
  ]
}
```

```bash
# List SCPs in your organization
aws organizations list-policies --filter SERVICE_CONTROL_POLICY

# View an SCP's content
aws organizations describe-policy --policy-id p-abc123def4
```

### IAM Roles Anywhere: X.509 Certificates for Hybrid Workloads

Not every workload that needs AWS API access runs inside AWS. On-premises servers, edge devices, and partner-hosted VMs traditionally forced teams toward long-lived IAM user access keys embedded in configuration files---precisely the anti-pattern this module argues against. **IAM Roles Anywhere** closes that gap by letting external workloads authenticate with **X.509 certificates** issued by a certificate authority you register as a **trust anchor**, then receive temporary STS credentials for an IAM role the same way EC2 instance profiles do.

The workflow has three components. A **trust anchor** references either AWS Private CA or an external CA certificate, establishing PKI trust between your non-AWS infrastructure and IAM. A **profile** links one or more IAM roles to optional session policies that further restrict the credentials Roles Anywhere issues. The workload presents its certificate to the Roles Anywhere endpoint, which validates the chain, assumes the configured role, and returns temporary credentials scoped by the profile's session policy. [AWS documents that Roles Anywhere uses the same IAM roles and policies as in-account workloads, avoiding a parallel permission model for hybrid environments.](https://docs.aws.amazon.com/rolesanywhere/latest/userguide/introduction.html)

Trust is scoped at the **account level**. Any certificate from any trust anchor in the account can assume any role trusting the Roles Anywhere service principal. The role trust policy can add conditions such as `aws:SourceArn` matching a specific trust anchor. For multi-account setups, delegate through standard cross-account role assumption. Do not expect organization-wide Roles Anywhere controls out of the box. Roles Anywhere resources are regional. They must reside in the same account and region as the roles they target. Plan certificate renewal and trust-anchor rotation in the same change window to avoid unexpected credential gaps.

Hypothetical scenario: a manufacturing plant runs a telemetry collector on bare-metal servers that must push metrics to Amazon Managed Prometheus. Instead of embedding access keys in the collector's config, the platform team registers the plant's internal CA as a trust anchor, creates a profile with a session policy allowing only `aps:RemoteWrite` on one workspace, and rotates certificates through the existing PKI renewal process---no AWS-side key rotation tickets required.

---

## IAM Best Practices: The Principle of Least Privilege in Action

Least privilege is not a one-time activity. It is a continuous process of granting the minimum permissions needed, monitoring actual usage, and tightening further as roles and services evolve. Teams that treat it as a project task instead of an ongoing loop often start broad, then discover drift in monthly audits; the safer pattern is to build a loop where evidence and controls are collected before each review.

> **Pause and predict:** Why is it dangerous to start with `AdministratorAccess` and plan to remove unused permissions later? Consider what risks emerge even if an engineering team fully intends to complete policy tightening before production.

<details>
<summary>Check your prediction</summary>

Temporary broad access inevitably becomes permanent because delivery pressures and hidden dependencies intervene once services work without friction. In addition, over-permissive bootstrap credentials expose the cloud account to severe blast radius during development and testing, creating brittle architectures where workloads silently rely on privileged APIs that break when policies are eventually locked down.

</details>

### Step 1: Start with Zero and Add

The first habit of reliable IAM design is to start with the minimum base and expand deliberately. Start with zero permissions and add only what breaks because every additional permission becomes part of the blast radius for the next engineer, script, or compromised secret.

### Step 2: Use IAM Access Analyzer

After baseline policies are in place, use actual activity to drive reductions rather than guesswork. [AWS provides tools to help you right-size permissions based on actual CloudTrail activity:](https://docs.aws.amazon.com/IAM/latest/UserGuide/access-analyzer-policy-generation.html) When you can see which actions are actually used and which never occur, you can safely remove stale permissions and avoid overfitting to imagined use cases.

```bash
# Generate a policy based on actual API calls made by a role
# (requires CloudTrail logging enabled)
aws accessanalyzer start-policy-generation \
  --policy-generation-details '{
    "principalArn": "arn:aws:iam::123456789012:role/MyAppRole",
    "cloudTrailDetails": {
      "trailArn": "arn:aws:cloudtrail:us-east-1:123456789012:trail/my-trail",
      "startTime": "2025-01-01T00:00:00Z",
      "endTime": "2025-03-01T00:00:00Z"
    }
  }'

# Find unused access (roles, access keys, permissions)
aws accessanalyzer list-findings \
  --analyzer-arn arn:aws:accessanalyzer:us-east-1:123456789012:analyzer/my-analyzer

# Check when an access key was last used
aws iam get-access-key-last-used --access-key-id AKIAIOSFODNN7EXAMPLE

# List all users and their last activity
aws iam generate-credential-report
aws iam get-credential-report --query 'Content' --output text | base64 -d
```

### Step 3: Tag-Based Access Control (ABAC)

Instead of creating a separate policy for each project, use tags to create dynamic, scalable policies that remain stable as teams and workloads change. This approach lets you encode operational ownership directly in policy conditions, so new projects inherit intent without creating another policy sprawl cycle.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowActionsOnOwnResources",
      "Effect": "Allow",
      "Action": ["ec2:StartInstances", "ec2:StopInstances"],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:ResourceTag/Project": "${aws:PrincipalTag/Project}"
        }
      }
    }
  ]
}
```

[This single policy works for every team. If Alice is tagged with `Project: payments` and Bob with `Project: search`, they can each only manage EC2 instances tagged with their respective project. No policy updates needed when a new project is created.](https://docs.aws.amazon.com/IAM/latest/UserGuide/tutorial_attribute-based-access-control.html)

### Step 4: Continuous Access Review and Credential Hygiene

Least privilege is not a milestone you reach once. It is a loop you run every sprint. New services launch new API actions. Engineers change teams. Vendors rotate. Emergency break-glass grants linger. Each of these events can widen effective permissions without anyone editing a policy document directly. A practical review cadence combines automated signals with human judgment so you tighten access based on evidence rather than calendar guilt.

Start with the **credential report**. Run `aws iam generate-credential-report` monthly and inspect password age, access-key age, and last-used timestamps. Any human IAM user with active access keys should trigger a migration ticket to Identity Center. Any application key older than ninety days without a documented rotation owner is a finding, not an accepted risk. Pair the credential report with **Access Analyzer unused-access findings** in production accounts first. Unused permissions are cheaper to remove than to explain after an audit.

For roles and policies, schedule **quarterly policy simulations** against your highest-risk principals: deployment roles, data-pipeline roles, and break-glass roles. Use `aws iam simulate-principal-policy` with the exact API actions your runbooks require. Remove Allow statements that simulate as unused for ninety days of CloudTrail history. When removing permissions breaks a workflow, fix the workflow---do not restore the broad Allow. Document the required action in the role's runbook so the next reviewer understands why it exists.

Finally, treat **trust policy changes** with the same rigor as permission policy changes. A permissive trust policy on a tightly scoped role still lets the wrong principal assume that role and inherit whatever the role permits. Code-review trust policies in IaC pull requests. Require `sts:ExternalId` for every third-party assumption path. Alert on CloudTrail `AssumeRole` events for break-glass roles within minutes, not days. Hypothetical scenario: a quarterly review discovers a CI role unused for six months but still trusted by an old GitHub OIDC provider from a decommissioned repository. The role permissions are least-privilege; the trust policy is the actual vulnerability. Continuous review catches that mismatch before an attacker does.

---

## Patterns & Anti-Patterns

Mature IAM design is less about memorizing JSON syntax and more about recognizing recurring shapes that scale safely versus shapes that create silent debt. The patterns below appear repeatedly in well-run AWS organizations; the anti-patterns are the failure modes incident reviewers see after credentials leak or auditors flag excessive access.

### Proven Patterns

| Pattern | When to Use | Why It Works | Scaling Note |
| :--- | :--- | :--- | :--- |
| **One role per workload** | Every Lambda, EC2 instance profile, EKS ServiceAccount, or ECS task gets its own IAM role scoped to that application's API surface | Blast radius stays bounded: compromising one workload's credentials does not grant access to unrelated services; CloudTrail session names map cleanly to owners | At hundreds of roles, automate creation via IaC and enforce naming conventions (`app-env-component-role`) |
| **Permission boundaries for delegated role creation** | Developers or application teams may create their own IAM roles (Lambda, ECS) but must not self-grant admin | Boundaries intersect with identity policies, so attaching `AdministratorAccess` to a bounded role still yields only boundary-permitted actions | Publish a small library of approved boundary policies (`Boundary-DataPlane`, `Boundary-ReadOnly`) rather than ad-hoc boundaries per team |
| **ABAC via principal/resource tags** | Many teams, dynamic project namespaces, shared accounts where RBAC policy count would explode | One policy template keyed on `${aws:PrincipalTag/Project}` scales to N projects without N policy documents | Requires tag governance: untagged resources become invisible or overly accessible depending on policy default |
| **Centralized human identity via IAM Identity Center** | Any human accessing AWS console or CLI across multiple accounts | Eliminates long-lived IAM user keys; SAML/OIDC federation provides SSO and automatic credential rotation | Map IdP groups to permission sets once; avoid duplicating user records in each account |
| **Break-glass role with heavy auditing** | Rare emergency operations (full admin) that cannot be pre-approved via normal RBAC | Role exists but trust policy restricts assumption to specific break-glass IdP group + MFA + `aws:SourceIp`; CloudTrail + alerting on every session | Session duration set to minimum (15-60 minutes); automatic ticket creation on assumption |

### Anti-Patterns

| Anti-Pattern | What Goes Wrong | Why Teams Fall Into It | Better Alternative |
| :--- | :--- | :--- | :--- |
| **Long-lived access keys on IAM users** | Keys leak via git, logs, or SSRF to metadata endpoints; no automatic expiry | "It's just a quick script" or legacy CI that predates OIDC | Roles with temporary credentials; Identity Center for humans; OIDC federation for CI |
| **`Resource: "*"` on production Allow statements** | Any resource of that type in the account becomes reachable, including data stores owned by other teams | Wildcards unblock development faster than ARN discovery | Scope to ARNs; use ABAC conditions; simulate before deploy |
| **"Temporary" AdministratorAccess** | Admin permissions never get removed; drift becomes permanent | Deadline pressure during incidents or PoC phases | Time-bound permission sets in Identity Center; break-glass role with alerting |
| **One shared role across many workloads** | Cannot attribute CloudTrail activity; one compromise affects every consumer | Copy-paste from a tutorial or fear of IAM quota limits | One role per workload; use IAM policy reuse via customer managed policies |
| **`Principal: "*"` in trust policy without conditions** | Any AWS principal (or in some cases any caller) can attempt assumption | Vendor docs omit ExternalId; confusion between resource and trust policies | Always pair broad principals with `StringEquals` on `sts:ExternalId`, `aws:PrincipalOrgID`, or specific ARNs |
| **Third-party cross-account trust without ExternalId** | Confused deputy: another customer of the same vendor could trigger assumption of your role | Vendor template uses bare account-root principal | Generate unique ExternalId per vendor; enforce in trust policy Condition block |

---

## Decision Framework

Choosing among IAM primitives is a design decision, not a syntax exercise. The matrix and flowchart below summarize the tradeoffs this module covers; use them during architecture reviews when someone proposes "just create an IAM user" or "let's use AdministratorAccess for now."

### Human Access: IAM User vs IAM Role vs Identity Center

| Criterion | IAM User | IAM Role (direct) | IAM Identity Center |
| :--- | :--- | :--- | :--- |
| **Credential type** | Long-term password + access keys | Temporary STS (requires federation or assumption path) | Temporary STS via SSO portal |
| **Multi-account** | Duplicate user per account | Role per account; manual federation setup | Native multi-account permission sets |
| **Rotation** | Manual key/password rotation | Automatic via STS | Automatic via SSO session |
| **AWS recommendation** | Discouraged for humans | For machines and federation targets | Recommended for all human access |
| **Best fit** | Legacy break-glass only | Service-to-service, EC2/Lambda/EKS workloads | Engineers, operators, auditors |

### ABAC vs RBAC

| Criterion | RBAC (role/group policies) | ABAC (tag-driven conditions) |
| :--- | :--- | :--- |
| **Policy count** | Grows with teams × services | Stable template policies |
| **Governance dependency** | Role catalog maintenance | Tag schema enforcement on principals and resources |
| **Audit clarity** | "Alice has DeveloperRole" is human-readable | "Alice's Project tag matches resource tag" requires tag inspection |
| **Best fit** | Small teams, fixed roles, strict separation of duties | Large orgs, many projects, shared accounts |

### Permission Boundary vs SCP

| Criterion | Permission Boundary | SCP |
| :--- | :--- | :--- |
| **Scope** | Single IAM user or role in one account | All principals in member accounts (org-wide) |
| **Grants permissions?** | No---caps maximum | No---caps maximum |
| **Bypassable by account admin?** | Admin can modify boundary if they have `iam:PutRolePermissionsBoundary` | Even root user in member account cannot override explicit SCP Deny |
| **Best fit** | Delegated developer self-service within an account | Org-wide guardrails (region lock, deny root actions, protect security roles) |

```mermaid
flowchart TD
    Start([Who or what needs AWS access?]) --> Human{Human operator?}

    Human -- Yes --> SSO[IAM Identity Center<br/>+ permission sets]
    Human -- No --> Compute{Runs on AWS compute?}

    Compute -- Yes --> AWSService{Which platform?}
    AWSService -- EC2/Lambda/ECS --> InstanceRole[Service-specific IAM role<br/>instance profile / execution role]
    AWSService -- EKS Pod --> K8sChoice{Cluster supports<br/>Pod Identity?}
    K8sChoice -- Yes, Linux EC2 --> PodId[EKS Pod Identity association]
    K8sChoice -- No / Fargate / existing IRSA --> IRSA[IRSA with OIDC trust]
    K8sChoice -- Cross-account from Pod --> IRSA

    Compute -- No --> Hybrid{Has X.509 PKI?}
    Hybrid -- Yes --> RA[IAM Roles Anywhere<br/>trust anchor + profile]
    Hybrid -- No --> Fed[Federate via SAML/OIDC<br/>or re-architect onto AWS]

    SSO --> Scope{Need org-wide max cap?}
    InstanceRole --> Scope
    PodId --> Scope
    IRSA --> Scope
    RA --> Scope

    Scope -- Account-level delegation --> Boundary[Permission boundary<br/>on creatable roles]
    Scope -- Org-wide guardrail --> SCP[Service Control Policy<br/>on OU/account]
    Scope -- Single session delegation --> SessionPol[Session policy at AssumeRole]
```

---

## Cost Lens: IAM Is Free, Visibility Is Not

[IAM itself, IAM Identity Center, and AWS STS incur no additional charge---you pay only when those credentials invoke other AWS services.](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html) This makes IAM deceptively "free" in budget conversations while the observability and governance tooling around it carries real line-item cost at scale. Understanding where charges appear prevents surprise finance reviews after you enable organization-wide least-privilege automation.

**CloudTrail** is the primary audit backbone for IAM activity. [Management events delivered via the 90-day Event history and the first copy of management events to S3 through a trail are available at no additional CloudTrail charge; however, CloudTrail Lake ingestion, advanced event selectors, and data events are billed separately.](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-aws-service-charges.html) Data events---which log object-level S3 operations and Lambda invocations---are priced per event and can spike unexpectedly if you enable them account-wide on high-traffic buckets. The cost knob is selective data-event logging: scope to sensitive buckets and keys rather than `ReadWriteType: All` on every S3 ARN in the organization.

**IAM Access Analyzer** splits free and paid tiers sharply. [External access analysis (public and cross-account findings) is free; unused access analysis is billed per IAM role and user per month; internal access analysis is billed per monitored resource per Region per month; custom policy checks are billed per API call.](https://aws.amazon.com/iam/access-analyzer/pricing/) A single organization with hundreds of roles and dozens of S3 buckets monitored for unused and internal access can reach hundreds of dollars monthly---still cheaper than one incident, but not zero. Enable unused-access analyzers first in production accounts where stale permissions matter most, rather than blindly at org root on day one.

**Identity Center** remains free; the cost surface is indirect. Engineers with broader permission sets can provision expensive resources. That is an IAM governance problem manifesting as EC2 or RDS bills rather than an IAM line item. Tag-based ABAC that prevents cross-project resource access often pays for itself by blocking accidental provisioning in wrong accounts. Finance teams sometimes miss this linkage until a quarterly review connects oversized permission sets to orphaned infrastructure spend.

Hypothetical scenario: a security team enables CloudTrail data events on all S3 buckets in a data-lake account processing billions of GET requests monthly. The IAM policies are perfect, but the CloudTrail bill triggers a finance escalation---the fix is narrowing data events to buckets holding PII, not removing audit capability entirely.

---

## Did You Know?

1.  The AWS IAM system [processes over **half a billion API calls per second** globally](https://aws.amazon.com/blogs/security/how-to-monitor-and-query-iam-resources-at-scale-part-1/), evaluating complex JSON policies in milliseconds without adding noticeable latency to requests. This makes it one of the highest-throughput authorization systems ever built.
2.  IAM is a globally distributed service, and policy or role changes can take time to propagate. If a newly created or updated identity fails immediately, retry with backoff before assuming the policy is wrong.
3.  [You can use the `aws:PrincipalOrgID` condition key in a resource policy (like an S3 bucket policy) to instantly restrict access to only principals originating from accounts within your specific AWS Organization, creating a powerful defense-in-depth layer. This single condition key replaces the need to list every account ID individually.](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html)
4.  IAM policy size and attachment quotas are real design constraints, but the exact limits vary by policy type and by entity; check the current IAM quotas before assuming a single universal size cap.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
| :--- | :--- | :--- |
| **Using `Resource: "*"` excessively** | It is easier than finding the exact ARN, especially when quickly trying to make a script work. | Always scope policies to the specific ARNs required. Use tags and condition keys if ARNs are dynamic. Use `aws iam simulate-principal-policy` to verify. |
| **Creating IAM Users for applications** | Passing access keys into applications feels natural for legacy app developers used to database connection strings. | Always use IAM Roles (via EC2 Instance Profiles, EKS IRSA/Pod Identity, or Lambda execution roles) to provide temporary credentials to compute resources. |
| **Ignoring the Trust Policy** | Teams focus on what the role can *do* (Permissions Policy) and forget to secure who can *assume* it (Trust Policy). | Review Trust Policies rigorously. Never use `Principal: "*"` in a trust policy unless strictly necessary and protected by strong Condition blocks (like `sts:ExternalId`). |
| **Failing to rotate Access Keys** | Human users with permanent keys keep them for years because "they still work" and rotating them requires updating local `.aws/credentials` files. | Enforce key rotation via AWS Config rules. Better yet, eliminate permanent keys entirely by migrating to IAM Identity Center for CLI access. |
| **Testing permissions in production** | Developers tweak JSON policies directly in the console until the error goes away, often over-provisioning access in the process. | Use the IAM Policy Simulator (`aws iam simulate-principal-policy`). Use AWS CloudTrail logs to see exactly which API call failed and why, then grant only that specific action. |
| **Misunderstanding Implicit vs Explicit Deny** | Believing that removing an `Allow` statement actively prevents an action, forgetting that another policy might still grant it. | [Understand that access requires an explicit Allow and NO explicit Deny anywhere in the evaluation chain (Identity policies, Resource policies, Boundaries, SCPs).](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html) |
| **Forgetting the S3 dual-ARN problem** | Granting `s3:GetObject` on a bucket ARN (without `/*`) or `s3:ListBucket` on the objects ARN (with `/*`). | Remember: `ListBucket` acts on the bucket (`arn:aws:s3:::bucket`), `GetObject`/`PutObject` act on objects (`arn:aws:s3:::bucket/*`). Always include both resource entries. |
| **Not using session tags or ExternalId for third parties** | Blindly trusting a cross-account role assumption because "the vendor told us to set it up this way." | [Always require `sts:ExternalId` in trust policies for third-party access. Without it, you are vulnerable to the Confused Deputy attack.](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html) Generate a unique, random ExternalId per vendor. |

---

## Quiz

<details>
<summary>Question 1: You have an IAM role attached to an EC2 instance. The role's policy explicitly allows `s3:GetObject` on `arn:aws:s3:::financial-reports/*`. However, the EC2 instance receives an Access Denied error when trying to download a file. A developer points out that there is an S3 Bucket Policy on the `financial-reports` bucket. What must the Bucket Policy contain for the download to succeed?</summary>

**Answer**: The Bucket Policy does not necessarily need to contain anything to allow the action, but it **must NOT** contain an Explicit Deny for that role or action. Because the IAM role already grants an explicit Allow, the evaluation logic permits the action as long as no resource policy (the Bucket Policy) or organizational policy (SCP) explicitly denies it. If the bucket and the EC2 instance are in the same account, the IAM policy alone is sufficient. However, if this were a **cross-account** scenario (EC2 in Account A, bucket in Account B), then the Bucket Policy in Account B *would* need to explicitly allow the EC2 role from Account A, because cross-account access requires both sides to grant permission.
</details>

<details>
<summary>Question 2: A developer proposes creating an IAM User with long-term access keys for a new microservice running on EC2, arguing it is simpler than configuring instance profiles. You must defend the use of an IAM Role instead. What is the primary security advantage of the IAM Role in this specific scenario?</summary>

**Answer**: IAM Roles use temporary security credentials generated dynamically by STS, which is a major security advantage over IAM Users. These credentials expire automatically (typically within 1 hour, configurable up to 12 hours), significantly reducing the blast radius if an attacker manages to steal them. Because the credentials cannot be used beyond their expiration time, the window of opportunity for an exploit is extremely limited. In contrast, IAM Users rely on long-term Access Keys that remain valid indefinitely until manually rotated or deleted. Furthermore, role credentials are automatically rotated by the AWS infrastructure (like the EC2 metadata service), meaning the application usually does not have to manage credential rotation logic itself.
</details>

<details>
<summary>Question 3: A third-party analytics vendor requires read access to an S3 bucket in your production AWS account. The vendor operates entirely out of their own AWS account. Your team debates whether to create a dedicated IAM User in your account for them or to configure cross-account Role access. Which approach should you choose and why?</summary>

**Answer**: You should set up cross-account Role access rather than creating an IAM User. To do this, you create a Role in your account with a Trust Policy that allows the vendor's account to assume it, strictly enforcing an `sts:ExternalId` condition to prevent the Confused Deputy problem. This approach eliminates the operational and security burden of managing the lifecycle, passwords, MFA, and key rotation for external users. Furthermore, when the vendor relationship ends, you simply delete the role, ensuring no orphaned long-term credentials are left behind to be potentially exploited.
</details>

<details>
<summary>Question 4: You are debugging an access issue for a junior developer. Their IAM user has an attached permission policy granting full access to `s3:*` and `rds:*`. However, the security team has applied a Permission Boundary to their user that only allows `ec2:*` and `s3:*`. When the developer attempts to restart an RDS database, the action fails. Why did this happen and what are their effective permissions?</summary>

**Answer**: The developer's effective permissions are only `s3:*`, which is why the RDS action failed. Effective permissions are always the intersection of the permissions boundary and the identity-based policy. In this scenario, the boundary allows EC2 but the identity policy does not grant it, and the identity policy grants RDS but the boundary does not allow it. Because only S3 actions appear in both the boundary and the identity policy, only S3 actions are permitted by the IAM evaluation engine.
</details>

<details>
<summary>Question 5: You are configuring a cross-account IAM role to allow a third-party Cloud Security Posture Management (CSPM) SaaS provider to audit your AWS account. The documentation insists you must include an `ExternalId` in the trust policy. What specific attack does this parameter prevent, and how does it work?</summary>

**Answer**: The `ExternalId` parameter prevents the "Confused Deputy" problem. If multiple customers use the same third-party SaaS, an attacker who is also a customer could trick the SaaS provider's system into assuming the IAM role belonging to your account by providing your Role ARN (which may be public or easily guessable). By requiring a unique, secret `ExternalId` (which you generate and configure in both the SaaS portal and your Trust Policy), you ensure the SaaS provider only assumes your role when acting specifically on your behalf. Since the attacker cannot guess your ExternalId, their attempt to provide your Role ARN will fail the Trust Policy condition.
</details>

<details>
<summary>Question 6: An incident response script running in a member account of your AWS Organization fails to terminate a compromised EC2 instance. The script assumes an IAM role that has an identity-based policy explicitly granting `ec2:*`. However, the Organization's root account has an SCP applied that denies `ec2:TerminateInstances` outside of approved maintenance windows. Will the script succeed in terminating the instance?</summary>

**Answer**: No, the script will fail to terminate the instance. Service Control Policies (SCPs) define the maximum available permissions for any principal within an account, acting as the highest guardrail in the authorization chain. Even though the IAM role's identity policy explicitly allows `ec2:*`, the explicit deny in the SCP immediately overrides any allow in an identity policy. In fact, even the member account's root user cannot bypass an SCP restriction, meaning the action is permanently blocked until the SCP condition is met or modified.
</details>

<details>
<summary>Question 7: A Lambda function needs to read from DynamoDB and write to an SQS queue. A junior engineer creates an IAM user, generates access keys, and hardcodes them in the Lambda environment variables. What are at least three things wrong with this approach?</summary>

**Answer**: First, IAM user access keys never expire automatically, meaning if they are leaked in CloudWatch logs or a git commit, they remain valid indefinitely until manually deleted. Second, embedding long-term credentials in environment variables violates security best practices, as the keys are easily exposed if the Lambda configuration is exported or viewed. Third, this approach lacks automatic key rotation, meaning the keys will remain unchanged forever unless manually rotated. The correct, secure approach is to use a Lambda execution role, which dynamically provides automatically rotating, temporary STS credentials to the function at invocation time.
</details>

<details>
<summary>Question 8: Your startup is rapidly prototyping a new application and the lead developer suggests attaching the AWS Managed Policy `AmazonS3FullAccess` to the application's roles to save time, rather than writing Customer Managed Policies. What is the primary operational benefit of this approach, and what critical security tradeoff are they making?</summary>

**Answer**: The primary operational benefit of using AWS Managed Policies is that they are maintained and automatically updated by AWS. Whenever AWS releases a new feature or API action for a service, they update the relevant managed policies, saving administrators the overhead of constantly updating custom policies to keep pace. However, the critical tradeoff is a severe reduction in control and a high likelihood of over-provisioning permissions, which violates the principle of least privilege. For example, `AmazonS3FullAccess` grants access to all S3 buckets in the account, exposing potentially sensitive data to the application unnecessarily. It is highly recommended to use scoped Customer Managed Policies for production workloads.
</details>

---

## Hands-On Exercise: Multi-Account IAM and Least Privilege

In this exercise, we will simulate a scenario where an application running in a "Development" environment needs to read configuration data from a centralized "Shared Services" environment. We will use two IAM roles within the same account to simulate the cross-account boundary and practice `AssumeRole` mechanics from the CLI.

**What you will practice:** complete this exercise end-to-end by creating scoped roles, validating cross-role access boundaries, and confirming failures where access should be denied by design.

- Creating roles with custom trust policies
- Writing scoped permissions policies (least privilege)
- Using STS to assume a role and obtain temporary credentials
- Verifying that least privilege works (allowed actions succeed, everything else fails)
- Using Permission Boundaries to limit privilege escalation
- Cleaning up all resources

### Lab Preflight and Cost Expectations

Before executing these commands, ensure your active AWS CLI profile possesses administrative IAM permissions (`iam:*`, `sts:*`, and `s3:*`) to create roles, attach managed and inline policies, and provision buckets. The operational cost of this hands-on lab is effectively zero because AWS IAM and AWS STS API calls are completely free of charge. Creating a temporary S3 bucket with several small JSON configuration files incurs negligible storage costs and does not enable billed CloudTrail data events. Performing the cleanup step at the conclusion of this lab is strictly mandatory to prevent lingering permissive test roles and orphaned storage buckets from cluttering your cloud environment.

### Task 1: Set Up Your Environment Variables

```bash
# Get your account ID (you'll need this throughout)
export ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
echo "Account ID: $ACCOUNT_ID"

# Set a unique bucket name
export CONFIG_BUCKET="dojo-shared-config-$(date +%s)"
echo "Bucket name: $CONFIG_BUCKET"

# Verify your current identity
aws sts get-caller-identity
```

### Task 2: Create the Data Source (S3 Bucket)

First, let us create a bucket to act as our centralized configuration store, and then use it as a controlled test asset for verifying whether role-based read/write rules are working exactly as intended.

```bash
# Create the bucket
aws s3 mb s3://$CONFIG_BUCKET

# Create sample config files and upload them
echo '{"db_port": 5432, "api_endpoint": "api.internal.local"}' > config.json
echo '{"secret": "do-not-read-this"}' > secret.json

aws s3 cp config.json s3://$CONFIG_BUCKET/app/config.json
aws s3 cp secret.json s3://$CONFIG_BUCKET/secrets/secret.json

# Verify the uploads
aws s3 ls s3://$CONFIG_BUCKET --recursive
```

### Task 3: Create the Target Role (The Role to be Assumed)

This role represents the permissions needed in the Shared Services account. We will attach a strict policy allowing read access *only* to the `app/` prefix in this specific bucket---not the `secrets/` prefix.

```bash
# 1. Create the trust policy document allowing your current identity to assume it
cat << EOF > trust-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::${ACCOUNT_ID}:root"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Verify the trust policy looks correct
cat trust-policy.json | jq .

# 2. Create the Role
aws iam create-role \
  --role-name DojoSharedConfigReaderRole \
  --assume-role-policy-document file://trust-policy.json

# 3. Create the strictly scoped permissions policy
# Note: we only allow reading from app/* prefix, NOT secrets/*
cat << EOF > permissions-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowListBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::${CONFIG_BUCKET}",
      "Condition": {
        "StringLike": {
          "s3:prefix": ["app/*"]
        }
      }
    },
    {
      "Sid": "AllowReadAppConfig",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::${CONFIG_BUCKET}/app/*"
    }
  ]
}
EOF

# Verify the permissions policy
cat permissions-policy.json | jq .

# 4. Attach the inline policy to the role
aws iam put-role-policy \
  --role-name DojoSharedConfigReaderRole \
  --policy-name S3ConfigReadAccess \
  --policy-document file://permissions-policy.json

# 5. Verify the role was created correctly
aws iam get-role --role-name DojoSharedConfigReaderRole --query 'Role.Arn'
aws iam get-role-policy --role-name DojoSharedConfigReaderRole --policy-name S3ConfigReadAccess
```

### Task 4: Assume the Role via CLI

Now, pretend you are the application. You need to call STS to get temporary credentials for the `DojoSharedConfigReaderRole`.

```bash
# Get the Role ARN
ROLE_ARN=$(aws iam get-role --role-name DojoSharedConfigReaderRole --query 'Role.Arn' --output text)
echo "Assuming role: $ROLE_ARN"

# Assume the role using STS (request 1-hour session)
aws sts assume-role \
  --role-arn $ROLE_ARN \
  --role-session-name AppConfigSession \
  --duration-seconds 3600 > assume-role-output.json

# Inspect the output - note the Expiration field
cat assume-role-output.json | jq '.Credentials.Expiration'

# Extract and export the temporary credentials
export AWS_ACCESS_KEY_ID=$(jq -r '.Credentials.AccessKeyId' assume-role-output.json)
export AWS_SECRET_ACCESS_KEY=$(jq -r '.Credentials.SecretAccessKey' assume-role-output.json)
export AWS_SESSION_TOKEN=$(jq -r '.Credentials.SessionToken' assume-role-output.json)
```

### Task 5: Verify Least Privilege (The Critical Tests)

Now that you are operating under the assumed role, verify what you can and cannot do. Each test validates a specific aspect of your policy.

```bash
# Verify your active identity (should show the assumed role, not your original user)
aws sts get-caller-identity
# Expected: "Arn" contains "assumed-role/DojoSharedConfigReaderRole/AppConfigSession"

# --- TEST 1: Read allowed config file (SHOULD SUCCEED) ---
aws s3 cp s3://$CONFIG_BUCKET/app/config.json /tmp/downloaded-config.json
cat /tmp/downloaded-config.json
echo "TEST 1 PASSED: Successfully read app config"

# --- TEST 2: List objects in app/ prefix (SHOULD SUCCEED) ---
aws s3 ls s3://$CONFIG_BUCKET/app/
echo "TEST 2 PASSED: Successfully listed app/ prefix"

# --- TEST 3: Read secret file (SHOULD FAIL - Access Denied) ---
aws s3 cp s3://$CONFIG_BUCKET/secrets/secret.json /tmp/secret.json 2>&1 || \
  echo "TEST 3 PASSED: Correctly denied access to secrets/"

# --- TEST 4: Write to the bucket (SHOULD FAIL - Access Denied) ---
echo "hacked" > /tmp/test.txt
aws s3 cp /tmp/test.txt s3://$CONFIG_BUCKET/app/test.txt 2>&1 || \
  echo "TEST 4 PASSED: Correctly denied write access"

# --- TEST 5: Access a different AWS service entirely (SHOULD FAIL) ---
aws ec2 describe-instances 2>&1 || \
  echo "TEST 5 PASSED: Correctly denied access to EC2"

# --- TEST 6: Try to escalate by creating a new role (SHOULD FAIL) ---
aws iam create-role --role-name HackerRole \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[]}' 2>&1 || \
  echo "TEST 6 PASSED: Correctly denied IAM access"
```

### Task 6: Create a Permission Boundary (Bonus)

Let us also practice creating a Permission Boundary. First, revert to your original identity, then create a boundary and a role that would otherwise be over-privileged so you can verify that the effective permissions are reduced by design.

```bash
# Revert to original identity
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
aws sts get-caller-identity

# Create a permission boundary that only allows S3 and DynamoDB
cat << EOF > boundary-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BoundaryAllowS3AndDynamo",
      "Effect": "Allow",
      "Action": [
        "s3:*",
        "dynamodb:*"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Create the boundary as a managed policy
aws iam create-policy \
  --policy-name DojoBoundaryPolicy \
  --policy-document file://boundary-policy.json

BOUNDARY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/DojoBoundaryPolicy"

# Create a new role WITH the boundary attached
cat << EOF > bounded-trust.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::${ACCOUNT_ID}:root"},
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name DojoBoundedRole \
  --assume-role-policy-document file://bounded-trust.json \
  --permissions-boundary $BOUNDARY_ARN

# Attach a policy that tries to grant ec2:* (boundary should block it)
cat << EOF > overreach-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:*", "ec2:*", "dynamodb:*"],
      "Resource": "*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name DojoBoundedRole \
  --policy-name OverreachPolicy \
  --policy-document file://overreach-policy.json

# Assume the bounded role and test
BOUNDED_ROLE_ARN=$(aws iam get-role --role-name DojoBoundedRole --query 'Role.Arn' --output text)
aws sts assume-role \
  --role-arn $BOUNDED_ROLE_ARN \
  --role-session-name BoundaryTest > bounded-output.json

export AWS_ACCESS_KEY_ID=$(jq -r '.Credentials.AccessKeyId' bounded-output.json)
export AWS_SECRET_ACCESS_KEY=$(jq -r '.Credentials.SecretAccessKey' bounded-output.json)
export AWS_SESSION_TOKEN=$(jq -r '.Credentials.SessionToken' bounded-output.json)

# S3 should work (in both policy AND boundary)
aws s3 ls 2>&1 && echo "BOUNDARY TEST 1: S3 allowed (expected)"

# EC2 should fail (in policy but NOT in boundary)
aws ec2 describe-instances 2>&1 || echo "BOUNDARY TEST 2: EC2 blocked by boundary (expected)"
```

### Task 7: Independent Policy Layer Diagnosis

An operator testing delegated workload credentials executes an administrative inspection command against the database cluster and observes the following failure:

```bash
aws rds describe-db-instances
An error occurred (AccessDenied) when calling the DescribeDBInstances operation: User: arn:aws:sts::123456789012:assumed-role/DojoBoundedRole/BoundaryTest is not authorized to perform: rds:DescribeDBInstances
```

Trace the IAM policy evaluation hierarchy to identify exactly which policy layer blocked this call. Determine whether the rejection occurred at the organization SCP, permissions boundary, role identity policy, or resource policy layer.

<details>
<summary>Check your diagnosis</summary>

Failure layer: Role identity-based policy. Although the role has an attached permissions boundary, evaluation requires an explicit Allow in the identity-based policy (`OverreachPolicy`) for the requested action. Because `OverreachPolicy` only specifies `s3:*`, `ec2:*`, and `dynamodb:*`, the request for `rds:DescribeDBInstances` encounters an implicit deny at the identity layer, blocking the call before boundary intersection even matters.

</details>

### Clean Up

Clear the temporary credentials from your environment and delete all resources. This finalization step matters because it prevents accidental reuse of the demo credentials and leaves your account in a reproducible, clean state for another learner.

```bash
# Remove temporary credentials to revert to your original admin identity
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

# Verify you are back to your admin identity
aws sts get-caller-identity

# Delete the bounded role and its resources
aws iam delete-role-policy --role-name DojoBoundedRole --policy-name OverreachPolicy
aws iam delete-role --role-name DojoBoundedRole
aws iam delete-policy --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/DojoBoundaryPolicy

# Delete the config reader role and its resources
aws iam delete-role-policy --role-name DojoSharedConfigReaderRole --policy-name S3ConfigReadAccess
aws iam delete-role --role-name DojoSharedConfigReaderRole

# Delete the S3 bucket
aws s3 rm s3://$CONFIG_BUCKET --recursive
aws s3 rb s3://$CONFIG_BUCKET

# Clean up local files
rm -f trust-policy.json permissions-policy.json config.json secret.json \
  assume-role-output.json boundary-policy.json bounded-trust.json \
  overreach-policy.json bounded-output.json /tmp/test.txt /tmp/downloaded-config.json /tmp/secret.json

echo "All resources cleaned up successfully."
```

**Card A: Same-account S3 GetObject always needs a bucket policy.** An infrastructure engineer configures an IAM role with an identity-based policy permitting `s3:GetObject` on a private company bucket in the same account. Believing that Amazon S3 objects are fundamentally inaccessible without an explicit resource policy attached to the bucket, the engineer delays deployment to write custom bucket policies for every target. They assume that identity-based permissions remain completely inactive until the destination bucket acknowledges the requesting principal directly.

<details>
<summary>Check your prediction</summary>

Failure layer: Misunderstanding single-account S3 authorization logic. Next action: Rely on the identity-based policy alone for same-account access when no explicit bucket deny exists, reserving bucket policies for cross-account delegation or resource-level guardrails.

</details>

**Card B: A permission boundary by itself grants permissions.** A security administrator attaches a managed permission boundary allowing broad S3 and DynamoDB operations to a newly provisioned developer role. The administrator assumes the boundary immediately equips the role with active capabilities to query tables and retrieve objects across the development account. Because the policy document contains explicit Allow statements, the team deploys the role to production without attaching any standard identity policies.

<details>
<summary>Check your prediction</summary>

Failure layer: Equating an authorization ceiling with an active permission grant. Next action: Attach an identity-based permissions policy containing explicit Allow statements alongside the boundary, recognizing that effective permissions require both policies to allow the action.

</details>

**Card C: AdministratorAccess plus a later cleanup is a safe bootstrap.** A cloud engineering team assigns `AdministratorAccess` to an experimental microservice role so that developers can build features without encountering permissions errors during early sprints. The team plans to review CloudTrail logs and replace the broad policy with fine-grained permissions right before releasing the application to production. They operate under the belief that granting temporary full privileges speeds up early delivery without imposing security exposure on non-production infrastructure.

<details>
<summary>Check your prediction</summary>

Failure layer: Underestimating developmental blast radius and technical debt inertia. Next action: Start with zero permissions and iteratively grant required service actions as code evolves, preventing over-privileged credentials from persisting into production.

</details>

**Card D: sts:AssumeRole success means the session can do everything the role identity policy allows, ignoring SCPs and session policies.** An integration engineer successfully assumes a deployment role using the AWS CLI and confirms that the assumed-role session token was generated without error. Because STS permitted the assume-role request, the engineer assumes every action listed in the role's identity policy will execute successfully throughout the session. They treat the assume-role API success as proof that later service calls cannot be denied.

<details>
<summary>Check your prediction</summary>

Failure layer: Conflating successful role assumption with unrestricted downstream API authorization. Next action: Trace the complete authorization intersection including SCPs, permission boundaries, and session policies when diagnosing unexpected runtime denials on assumed sessions.

</details>

**Success Criteria**:

- [ ] I created a role with a custom trust policy and verified it with `get-role`.
- [ ] I used `sts assume-role` to generate temporary credentials and verified my new identity with `get-caller-identity`.
- [ ] I confirmed the role could read the `app/` prefix but was denied access to the `secrets/` prefix (demonstrating path-level scoping).
- [ ] I confirmed the role was denied write access to S3 and had no access to EC2 or IAM.
- [ ] I created a Permission Boundary and verified that it restricted effective permissions to the intersection of the boundary and the identity policy.
- [ ] I cleaned up all resources (roles, policies, bucket, local files) and verified my original identity was restored.

---

## Next Module

Ready to build the network foundation where your identities will operate? Head to [Module 1.2: VPC & Core Networking](../module-1.2-vpc/).

## Sources

- [docs.aws.amazon.com: best practices.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html) — AWS's IAM best-practices page recommends federation and IAM Identity Center for human users and temporary credentials over long-term IAM-user credentials.
- [docs.aws.amazon.com: reference policies elements principal.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_principal.html) — The Principal element reference explicitly says IAM user groups cannot be identified as principals in a policy.
- [docs.aws.amazon.com: id roles.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles.html) — The IAM roles guide directly states that roles lack long-term credentials and issue temporary credentials when assumed.
- [docs.aws.amazon.com: elb service linked roles.html](https://docs.aws.amazon.com/elasticloadbalancing/latest/userguide/elb-service-linked-roles.html) — The ELB service-linked-role guide covers the exact role name, automatic creation behavior, and IAM editing limits.
- [docs.aws.amazon.com: id roles update role trust policy.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_update-role-trust-policy.html) — AWS's trust-policy documentation directly defines trust policy as the mechanism that controls who can assume a role.
- [docs.aws.amazon.com: API AssumeRole.html](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html) — The `AssumeRole` API reference documents temporary credentials, the 1–12 hour session-duration limit, session-policy intersection semantics, and the 2,048-character session-policy limit.
- [docs.aws.amazon.com: access policies managed versioning.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_managed-versioning.html) — AWS's managed-policy versioning documentation explicitly states the five-version limit and rollback behavior.
- [docs.aws.amazon.com: reference policies elements version.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_version.html) — The IAM `Version` element reference directly compares `2012-10-17` and `2008-10-17` and notes policy-variable support.
- [docs.aws.amazon.com: reference policies examples s3 rw bucket.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_examples_s3_rw-bucket.html) — The S3 IAM policy example shows `s3:ListBucket` on the bucket ARN and object actions on the `bucket/*` ARN.
- [docs.aws.amazon.com: reference policies evaluation logic.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html) — AWS's policy-evaluation documentation describes default deny, explicit deny precedence, and intersection behavior with boundaries and SCPs.
- [docs.aws.amazon.com: intro structure.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/intro-structure.html) — The IAM 'How IAM works' guide explicitly states that cross-account access requires a policy in the other account and an identity-based allow for the caller.
- [docs.aws.amazon.com: manage your identity source idp.html](https://docs.aws.amazon.com/singlesignon/latest/userguide/manage-your-identity-source-idp.html) — The IAM Identity Center external-IdP documentation states that users sign in with corporate credentials and get automatic short-term credential generation and rotation.
- [docs.aws.amazon.com: access policies boundaries.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html) — AWS's permissions-boundaries guide states both the maximum-permissions model and the intersection semantics.
- [docs.aws.amazon.com: orgs manage policies scps.html](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html) — The AWS Organizations SCP guide directly states these three behaviors.
- [docs.aws.amazon.com: access analyzer policy generation.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/access-analyzer-policy-generation.html) — AWS documents policy generation from CloudTrail events on the IAM Access Analyzer policy-generation page.
- [docs.aws.amazon.com: tutorial attribute based access control.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/tutorial_attribute-based-access-control.html) — AWS's ABAC tutorial explicitly says tag-based policies let teams and resources grow with fewer policy changes.
- [aws.amazon.com: how to monitor and query iam resources at scale part 1](https://aws.amazon.com/blogs/security/how-to-monitor-and-query-iam-resources-at-scale-part-1/) — An AWS Security Blog post states that AWS Identity handles over half a billion API calls per second worldwide.
- [docs.aws.amazon.com: reference policies condition keys.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html) — The global condition-keys reference explicitly describes `aws:PrincipalOrgID` as an alternative to listing all account IDs.
- [docs.aws.amazon.com: confused deputy.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html) — AWS's confused-deputy guidance directly explains the role of `ExternalId` in third-party cross-account access.
- [docs.aws.amazon.com: pod-identities.html](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html) — EKS Pod Identity documentation covers the `pods.eks.amazonaws.com` trust principal, agent-based credential delivery, and comparison with IRSA.
- [docs.aws.amazon.com: iam-roles-for-service-accounts.html](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html) — IRSA documentation describes OIDC federation, projected service account tokens, and IMDS isolation requirements.
- [docs.aws.amazon.com: id credentials temp control-access assumerole.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_control-access_assumerole.html) — AWS explains session policies as further-restrict-only filters at role assumption time.
- [docs.aws.amazon.com: reference policies elements notaction.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_notaction.html) — NotAction element reference warns that Allow + NotAction can over-provision unintentionally.
- [docs.aws.amazon.com: reference policies elements notresource.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_notresource.html) — NotResource element reference explicitly warns against Allow + Action * + NotResource combinations.
- [docs.aws.amazon.com: rolesanywhere introduction.html](https://docs.aws.amazon.com/rolesanywhere/latest/userguide/introduction.html) — IAM Roles Anywhere guide covers trust anchors, profiles, X.509 authentication, and hybrid workload credentialing.
- [docs.aws.amazon.com: cloudtrail-aws-service-charges.html](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-aws-service-charges.html) — CloudTrail pricing documentation distinguishes free management-event delivery from billed Lake and data events.
- [aws.amazon.com: iam access-analyzer pricing](https://aws.amazon.com/iam/access-analyzer/pricing/) — IAM Access Analyzer pricing page separates free external access analysis from billed unused and internal access analyzers.
