---
title: "Module 9.1: Managed Database Integration (RDS / Cloud SQL / Azure / NoSQL)"
slug: cloud/managed-services/module-9.1-databases
sidebar:
  order: 2
---
**Complexity**: `[MEDIUM]` | **Time to Complete**: 2h | **Prerequisites**: Cloud Essentials (any provider), Kubernetes networking basics

## What You'll Be Able to Do

After completing this module, you will be able to:

- **Configure private connectivity from Kubernetes pods to managed databases (RDS, Cloud SQL, Flexible Server) using VPC-native networking**
- **Implement connection pooling with PgBouncer or ProxySQL sidecars to optimize database connection management from pods**
- **Deploy automated credential rotation for database secrets using cloud-native rotation with Kubernetes External Secrets Operator**
- **Design high-availability database architectures with cross-AZ failover that Kubernetes workloads survive transparently**
- **Compare relational, document, key-value, and globally distributed managed databases across AWS, GCP, and Azure and choose the right engine for a Kubernetes workload**

---

## Why This Module Matters

Hypothetical scenario: a platform team runs PostgreSQL on Kubernetes with a StatefulSet backed by zone-local persistent volumes. During a regional AZ impairment, pods reschedule cleanly but the database volume remains pinned to the failed zone, and read traffic saturates cross-AZ links while failover scripts run manually. The incident is survivable, but the recovery path consumes senior database time that was supposed to go toward product features.

Many production teams reach the same conclusion without waiting for that outage: Kubernetes excels at stateless orchestration, while managed database services absorb the operational burden of automated failover, point-in-time recovery (PITR), engine patching, and cross-AZ or cross-region replication. The engineering challenge then shifts from "keeping PostgreSQL alive" to "connecting Kubernetes workloads to the right managed database securely, efficiently, and at predictable cost."

This module teaches that integration layer across AWS, GCP, and Azure. You will connect pods through private networking, tame connection storms with pooling and managed proxies, rotate credentials without downtime, run schema migrations safely in GitOps pipelines, and design HA/DR topologies that survive AZ and regional failures. You will also learn when a relational engine, a document store, or a globally distributed database is the correct choice — and when an in-cluster operator still makes sense.

---

## Multi-Cloud Relational Database Landscape

Relational managed databases remain the default for transactional applications: orders, ledgers, identity records, and anything that needs ACID guarantees with SQL ergonomics. Each cloud offers a spectrum from "lift-and-shift compatible" to "cloud-native rewrite," and Kubernetes integration patterns differ subtly across them.

**AWS: RDS and Aurora.** [Amazon RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html) supports PostgreSQL, MySQL, MariaDB, SQL Server, and Oracle as managed instances with familiar engines. RDS Multi-AZ maintains a synchronous standby in another Availability Zone; on primary failure, AWS promotes the standby and updates the endpoint DNS name, typically within about 60–120 seconds depending on workload and engine. Read replicas are asynchronous and scale read traffic — they are not automatic failover targets unless you promote one manually. For Kubernetes teams, RDS remains the default lift-and-shift path when your Helm charts already expect a PostgreSQL connection string and your ORM migration folder targets standard SQL dialect features without Spanner-style interleaved tables.

[Aurora](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/CHAP_AuroraOverview.html) replicates storage at the volume layer across three AZs in a region. Storage durability is decoupled from compute. Aurora Serverless v2 autoscales Aurora Capacity Units (ACUs) based on load. You avoid picking a fixed instance size upfront for spiky Kubernetes microservices. [Aurora Global Database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html) adds up to 10 read-only secondary clusters in other regions. Replication latency is typically under one second. That supports regional DR and low-latency global reads from the writer endpoint in the primary region. When EKS spans multiple regions for latency, each regional cluster can read locally while writes funnel to the primary. Application code must tolerate write latency to the primary region or use Aurora write forwarding where supported.

**GCP: Cloud SQL, AlloyDB, and Spanner.** [Cloud SQL](https://cloud.google.com/sql/docs) offers managed PostgreSQL, MySQL, and SQL Server with regional HA (primary + standby in another zone within the region) and optional cross-region read replicas for DR or migration. Private IP connectivity uses VPC peering to Google's managed services network, which is the pattern you use from GKE workloads that should never traverse the public internet to reach data. Cloud SQL Auth Proxy sidecars remain popular for local development parity even when production uses private IP, because the proxy handles TLS and IAM login consistently across environments.

[AlloyDB for PostgreSQL](https://cloud.google.com/alloydb/docs/overview) targets PostgreSQL-compatible OLTP with a disaggregated storage/compute architecture and columnar acceleration for analytics-style queries without leaving the transactional engine. Choose AlloyDB when PostgreSQL compatibility matters but you need higher throughput than standard Cloud SQL tiers at moderate scale — for example, a GKE-hosted SaaS with heavy read/write contention on a single large tenant table where Cloud SQL CPU pegs during business hours.

[Cloud Spanner](https://cloud.google.com/spanner/docs) is a different species: horizontally scalable, globally distributed, and externally consistent thanks to [TrueTime](https://cloud.google.com/spanner/docs/true-time-external-consistency). Spanner suits workloads that outgrow single-primary relational limits — global inventory, financial ledgers spanning regions — at the cost of Spanner-specific schema design and pricing. From Kubernetes, you connect like any external database using private IP or authorized networks, with client libraries that understand Spanner's SQL dialect and interleaved index patterns that differ from idiomatic PostgreSQL migrations.

**Azure: SQL Database and Flexible Server.** [Azure SQL Database](https://learn.microsoft.com/en-us/azure/azure-sql/database/sql-database-paas-overview) offers DTU-based (bundled compute/storage/I/O) and vCore-based (transparent hardware choice) purchasing models. The [Hyperscale tier](https://learn.microsoft.com/en-us/azure/azure-sql/database/service-tier-hyperscale) separates compute from storage for very large databases with fast scale-out reads via replicas — think multi-terabyte SaaS tenants where storage growth outpaces CPU needs and AKS-hosted services must query without resharding application code.

[Azure Database for PostgreSQL Flexible Server](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/overview) and the MySQL equivalent integrate directly into your VNet with private DNS (`privatelink.postgres.database.azure.com`), zone-redundant HA, and geo-replication via read replicas in other regions. This is the Azure counterpart to RDS/Cloud SQL for AKS workloads that speak standard PostgreSQL wire protocol, and it pairs naturally with Entra Workload ID for Key Vault–backed credentials synced through External Secrets Operator.

| Dimension | AWS RDS/Aurora | GCP Cloud SQL / AlloyDB | Azure SQL / Flexible Server |
|-----------|----------------|-------------------------|----------------------------|
| Primary HA model | Multi-AZ sync standby; Aurora storage replication | Regional HA (primary + standby zone) | Zone-redundant HA option |
| Read scaling | Read replicas (async); Aurora readers in cluster | Read replicas; AlloyDB read pools | Geo-replicas; Hyperscale secondaries |
| Global distribution | Aurora Global Database (≤10 secondary regions) | Cross-region Cloud SQL replicas; Spanner natively global | Geo-replicated Flexible Server read replicas |
| Typical K8s access | Private subnets + security groups; RDS Proxy optional | Private IP via VPC peering | VNet integration + private DNS |
| Best fit | Broad engine support; mature ecosystem | PostgreSQL-heavy GCP estates | Microsoft stack + PostgreSQL/MySQL on Azure |

---

## NoSQL and Purpose-Built Managed Databases

Not every Kubernetes workload belongs on PostgreSQL. Session stores, product catalogs with flexible schema, high-velocity telemetry keys, and globally replicated shopping carts each map to different data models — and each cloud ships purpose-built managed services that integrate with Kubernetes through private networking and workload identity rather than in-cluster StatefulSets. The decision is not "SQL vs NoSQL" in the abstract; it is whether your access patterns, consistency requirements, and operational budget align with a single-primary relational engine or a horizontally partitioned store designed for keyed lookups at planet scale.

**Choosing relational vs document vs key-value vs wide-column.** Relational engines win when you need joins, constraints, and transactional updates across normalized tables — billing, accounts, reservations. Document stores ([Amazon DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction.html) items, [Firestore](https://firebase.google.com/docs/firestore) documents, [Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/introduction) JSON documents) excel when access patterns are keyed lookups with optional secondary indexes and schema flexibility matters more than ad-hoc joins. Key-value caches (often ElastiCache/Memorystore — see Module 9.5) sit in front of databases; wide-column stores like [Bigtable](https://cloud.google.com/bigtable/docs) target massive throughput time-series or analytics ingestion where single-row latency at billions of rows is the design center. Hybrid architectures are common: PostgreSQL as system of record, DynamoDB for high-velocity session state, and Bigtable for append-only telemetry — each accessed from the same Kubernetes namespace via distinct Services and IAM roles.

**AWS DynamoDB.** DynamoDB offers on-demand capacity (pay per request) and provisioned capacity (predictable RCU/WCU with autoscaling). [Global tables](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GlobalTables.html) provide multi-region active-active replication for eventually consistent cross-region reads; design for idempotent writers because conflict resolution is last-writer-wins at the item level. From EKS, access DynamoDB through the AWS SDK with [IAM Roles for Service Accounts (IRSA)](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html) or [EKS Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html) — no long-lived access keys in Secrets. Partition key design is the Kubernetes-adjacent lesson: hot partitions from a poorly chosen key hurt every pod equally, so load tests must include realistic shard distribution, not just pod count.

**GCP Firestore and Bigtable.** Firestore (Native mode) is a serverless document database with real-time listeners — common for mobile/web backends called from services on GKE. Bigtable is a wide-column store for high-throughput, low-latency workloads (metrics, IoT, ML feature stores) where you design row keys carefully to avoid hot partitions. Both integrate via Google client libraries and [GKE Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity) for keyless authentication, which means your Deployment manifests reference a Kubernetes ServiceAccount while GCP IAM bindings enforce which tables or collections that workload may touch.

**Azure Cosmos DB.** Cosmos DB exposes multiple APIs (SQL, MongoDB, Cassandra, Gremlin, Table) over a globally distributed storage engine. It offers [five consistency levels](https://learn.microsoft.com/en-us/azure/cosmos-db/consistency-levels) from strong to eventual, letting you trade latency for correctness per container. Critically, the [conflict resolution policy is immutable after container creation](https://learn.microsoft.com/en-us/azure/cosmos-db/conflict-resolution-policies) — choose last-writer-wins vs custom merge logic at design time, not after launch. Multi-region writes enable active-active patterns for globally distributed Kubernetes Deployments fronted by Traffic Manager or a global load balancer, but your microservices must implement compensating transactions when merge semantics reject conflicting updates.

| Workload signal | Lean toward | Why |
|-----------------|-------------|-----|
| Multi-table ACID transactions | RDS / Cloud SQL / Flexible Server | Mature SQL + FK constraints |
| Single-digit ms keyed lookups at huge scale | DynamoDB / Cosmos DB (partition key design) | Horizontal partition scaling |
| Flexible nested JSON, mobile sync | Firestore | Document model + offline clients |
| Billions of rows, scan-heavy analytics | Bigtable / DynamoDB streams + analytics | Wide-column throughput |
| Global external consistency | Spanner / Cosmos DB (strong) | Coordinated cross-region commits |

---

## Private Network Connectivity

The first rule of database connectivity from Kubernetes: **avoid exposing your database to the public internet whenever possible**. Every cloud provider offers private endpoint mechanisms that keep traffic on the provider's backbone network. Production clusters should treat a publicly reachable database endpoint as a temporary lab mistake. Private connectivity also simplifies compliance narratives. Auditors can draw a clear boundary: pods and databases communicate inside RFC1918 space or peered networks, not across the public internet.

**Architecture: VPC-native connectivity.** The diagram below shows the mental model every integration follows regardless of cloud: pods talk to a stable in-cluster DNS name, network policy and security groups enforce least privilege, and the managed database listens only on private addresses inside the peered VPC or VNet.

```mermaid
flowchart LR
    subgraph K8sVPC [Kubernetes VPC]
        PodA[Pod A]
        PodB[Pod B]
        Svc[ClusterIP Service]
        PodA --> Svc
        PodB --> Svc
    end
    
    subgraph DBSvc [Database Service]
        Primary[Primary AZ-a]
        Replica[Replica AZ-b]
    end
    
    Svc -- VPC Peering/Private Endpoint ---> Primary
```

**Pause and predict:** When an application pod in availability zone A executes queries against a managed database instance located in availability zone B over a private VPC peering connection, what operational and billing consequence occurs?

<details>
<summary>Check your prediction</summary>

Cross-AZ private traffic is still billed data transfer, whereas same-AZ private IP communication incurs zero inter-zone network fees. Major cloud providers meter and bill inter-zone traffic in both directions whenever packets cross an Availability Zone boundary, even when routing entirely within private VPC subnets. In addition to compounding egress and ingress costs for high-throughput database workloads, inter-zone transit introduces network latency overhead compared to co-located compute and storage.
</details>

Platform engineers minimize inter-zone network charges and query overhead by aligning compute placements with database primary instances across cluster node groups.

**AWS: RDS with VPC private subnets.** On AWS, your EKS cluster and RDS instance should share the same VPC or use VPC peering. [RDS instances deployed into private subnets are accessible from any resource within the VPC](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.WorkingWithRDSInstanceinaVPC.html). Security groups are the primary enforcement layer: allow TCP 5432 (or your engine port) only from the EKS node security group or pod security group if you use Security Groups for Pods, rather than opening the entire `10.0.0.0/8` supernet because it was faster during sprint planning.

```bash
# Create a DB subnet group using private subnets
aws rds create-db-subnet-group \
  --db-subnet-group-name eks-database-subnets \
  --db-subnet-group-description "Private subnets for RDS from EKS" \
  --subnet-ids subnet-0a1b2c3d4e5f00001 subnet-0a1b2c3d4e5f00002

# Create a security group allowing traffic from EKS node CIDR
aws ec2 create-security-group \
  --group-name rds-from-eks \
  --description "Allow PostgreSQL from EKS nodes" \
  --vpc-id vpc-0abc123def456

SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=rds-from-eks" \
  --query 'SecurityGroups[0].GroupId' --output text)

# Allow port 5432 from EKS pod CIDR (check your VPC CNI config)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp --port 5432 \
  --cidr 10.0.0.0/16

# Create RDS instance in private subnets
aws rds create-db-instance \
  --db-instance-identifier app-postgres \
  --db-instance-class db.r6g.large \
  --engine postgres --engine-version 16.4 \
  --master-username appadmin \
  --manage-master-user-password \
  --allocated-storage 100 --storage-type gp3 \
  --db-subnet-group-name eks-database-subnets \
  --vpc-security-group-ids $SG_ID \
  --multi-az --storage-encrypted \
  --no-publicly-accessible
```

The [`--manage-master-user-password` flag tells RDS to store the master password in AWS Secrets Manager automatically](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html). RDS generates and stores the password in Secrets Manager so you can avoid hardcoding or manually distributing it — a pattern that pairs directly with External Secrets Operator syncing credentials into Kubernetes Secrets for your Deployments.

**GCP: Cloud SQL with private IP connectivity.** Cloud SQL private IP requires allocating a VPC peering range and connecting the servicenetworking API before the instance is created; skipping this ordering forces destructive recreation later. GKE nodes in the same VPC reach Cloud SQL private IPs without NAT, keeping latency predictable for east-west traffic inside the region.

```bash
# Allocate IP range for Private Services Access
gcloud compute addresses create google-managed-services \
  --global --purpose=VPC_PEERING \
  --addresses=10.100.0.0 --prefix-length=16 \
  --network=my-vpc

# Create the private connection
gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=google-managed-services \
  --network=my-vpc

# Create Cloud SQL with private IP only
gcloud sql instances create app-postgres \
  --database-version=POSTGRES_16 \
  --tier=db-custom-4-16384 \
  --region=us-central1 \
  --network=my-vpc \
  --no-assign-ip \
  --availability-type=REGIONAL \
  --storage-type=SSD --storage-size=100GB \
  --storage-auto-increase

# Get the private IP
gcloud sql instances describe app-postgres \
  --format='value(ipAddresses.filter(type:PRIVATE).ipAddress)'
```

**Azure: Flexible Server with private access (VNet integration).** Azure Flexible Server injects the database into your VNet subnet and registers a private DNS zone so the FQDN resolves to internal addresses only. AKS pods resolve `app-postgres.privatelink.postgres.database.azure.com` the same way they resolve in-cluster Services, which keeps connection strings portable between local jump boxes and production pods.

```bash
# Create a private DNS zone for PostgreSQL
az network private-dns zone create \
  --resource-group myRG \
  --name privatelink.postgres.database.azure.com

# Link DNS zone to the VNET
az network private-dns zone vnet-link create \
  --resource-group myRG \
  --zone-name privatelink.postgres.database.azure.com \
  --name aks-link --virtual-network aks-vnet \
  --registration-enabled false

# Create Flexible Server with VNET integration
az postgres flexible-server create \
  --resource-group myRG --name app-postgres \
  --version 16 --sku-name Standard_D4ds_v5 \
  --storage-size 128 \
  --vnet aks-vnet --subnet db-subnet \
  --private-dns-zone privatelink.postgres.database.azure.com \
  --high-availability ZoneRedundant
```

**Kubernetes Service for database endpoints.** Regardless of cloud, create an ExternalName or headless Service so your application code uses a Kubernetes-native DNS name rather than embedding vendor-specific hostnames in twelve ConfigMaps spread across microservices.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: app-database
  namespace: production
spec:
  type: ExternalName
  externalName: app-postgres.abc123.us-east-1.rds.amazonaws.com
```

Your application connects to `app-database.production.svc.cluster.local`. If you migrate from RDS to Cloud SQL, you change the Service -- not every application config. Document the Service name in platform runbooks so teams never hardcode vendor hostnames in Helm values again.

---

## Connection Pooling with PgBouncer

Every database connection consumes server memory, so large numbers of idle connections waste capacity. Kubernetes makes this worse because pods scale horizontally. If you have 20 replicas, each maintaining a pool of 10 connections, that is 200 connections. During a rolling deployment, both old and new pods exist simultaneously -- suddenly 400 connections.

Managed databases have connection limits. Real performance usually degrades before you reach the configured maximum. The answer is connection pooling. Pooling is not a single knob — it is an architecture choice among sidecars, centralized Deployments, and cloud-managed proxies. That choice must align with your failover and IAM strategy.

**PgBouncer as a sidecar.** The sidecar pattern places PgBouncer in the same pod as your application so each pod maintains a small local pool that multiplexes onto shared backend connections without exposing the database to unbounded pod-level fan-out.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
  namespace: production
spec:
  replicas: 10
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
    spec:
      containers:
        - name: api
          image: mycompany/api-server:2.1.0
          ports:
            - containerPort: 8080
          env:
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: password
            - name: DATABASE_URL
              value: "postgresql://appuser:$(DB_PASSWORD)@localhost:6432/appdb?sslmode=disable"
        - name: pgbouncer
          image: bitnamilegacy/pgbouncer:1.23.0
          ports:
            - containerPort: 6432
          env:
            - name: PGBOUNCER_DATABASE
              value: appdb
            - name: POSTGRESQL_HOST
              value: app-postgres.abc123.us-east-1.rds.amazonaws.com
            - name: POSTGRESQL_PORT
              value: "5432"
            - name: POSTGRESQL_USERNAME
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: username
            - name: POSTGRESQL_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: password
            - name: PGBOUNCER_POOL_MODE
              value: transaction
            - name: PGBOUNCER_DEFAULT_POOL_SIZE
              value: "5"
            - name: PGBOUNCER_MAX_CLIENT_CONN
              value: "100"
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 128Mi
```

> **Image note:** As of 2025-08-28, Broadcom moved versioned `docker.io/bitnami/*` tags to `docker.io/bitnamilegacy/*`; this module uses `bitnamilegacy/pgbouncer:1.23.0` so labs stay pullable. The legacy registry receives **no security updates** — production should use a maintained image such as [`edoburu/pgbouncer`](https://hub.docker.com/r/edoburu/pgbouncer) or Bitnami Secure.

The sidecar `DATABASE_URL` uses `sslmode=disable` because Bitnami PgBouncer does not enable TLS on port 6432 by default; use `sslmode=require` only after you configure TLS on PgBouncer and PostgreSQL.

**PgBouncer as a centralized proxy.** For larger clusters, a centralized PgBouncer Deployment is more efficient because it amortizes pool state across hundreds of pods and gives platform engineers one place to tune `max_db_connections` in response to RDS CloudWatch `DatabaseConnections` metrics.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pgbouncer
  namespace: database
spec:
  replicas: 3
  selector:
    matchLabels:
      app: pgbouncer
  template:
    metadata:
      labels:
        app: pgbouncer
    spec:
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: pgbouncer
      containers:
        - name: pgbouncer
          image: bitnamilegacy/pgbouncer:1.23.0
          ports:
            - containerPort: 6432
          env:
            - name: PGBOUNCER_POOL_MODE
              value: transaction
            - name: PGBOUNCER_DEFAULT_POOL_SIZE
              value: "25"
            - name: PGBOUNCER_MAX_CLIENT_CONN
              value: "1000"
            - name: PGBOUNCER_MAX_DB_CONNECTIONS
              value: "150"
          readinessProbe:
            tcpSocket:
              port: 6432
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: pgbouncer
  namespace: database
spec:
  selector:
    app: pgbouncer
  ports:
    - port: 5432
      targetPort: 6432
```

**Pause and predict:** Consider a microservice where each incoming HTTP request opens and immediately closes a database connection. If you configure PgBouncer in session pooling mode, how will backend PostgreSQL connection utilization behave under heavy concurrency?

<details>
<summary>Check your prediction</summary>

Session pooling assigns a server connection for the entire client session; rapid connect and disconnect cycles do not multiplex connections onto few backends. Because PgBouncer binds a dedicated server connection to the client until that client completely terminates its socket, concurrent HTTP requests each claim an individual backend connection. Workloads with rapid connection churn will rapidly exhaust PostgreSQL connection limits under load. To achieve effective multiplexing, applications must run in transaction pooling mode so server connections return to the pool immediately after each transaction completes.
</details>

Selecting an appropriate pooling architecture requires balancing client connection volume against the specific session state requirements of the application.

**Pool mode decision matrix.** Transaction mode is the default recommendation for stateless HTTP services, but the matrix below captures why legacy session-oriented applications sometimes require session mode despite weaker multiplexing.

| Pool Mode | How It Works | Best For | Watch Out |
|-----------|-------------|----------|-----------|
| **session** | Connection assigned for entire client session | Legacy apps using PREPARE/LISTEN | Fewest pooling benefits |
| **transaction** | Connection returned after each transaction | Most web applications | Cannot use session-level features |
| **statement** | Connection returned after each statement | Simple read workloads | Breaks multi-statement transactions |

For many stateless web workloads, `transaction` mode is a strong default because it balances connection reuse with broad application compatibility.

**Managed proxies: RDS Proxy and cloud equivalents.** In-cluster PgBouncer is powerful, but each cloud also offers managed connection proxies that understand failover semantics and IAM authentication — reducing operational toil when Lambda functions or bursty Deployments threaten to exhaust `max_connections`.

[Amazon RDS Proxy](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.html) sits between your applications and RDS/Aurora, pooling and multiplexing connections while preserving sessions during Multi-AZ failover. It integrates with Secrets Manager and supports IAM authentication from clients to the proxy. RDS Proxy queues or throttles connection attempts when the pool is saturated rather than letting thousands of pods open raw PostgreSQL sessions simultaneously — the classic **thundering herd** after a cold start or deployment scale-up.

On GCP, [Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/sql-proxy) (sidecar or standalone) handles TLS and IAM-based login; for AlloyDB, the [AlloyDB Auth Proxy](https://cloud.google.com/alloydb/docs/auth-proxy/overview) plays a similar role. Azure Flexible Server supports private access patterns where connection pooling still typically lives in PgBouncer or application pools, though Hyperscale read replicas benefit from the same centralized pooler architecture.

Hypothetical scenario: an e-commerce API scales from 10 to 200 pods during a flash sale. Each pod's ORM opens 20 connections on startup. Without a proxy, 4,000 connection attempts hit PostgreSQL within seconds — exceeding limits and causing cascading timeouts. A centralized PgBouncer Deployment capped at 150 backend connections, or RDS Proxy with a configured max connections percentage, absorbs the spike while pods wait milliseconds in a queue instead of failing authentication.

```yaml
# Example: annotate pods to use RDS Proxy endpoint instead of direct RDS hostname
# Application DATABASE_URL points to the proxy endpoint in the same VPC as EKS.
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-database-config
  namespace: production
data:
  DATABASE_HOST: "my-db-proxy.proxy-abc123.us-east-1.rds.amazonaws.com"
  DATABASE_PORT: "5432"
  POOL_MODE: "transaction"
```

When choosing sidecar vs centralized vs managed proxy, consider: sidecars isolate noisy neighbors but multiply pooler memory; centralized poolers maximize multiplexing but become a shared failure domain; managed proxies add cost per hour but handle failover pinning rules and IAM integration that self-managed PgBouncer does not.

---

## Credential Rotation

Hardcoded database passwords in Kubernetes Secrets are a ticking time bomb. When you need to rotate them — and you will — you face a coordination problem. You must update the password in the database, update the Secret in Kubernetes, and restart every pod that uses it. You must do all of this without downtime. Managed rotation plus External Secrets Operator turns that manual runbook into an automated loop. Cloud services remain the source of truth while Kubernetes reflects changes on a refresh interval you control.

**External Secrets Operator (ESO) with rotation.** ESO [syncs secrets from cloud provider secret managers into Kubernetes Secrets automatically](https://github.com/external-secrets/external-secrets), which means your Deployments keep using familiar `secretKeyRef` env vars while the actual credential bytes live in Secrets Manager, Secret Manager, or Key Vault under audit logging and IAM policies.

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: db-credentials
  namespace: production
spec:
  refreshInterval: 5m
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: db-credentials
    creationPolicy: Owner
  data:
    - secretKey: username
      remoteRef:
        key: production/database/credentials
        property: username
    - secretKey: password
      remoteRef:
        key: production/database/credentials
        property: password
    - secretKey: host
      remoteRef:
        key: production/database/credentials
        property: host
```

When the secret rotates in Secrets Manager (via an AWS Lambda rotation function or equivalent), ESO picks up the new value within the `refreshInterval` window.

**Pause and predict:** How does External Secrets Operator authenticate with cloud secret managers without storing long-lived cloud credentials in Kubernetes secrets? What mechanism provides short-lived access?

<details>
<summary>Check your prediction</summary>

External Secrets Operator uses cloud workload identity rather than static IAM user access keys. The operator relies on mechanisms like AWS IRSA, EKS Pod Identity, GKE Workload Identity Federation, and Azure Entra Workload ID. Under these patterns, the cluster projects an OpenID Connect token from a Kubernetes ServiceAccount into the operator pod. The cloud provider STS endpoint verifies this token against the cluster OIDC issuer and exchanges it for temporary, short-lived cloud credentials.
</details>

Securing controller access to external cloud APIs requires establishing cryptographic trust boundaries between the Kubernetes control plane and cloud identity providers.

Pair ESO with cloud workload identity so the operator itself never stores long-lived cloud credentials. On EKS, [IRSA](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html) or [Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html) binds a Kubernetes ServiceAccount to an IAM role that can read Secrets Manager. On GKE, [Workload Identity Federation](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity) maps KSA → GSA for Secret Manager access. On AKS, [Microsoft Entra Workload ID](https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview) achieves the same keyless pattern for Key Vault. The [Secrets Store CSI Driver](https://secrets-store-csi-driver.sigs.k8s.io/) complements ESO. It mounts secrets as volumes for applications that cannot read Kubernetes Secret objects directly.

**Dual-user rotation strategy.** The safest rotation pattern uses two database users, alternating between them so one credential remains valid while pods roll onto the other during rotation windows — eliminating the race where old pods authenticate with passwords the database has already invalidated.

```mermaid
sequenceDiagram
    participant SM as Secrets Manager
    participant K8s as Kubernetes
    participant Pods as Application Pods
    participant DB as Database

    Note over DB: Time 0: user_a (active), user_b (standby)
    SM->>DB: Time 1: Rotate user_b password
    SM->>K8s: Time 2: Update Secret to point to user_b
    K8s->>Pods: Time 3: Trigger rolling restart
    Pods->>DB: Pods connect using user_b credentials
    Note over DB: Time 4: user_b (active), user_a (standby)
    SM->>DB: Time 5: Rotate user_a password (safe)
```

This ensures zero-downtime rotation because the [old credentials remain valid throughout the entire rollout](https://docs.aws.amazon.com/secretsmanager/latest/userguide/tutorials_rotation-alternating.html).

```bash
# AWS Secrets Manager rotation with dual-user strategy
aws secretsmanager rotate-secret \
  --secret-id production/database/credentials \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:123456789:function:db-rotation \
  --rotation-rules '{"AutomaticallyAfterDays": 30}'
```

**Triggering pod restarts on secret change.** Kubernetes does not remount Secrets into running containers when the Secret object updates — a behavior that surprises teams the first time ESO syncs a new password while pods continue using stale env vars until restarted.

Use [stakater/Reloader](https://github.com/stakater/Reloader) to automatically trigger rolling restarts:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
  annotations:
    reloader.stakater.com/auto: "true"
spec:
  # ... Reloader watches for Secret changes and triggers rolling updates
```

---

## Schema Migrations in GitOps

Running `ALTER TABLE` in production is nerve-wracking enough. Doing it automatically through a GitOps pipeline requires careful design. You must avoid breaking running applications during rollouts. Kubernetes intentionally runs old and new code simultaneously. That is the exact condition that makes breaking DDL dangerous if you treat schema and binary as one atomic change.

**The expand-contract pattern.** Avoid making breaking schema changes in a single step; instead, treat schema evolution like API versioning where multiple contract versions must coexist for the duration of a Deployment rollout.

```mermaid
flowchart LR
    P1["Phase 1: EXPAND<br/>(Add new column)"] --> P2["Phase 2: MIGRATE<br/>(Write to both)"]
    P2 --> P3["Phase 3: CONTRACT<br/>(Remove old column)"]
```

| Phase | Database Schema | Application Behavior |
| :--- | :--- | :--- |
| **1: EXPAND** | `[ id | name | email ]` (email is NEW, nullable) | App v1: Writes `[name]` |
| **2: MIGRATE** | `[ id | name | email ]`<br>*(Backfill script populates email)* | App v2: Writes both<br>Reads `[email]` |
| **3: CONTRACT**| `[ id | email ]`<br>*(name column dropped)* | App v3: Writes `[email]` |

**Pause and predict:** Why is running database schema migrations inside an application Deployment initContainer dangerous when replica counts fluctuate? What happens during a rapid horizontal scale event?

<details>
<summary>Check your prediction</summary>

Init containers run on every Pod replica during startup rather than once per application rollout. If a Deployment scales from two to ten replicas, ten init containers launch simultaneously and attempt concurrent migrations against the same tables. These parallel executions cause table lock contention, schema deadlocks, and migration failure. Production pipelines should always execute migrations through a dedicated Kubernetes Job that guarantees single-run execution before deploying application pods.
</details>

Automating schema updates safely within continuous delivery workflows requires isolating database modification tasks from horizontal pod autoscaling and rolling update lifecycles.

**Kubernetes Job for migrations.** A dedicated Job guarantees exactly one migration attempt per sync wave regardless of how many replicas your Deployment scales to during a rollout or load spike.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate-v42
  namespace: production
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: migrate
          image: mycompany/api-server:2.1.0
          command: ["./migrate", "--direction=up", "--steps=1"]
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: connection-string
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
      serviceAccountName: db-migrator
```

The [`argocd.argoproj.io/hook: PreSync` annotation tells Argo CD to run this Job before deploying new application pods](https://argo-cd.readthedocs.io/en/latest/user-guide/sync-waves/). The migration runs, the schema updates, then the new application version rolls out — preserving the invariant that the database schema is always compatible with the next wave of pods about to start.

**Migration safety checklist.** These rules apply equally whether the database runs under RDS, Cloud SQL, or an in-cluster operator; GitOps does not remove the need for lock timeouts and backward-compatible DDL.

| Rule | Reason |
|------|--------|
| Avoid dropping columns in the same release that removes their usage | Old pods still running during rollout can crash |
| Add columns as nullable or with defaults in rolling deployments | INSERT statements from old code won't fail |
| Use advisory locks in migration scripts | Prevents two migration Jobs from running simultaneously |
| Set a statement timeout | A long-running `ALTER TABLE` lock can block queries until the lock is released |
| Test rollback before applying | `migrate down` should work for the rollback path you expect to use |

```sql
-- Safe migration example: timeouts apply to ALTER TABLE, not index builds
SET lock_timeout = '5s';
SET statement_timeout = '30s';

ALTER TABLE orders ADD COLUMN shipping_method VARCHAR(50) DEFAULT 'standard';
```

Run `CREATE INDEX CONCURRENTLY` as its own statement **outside** the `statement_timeout` scope above — concurrent index builds routinely exceed 30s and would be aborted, and `CONCURRENTLY` cannot run inside a transaction block.

```sql
CREATE INDEX CONCURRENTLY idx_orders_shipping ON orders(shipping_method);
```

---

## High Availability, Disaster Recovery, and Read Replicas

Understanding HA primitives precisely prevents expensive mistakes. Multi-AZ is about synchronous durability and automatic failover within a region. Read replicas scale reads asynchronously. Global or geo features address regional DR and latency. These capabilities are complementary, not interchangeable. Kubernetes does not heal applications that cache DNS forever. It also does not fix clients that open connections without TCP keepalive probes. HA design must include client retry semantics and observability, not just a checkbox on the RDS console.

**Multi-AZ vs read replicas vs global topologies.** Teams frequently conflate these features because all three appear under "high availability" marketing pages, yet each solves a different failure mode with different RPO/RTO and billing implications.

**Multi-AZ (same region):** AWS RDS Multi-AZ maintains a synchronous standby; writes commit on the primary before acknowledgment, and failover promotes the standby with an endpoint DNS update. GCP Cloud SQL **regional** instances keep a standby in another zone. Azure Flexible Server **zone-redundant HA** places primary and standby in different zones. RPO for these patterns is effectively zero for uncommitted transactions already acknowledged, and RTO is typically one to two minutes — but application connection pools must retry through DNS TTL caching (see Quiz question 4).

**Read replicas (async):** Replicas lag the primary by seconds (or more under load). They scale read traffic and can serve DR after promotion, but they are not automatic failover targets unless you configure tools or runbooks. AWS RDS read replica endpoints (`-ro` suffix on cluster endpoints for Aurora), Cloud SQL read replicas, and Azure geo-replicas each expose separate hostnames — map them to `db-read` Services in Kubernetes.

**Cross-region global:** [Aurora Global Database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html) replicates to up to 10 secondary regions with sub-second typical lag; [Cloud SQL cross-region replicas](https://cloud.google.com/sql/docs/postgres/replication/cross-region-replicas) support migration and DR; [Azure Flexible Server geo-replication](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-read-replicas-geo) provides read-only secondaries in paired regions. Regional loss requires explicit failover/switchover — test these runbooks quarterly with game days that measure how long your Kubernetes Deployments take to resume writes after DNS and connection pool drains complete.

**Backups, PITR, and snapshots.** Automated backups plus PITR let you rewind to a timestamp before a bad migration — essential when a PreSync Job applies the wrong DDL. RDS and Cloud SQL retain backup windows and transaction logs; Azure Flexible Server offers PITR with configurable retention. Snapshots are user-initiated full copies for long-lived baselines or cross-account cloning. Backup storage often accrues cost separately from instance compute — verify retention policies so seven-year compliance requirements do not silently triple your storage bill while old snapshots linger after cluster teardown.

**Multi-AZ architecture comparison.** The table below summarizes failover behavior differences that directly affect how you configure Kubernetes Services and application retry logic.

All three clouds support Multi-AZ deployments for managed databases. The failover mechanics differ:

| Feature | AWS RDS Multi-AZ | GCP Cloud SQL Regional | Azure Flexible Server ZR |
|---------|-------------------|------------------------|--------------------------|
| Failover time | 60-120 seconds | ~60 seconds | 60-120 seconds |
| Read from standby | [No (Multi-AZ), Yes (Multi-AZ Cluster)](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html) | No | No |
| Cross-region | Separate feature (Read Replicas) | [Cross-region replicas](https://cloud.google.com/sql/docs/postgres/replication/cross-region-replicas) | [Geo-replication](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-read-replicas-geo) |
| Endpoint changes on failover | No (DNS CNAME updated) | No (IP stays same) | No (DNS updated) |

**Read replica routing in Kubernetes.** Create separate Services for read and write traffic so your application layer can enforce consistency rules in code rather than hoping a single DSN magically routes SELECTs to replicas without lag awareness.

```yaml
# Write endpoint (primary)
apiVersion: v1
kind: Service
metadata:
  name: db-write
  namespace: production
spec:
  type: ExternalName
  externalName: app-postgres.abc123.us-east-1.rds.amazonaws.com
---
# Read endpoint (replicas)
apiVersion: v1
kind: Service
metadata:
  name: db-read
  namespace: production
spec:
  type: ExternalName
  externalName: app-postgres-ro.abc123.us-east-1.rds.amazonaws.com
```

Your application then uses two connection strings. The write Service targets the primary endpoint. The read Service targets replica endpoints when lag is acceptable.

```python
# Application configuration
WRITE_DB = "postgresql://user:pass@db-write.production.svc:5432/appdb"
READ_DB = "postgresql://user:pass@db-read.production.svc:5432/appdb"
```

Instrument replica lag before trusting read Services for user-facing queries. CloudWatch `ReplicaLag`, Cloud SQL replication status metrics, and Azure `pg_stat_replication` views can gate read routing. Disable read routing when lag exceeds your business tolerance — often one to five seconds for dashboards, zero for account balances.

**Cross-AZ traffic costs.** This catches many teams off guard because intra-region traffic feels "local" until the finance dashboard shows bilateral per-GB charges on a chatty ORM.

- **AWS**: [$0.01/GB per direction between AZs](https://aws.amazon.com/blogs/networking-and-content-delivery/optimizing-data-transfer-costs-when-using-aws-network-load-balancer/)
- **GCP**: [$0.01/GB between zones in the same region](https://cloud.google.com/vpc/pricing)
- **Azure**: [Free within the same region](https://azure.microsoft.com/en-us/pricing/details/bandwidth) (as of 2025)

If your application in AZ-a talks to a database in AZ-b, every query and response crosses AZ boundaries. For a chatty application doing 10,000 queries per second, each returning 1 KB, that is roughly 864 GB/day -- about $17/day just in cross-AZ transfer.

**Mitigation strategies:**
1. Use topology-aware routing to prefer same-AZ replicas
2. Use connection pooling to reduce round-trips
3. Batch reads where possible
4. Cache frequently-accessed data (see Module 9.5)

---

## Kubernetes Integration: Managed Services vs In-Cluster Operators

Running PostgreSQL inside the cluster with [CloudNativePG](https://cloudnative-pg.io/) or the [Zalando Postgres operator](https://github.com/zalando/postgres-operator) gives you GitOps-native manifests, custom extensions, and no per-vCPU cloud markup — but you inherit backup scheduling, failover testing, storage class tuning, and version upgrades. Managed databases invert that trade: higher monthly cost, lower operational surface area.

Use managed when: your team lacks dedicated DBA capacity, compliance requires vendor-backed SLAs, you need cross-region HA without building it, or connection limits and patching cadence must be someone else's job. Use in-cluster operators when: you need specific extensions (PostGIS custom builds, logical decoding for CDC you control), air-gapped environments prohibit managed endpoints, or unit economics at sustained high throughput favor owned hardware over per-hour RDS charges.

Access patterns from pods should always prefer private networking plus workload identity. Static username/password Secrets in etcd are acceptable for labs; production paths flow through External Secrets Operator syncing from Secrets Manager / Secret Manager / Key Vault, with database IAM authentication where supported (RDS IAM auth, Cloud SQL IAM login). NetworkPolicies restricting egress to database CIDRs and security groups allowing only node/pod CIDRs complete the zero-trust picture — the database never accepts `0.0.0.0/0`.

For schema and data migrations, treat the managed endpoint like any external dependency: Jobs with PreSync hooks, expand-contract DDL, and advisory locks. Operators running inside the cluster do not remove migration discipline; they only colocate the process.

---

## Cost Lens for Managed Databases

Managed database bills combine compute shape, storage, I/O, replication, backup retention, and network egress. Kubernetes autoscaling can amplify those charges if every new pod opens uncapped connections or runs chatty cross-AZ queries. Right-size from metrics, not from peak load-test fantasies.

**Compute pricing models:** Provisioned instances (RDS `db.r6g.large`, Cloud SQL custom tier, Azure vCore) charge hourly whether or not queries run — simple to forecast but easy to over-provision "just in case." Serverless or autoscaling options ([Aurora Serverless v2 ACUs](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.how-it-works.html), DynamoDB on-demand, Cosmos DB serverless) shift cost toward usage but can spike during traffic bursts if minimum capacity floors are set too high. Right-size by observing CPU, freeable memory, and connection counts over a full business cycle, not just load-test peaks.

**Storage and IOPS:** General-purpose SSD (gp3 on RDS, SSD on Cloud SQL) suits most OLTP; provisioned IOPS tiers matter when random write latency dominates. Storage grows monotonically unless you archive — autopilot/auto-increase features prevent fullness outages but not budget surprises. Cross-AZ synchronous replication (Multi-AZ) duplicates write I/O internally; you pay compute for the standby but not double storage in all engines — verify your provider's billing FAQ.

**Replication and DR surcharges:** Read replicas bill as additional instances; cross-region replication adds inter-region egress (often ~$0.02/GB on AWS between regions — verify current rates). Aurora Global Database and Cosmos DB multi-region writes trade dollars for RTO/RPO improvements. Keep DR replicas in the minimum regions compliance requires, not "every region we might expand to someday."

**Backup and PITR storage:** Retained automated backups and manual snapshots persist after instance deletion unless lifecycle policies delete them — a common source of orphaned charges after tearing down lab clusters.

**Kubernetes-specific cost amplifiers:** Cross-AZ query chatter (quantified earlier), connection storms forcing larger instance sizes, and idle Dev clusters left running Multi-AZ production tiers over weekends. Mitigations: topology-aware routing, pooling/proxy layers, scheduled scale-down for non-prod namespaces, and separate smaller instances for preview environments.

| Cost driver | What spikes the bill | Mitigation |
|-------------|---------------------|------------|
| Over-provisioned instance class | Always-on headroom "for peak" | Use autoscaling/serverless tiers; right-size from metrics |
| Uncapped pod connections | ORM default pool × replica count | PgBouncer, RDS Proxy, lower per-pod pool sizes |
| Cross-AZ / cross-region traffic | Pods and DB in different zones/regions | Co-locate or use regional endpoints + replicas |
| Long backup retention | Compliance defaults on all envs | Tier retention: 7 days non-prod, 35+ prod |
| Idle Multi-AZ standby | Dev databases with production HA | Single-AZ for dev; Multi-AZ only where RTO demands |

---

## Patterns & Anti-Patterns

Production teams that integrate Kubernetes with managed databases converge on a small set of patterns — and repeat the same anti-patterns during their first migration.

| Pattern | When to Use | Why It Works | Scaling Consideration |
|---------|-------------|--------------|------------------------|
| ExternalName / headless Service indirection | Any managed DB accessed from many Deployments | Swap endpoints without redeploying every microservice | Document DNS TTL behavior during failover drills |
| Centralized PgBouncer or RDS Proxy | >20 pod replicas or serverless burst traffic | Multiplexes thousands of client sessions onto tens of DB connections | Run pooler replicas with topology spread across zones |
| Dual-user rotation with ESO + Reloader | Compliance-mandated password rotation | Old and new credentials valid during rolling restart | Automate rotation Lambda / cloud-native rotators |
| Expand-contract migrations via PreSync Job | GitOps-deployed schema changes | Old and new app versions coexist during rollout | Never retry failed migrations automatically (`backoffLimit: 0`) |
| Read/write Service split | Read-heavy APIs with async replicas | Offloads SELECT traffic from primary | Monitor replica lag before routing critical reads |

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Public database IP "temporarily" for debugging | Credential stuffing, data exfiltration | `kubectl port-forward` through a bastion pod; private IP only |
| One giant shared database for all microservices | Blast radius, noisy neighbor schema locks | Database per bounded context; shared only when truly coupled |
| ORM pool size × replica count without math | Hits `max_connections`, sudden outages | Calculate max backend connections; enforce via proxy |
| Running migrations in app startup / initContainer | N replicas ⇒ N concurrent DDL attempts | Single PreSync Job with advisory locks |
| Treating read replica as strongly consistent | Stale reads, double-spend bugs | Route only latency-tolerant reads; use primary for auth/billing |
| Choosing Cosmos conflict policy after launch | Immutable policy locks wrong merge semantics | Design active-active conflict handling at container creation |
| Skipping failover drills | Multi-AZ confidence without measured RTO | Quarterly forced failover tests with connection retry metrics |

---

## Decision Framework

Choosing a managed database is a requirements exercise, not a brand loyalty exercise. Start from access patterns, consistency needs, and operational capacity — then map to engine and cloud.

```mermaid
flowchart TD
    Start[New data store for K8s workload] --> ACID{Need multi-row ACID transactions?}
    ACID -- Yes --> SQL{Scale beyond single primary?}
    SQL -- No --> Relational[RDS / Cloud SQL / Flexible Server]
    SQL -- Yes --> Global{Global low-latency writes?}
    Global -- Yes --> SpannerOrCosmos[Spanner or Cosmos DB strong/multi-master]
    Global -- No --> AuroraOrHyperscale[Aurora / Hyperscale / read replicas]
    ACID -- No --> Access{Primary access pattern?}
    Access -- Key-value / session --> KV[DynamoDB / Cosmos DB / Firestore]
    Access -- Wide-column throughput --> Wide[Bigtable / Cassandra API]
    Access -- Cache --> CacheModule[Module 9.5: ElastiCache / Memorystore]
    Relational --> K8sIntegrate[Private VPC + pooler + ESO + workload identity]
    KV --> K8sIntegrate
```

| Requirement | Prefer | Avoid |
|-------------|--------|-------|
| Complex joins + FK constraints | PostgreSQL-compatible managed (RDS, Cloud SQL, Flexible Server) | DynamoDB without denormalization plan |
| Global external consistency | Cloud Spanner | Single-region RDS with app-level sync |
| Active-active multi-region writes | Cosmos DB multi-region / DynamoDB global tables | Standard async read replica as write target |
| Minimal ops, moderate scale | Managed relational + RDS Proxy/PgBouncer | Self-managed StatefulSet without DBA team |
| Strict air-gap / custom extensions | In-cluster operator (CloudNativePG) | Public managed endpoint dependency |
| Unpredictable spikey traffic | Aurora Serverless v2 / DynamoDB on-demand | Oversized fixed instance running 24/7 |
| Existing Microsoft stack + .NET ORM | Azure SQL Hyperscale / Flexible Server | Forcing cross-cloud egress to AWS |

Before committing, prototype three measurements from a representative Kubernetes Deployment. Measure p95 query latency through private networking. Count connections at max replica count. Estimate monthly cost at 50%, 100%, and 150% of expected load. If the prototype cannot survive a simulated AZ failover within your RTO target, fix networking and pool retry logic before production traffic — not during an outage.

---

## Observability and Resilience from Kubernetes

Connecting pods to a managed database is only half the integration. The other half is knowing when connections fail silently, when replica lag makes your read Service lie, and when pool exhaustion precedes user-visible errors. Treat database connectivity as a first-class SLO alongside HTTP latency. Kubernetes control plane health can look green while every pod logs `FATAL: too many connections`.

**Metrics that matter.** Export application-level database pool stats (active, idle, waiting clients) via Prometheus client libraries or sidecar exporters. Complement them with cloud metrics: RDS `DatabaseConnections`, `CPUUtilization`, and `FreeableMemory`; Cloud SQL `database/network/connections`; Azure Flexible Server `connections_failed` and `cpu_percent`. Alert on connection count approaching `max_connections` × 0.8, not at 100%. Recovery requires draining pools while traffic continues. Track PgBouncer `cl_waiting` or RDS Proxy queued client metrics to catch thundering herds during rollouts.

**Logs and traces.** Enable slow query logs on the managed instance with thresholds aligned to your p95 SLO (often 200–500 ms for OLTP). Correlate Kubernetes pod names in application logs using the downward API `metadata.name` field. That helps trace which Deployment version issued expensive queries. OpenTelemetry database spans should include `db.system`, `server.address`, and pool wait time — not just statement text. On-call engineers can then distinguish network blips from missing indexes.

**Failover testing from pods.** Schedule quarterly tests that run inside the cluster. A Job executes `aws rds reboot-db-instance --force-failover` (or cloud equivalent). A concurrent Deployment hammers the database Service with retry-enabled clients. Measure time-to-recovery at the application layer, not just RDS console "available" status. Configure connection pools with `maxLifetime` and `idleTimeout` shorter than typical DNS TTL mismatches. Stale connections recycle after Multi-AZ promotion.

**NetworkPolicy and egress observability.** Even private databases benefit from explicit NetworkPolicies allowing egress only to database CIDRs and DNS. VPC Flow Logs on AWS and GCP, plus NSG flow logs on Azure, reveal unexpected cross-AZ chatter before the finance team does. When flow logs show pod CIDRs talking to database subnets on high port counts, you likely have connection leaks. ORMs that skip pool drain on SIGTERM during short preStop hooks are a common culprit.

Hypothetical scenario: monitoring shows HTTP 200 responses but checkout success rate drops 3%. Database CPU is flat, yet RDS `DatabaseConnections` stair-steps upward each time HPA adds pods. Root cause: each new pod opens 30 connections on startup without a pooler. preStop does not drain the pool before SIGKILL. Fix: centralized PgBouncer with `terminationGracePeriodSeconds` aligned to pool drain time. Add HPA stabilization windows so connection count ramps smoothly instead of in spikes. Export a Grafana panel that overlays pod replica count and active DB connections. That makes this failure mode obvious before customers notice checkout errors.

---

## Did You Know?

1. **[Amazon Aurora Global Database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html) supports up to 10 secondary read-only clusters in different AWS Regions**, with dedicated replication infrastructure that typically keeps lag under one second — enabling regional DR without rebuilding your Kubernetes manifests per region.

2. **PostgreSQL connection capacity is constrained by server memory and per-connection process overhead**, so practical limits are often lower than the largest `max_connections` value you can configure — which is why RDS documents connection limits per instance class and recommends proxies for serverless-style burst clients.

3. **[Cloud Spanner's external consistency](https://cloud.google.com/spanner/docs/true-time-external-consistency) uses TrueTime to order transactions globally**, so a read after a committed write never observes a state where the write "hasn't happened yet" — stronger than default eventual consistency in many globally distributed stores.

4. **Azure Cosmos DB conflict resolution policy cannot be changed after container creation**, so multi-region active-active Kubernetes workloads must choose last-writer-wins or custom merge logic at design time — not after discovering duplicate-key production incidents.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|---------------|---------------|
| Exposing the database with a public IP "for debugging" | Developers need to query from laptops | Use `kubectl port-forward` to a pod with database access |
| Not setting `volumeBindingMode: WaitForFirstConsumer` when self-hosting | [Default StorageClass creates volumes immediately](https://kubernetes.io/docs/concepts/storage/storage-classes/) | Does not apply to managed DBs, but remember for dev environments |
| Allowing unlimited connections from pods | No connection pooling configured | Deploy PgBouncer (sidecar or centralized) with explicit limits |
| Storing database passwords in ConfigMaps | Confusion between ConfigMap and Secret | Use Secrets, and preferably ESO with a cloud secret manager |
| Running migrations in application startup code | Seems convenient -- every pod migrates on boot | Use a dedicated Job (PreSync hook) so migration runs exactly once |
| Ignoring cross-AZ data transfer costs | Not visible until the bill arrives | Monitor with VPC Flow Logs and use topology-aware routing |
| Using `session` pool mode in PgBouncer by default | It is the default setting | Explicitly set `transaction` mode for web workloads |
| Not testing database failover | "Multi-AZ handles it" | Schedule quarterly failover tests using [`aws rds reboot-db-instance --force-failover`](https://docs.aws.amazon.com/cli/v1/reference/rds/reboot-db-instance.html) |

---

## Quiz

<details>
<summary>1. Your team is migrating a legacy application to Kubernetes. The application currently hardcodes the RDS endpoint `prod-db.abc123.us-east-1.rds.amazonaws.com` in its configuration files. You suggest creating a Kubernetes Service to represent the database instead. If the database is still hosted in RDS, how does introducing a Kubernetes Service improve the architecture, and what specific type of Service should you use?</summary>

An ExternalName Service provides a layer of indirection, decoupling the application's configuration from the physical database location. By using an ExternalName Service, the application connects to a stable internal DNS name like `db-write.production.svc.cluster.local`. If you need to migrate the database, promote a read replica to primary, or switch to a different cloud provider, you only update the Service definition once. The application pods do not need to be reconfigured or restarted, minimizing risk and operational overhead during database maintenance.
</details>

<details>
<summary>2. A high-traffic e-commerce API is experiencing latency spikes. You notice the PostgreSQL database is hitting its maximum connection limit. The API is written in Go and opens a connection, runs a quick SELECT query, and closes it for every request. You deploy PgBouncer, but the database connection count doesn't drop significantly. You realize PgBouncer is using `session` mode. Why did `session` mode fail to solve the problem, and how would switching to `transaction` mode fix it?</summary>

In `session` mode, PgBouncer assigns a backend server connection to a client for the entire duration of the client's session. Because the Go API opens and closes connections rapidly, each request ties up a backend connection, providing minimal pooling benefits. Switching to `transaction` mode resolves this by returning the backend connection to the pool immediately after each transaction completes. This allows PgBouncer to multiplex thousands of brief client transactions over a small, stable pool of backend database connections, drastically reducing memory overhead and connection churn on the PostgreSQL server.
</details>

<details>
<summary>3. Your team needs to rename the `user_status` column to `account_state` in the primary database. The lead developer plans to run `ALTER TABLE users RENAME COLUMN user_status TO account_state;` during the next Argo CD sync. You block the PR, explaining that this will cause an outage during the rolling deployment. Why will a simple rename cause an outage in Kubernetes, and how should the team apply the expand-contract pattern to execute this change safely?</summary>

A simple rename causes an outage because Kubernetes rolling deployments run old and new pod versions simultaneously. The older pods still running during the rollout will attempt to query the `user_status` column, which no longer exists, causing them to fail as soon as they hit that code path. The expand-contract pattern solves this by breaking the change into additive phases, starting with expanding the schema to include the new `account_state` column. Next, you deploy application code that writes to both columns, and finally, once all pods are updated and data is backfilled, you contract by removing the old `user_status` column. This incremental approach ensures every version of the application can safely interact with the database schema at any given moment.
</details>

<details>
<summary>4. At 3:00 AM, the primary RDS instance in `us-east-1a` suffers a hardware failure. The database is configured for Multi-AZ, and a standby exists in `us-east-1b`. The failover completes in 60 seconds, but your Kubernetes pods continue throwing connection errors for 5 minutes before recovering. Assuming the pods are using an ExternalName Service pointing to the RDS endpoint, what caused this extended downtime, and how does Kubernetes eventually resolve the connection?</summary>

During an RDS Multi-AZ failover, AWS promotes the standby instance and updates the DNS CNAME record of the database endpoint to point to the new primary's IP address. However, Kubernetes pods and nodes often cache DNS lookups based on the Time-To-Live (TTL) of the record. The extended downtime occurs because the pods continue sending traffic to the old, dead IP address until their local DNS cache expires. Once the TTL expires, the pods re-resolve the ExternalName Service, receive the new IP address of the promoted instance, and successfully re-establish their database connections.
</details>

<details>
<summary>5. Your monthly cloud bill shows a massive spike in "Cross-AZ Data Transfer" costs. Your EKS nodes are spread across `us-west-2a`, `2b`, and `2c`, while your RDS instance is primarily in `us-west-2a`. The application makes thousands of small queries per second. Why is this architecture generating data transfer charges, and what are two architectural changes you could make to reduce this specific line item on the bill?</summary>

Cloud providers charge for data transfer that crosses Availability Zone boundaries, even within the same region. Because your pods are distributed across three AZs but the database is in one, roughly two-thirds of your application queries and their corresponding result sets are crossing AZ boundaries, incurring bilateral charges. To reduce this cost, you can implement topology-aware routing to force pods to prefer reading from a read replica in their local AZ. Alternatively, you can implement connection pooling or application-level caching to drastically reduce the total volume of round-trips made to the database.
</details>

<details>
<summary>6. A developer notices that a database migration Job deployed via an Argo CD PreSync hook occasionally fails due to a timeout. To ensure the deployment eventually succeeds, they propose changing the Job's `backoffLimit` from `0` to `3`. You reject this change. What is the danger of automatically retrying a failed database migration Job, and why is failing the entire deployment process the safer alternative?</summary>

Automatically retrying a database migration Job is dangerous because migrations are rarely idempotent by default. If a migration script fails halfway through—for example, it successfully creates a table but times out creating an index—retrying the Job will cause it to attempt creating the table again, resulting in a fatal error that requires manual database surgery to fix. By keeping `backoffLimit: 0`, a failure immediately stops the Argo CD sync process. This fail-fast behavior preserves the state of the database and forces an engineer to investigate the partial migration, manually rectify the schema, and safely resume the deployment.
</details>

<details>
<summary>7. Your security team mandates that database passwords be rotated every 30 days. You write a script that updates the password in RDS, then updates the Kubernetes Secret, and finally triggers a rolling restart of the application Deployments. During the next rotation, the application experiences 45 seconds of downtime where database authentication fails. How would implementing a dual-user rotation strategy eliminate this downtime window?</summary>

The downtime occurs because there is an unavoidable race condition: old pods still running during the rolling restart have the old password, but the database only accepts the new password. The dual-user rotation strategy eliminates this by maintaining two active database users. When rotation occurs, you change the password of the standby user, update Kubernetes to use the standby user, and trigger the rolling restart. Because the original user's password remains unchanged during the rollout, the old pods continue to function while the new pods connect using the newly rotated credentials.
</details>

---

## Hands-On Exercise: Connect Kind Cluster to Local PostgreSQL

Since managed databases require cloud accounts, this exercise simulates the architecture locally using Docker and kind. You will practice the same patterns production uses — headless Services, centralized PgBouncer, migration Jobs, read/write endpoint split, and credential rotation — without provisioning RDS or Cloud SQL. Complete all six tasks in order; each builds on the previous networking and pooling setup.

**Task 1 — Create an ExternalName Service.** Your first objective is to create a Kubernetes Service that points to the PostgreSQL container. Because ExternalName requires a DNS hostname rather than a raw IP, the lab uses a headless Service with manually maintained Endpoints — the same indirection pattern you use when wrapping RDS endpoints behind in-cluster DNS.

### Setup

```bash
alias k=kubectl

# Create a Docker network shared between kind and PostgreSQL
docker network create db-lab

# Start PostgreSQL in Docker
docker run -d --name lab-postgres \
  --network db-lab \
  -e POSTGRES_USER=appadmin \
  -e POSTGRES_PASSWORD=lab-secret-123 \
  -e POSTGRES_DB=appdb \
  -p 5432:5432 \
  postgres:16

# Create a kind cluster attached to the same Docker network
cat > /tmp/kind-db-lab.yaml << 'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
EOF

kind create cluster --name db-lab --config /tmp/kind-db-lab.yaml

# Connect kind nodes to the db-lab network
docker network connect db-lab db-lab-control-plane
docker network connect db-lab db-lab-worker
docker network connect db-lab db-lab-worker2

# Get PostgreSQL's IP on the db-lab network
PG_IP=$(docker inspect lab-postgres \
  --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' | head -1)
echo "PostgreSQL IP: $PG_IP"
```

<details>
<summary>Task 1 Solution</summary>

Since ExternalName requires a DNS name (not an IP), use a headless Service with Endpoints:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: app-database
  namespace: default
spec:
  clusterIP: None
  ports:
    - port: 5432
      targetPort: 5432
---
apiVersion: v1
kind: Endpoints
metadata:
  name: app-database
  namespace: default
subsets:
  - addresses:
      - ip: "${PG_IP}"   # Replace with actual IP from setup
    ports:
      - port: 5432
```

```bash
# Save the YAML above as /tmp/db-service.yaml, then apply (replace PG_IP with actual value)
sed "s/\${PG_IP}/$PG_IP/" /tmp/db-service.yaml | k apply -f -
```
</details>

**Task 2 — Deploy PgBouncer as a centralized proxy.** Deploy a PgBouncer Deployment with two replicas and a ClusterIP Service in front of it. Centralized pooling mirrors the production pattern where platform teams operate shared database infrastructure while application teams consume a stable cluster DNS name.

<details>
<summary>Task 2 Solution</summary>

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
stringData:
  username: appadmin
  password: lab-secret-123
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pgbouncer
spec:
  replicas: 2
  selector:
    matchLabels:
      app: pgbouncer
  template:
    metadata:
      labels:
        app: pgbouncer
    spec:
      containers:
        - name: pgbouncer
          image: bitnamilegacy/pgbouncer:1.23.0
          ports:
            - containerPort: 6432
          env:
            - name: PGBOUNCER_DATABASE
              value: appdb
            - name: POSTGRESQL_HOST
              value: app-database
            - name: POSTGRESQL_PORT
              value: "5432"
            - name: POSTGRESQL_USERNAME
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: username
            - name: POSTGRESQL_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: password
            - name: PGBOUNCER_POOL_MODE
              value: transaction
            - name: PGBOUNCER_DEFAULT_POOL_SIZE
              value: "10"
          readinessProbe:
            tcpSocket:
              port: 6432
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: pgbouncer
spec:
  selector:
    app: pgbouncer
  ports:
    - port: 5432
      targetPort: 6432
```

```bash
k apply -f /tmp/pgbouncer.yaml
k wait --for=condition=ready pod -l app=pgbouncer --timeout=60s
```
</details>

**Task 3 — Test connectivity through PgBouncer.** Run a test pod that connects through PgBouncer and creates a table. Verify that the pooler forwards authentication to PostgreSQL and that connection counts on the database stay low even when multiple clients connect through the proxy Service.

<details>
<summary>Task 3 Solution</summary>

```bash
k run db-test --rm -it --image=postgres:16 --restart=Never -- \
  psql "postgresql://appadmin:lab-secret-123@pgbouncer:5432/appdb" \
  -c "CREATE TABLE test_connection (id serial PRIMARY KEY, created_at timestamp DEFAULT now());
      INSERT INTO test_connection DEFAULT VALUES;
      SELECT * FROM test_connection;"
```
</details>

**Task 4 — Simulate a schema migration Job.** Create a Kubernetes Job that runs a migration script with `backoffLimit: 0`, matching the GitOps PreSync pattern from earlier in this module. The Job should create schema objects idempotently where possible so repeated lab runs do not fail on `already exists` errors.

<details>
<summary>Task 4 Solution</summary>

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: migration-v1
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: migrate
          image: postgres:16
          command:
            - psql
            - "postgresql://appadmin:lab-secret-123@pgbouncer:5432/appdb"
            - -c
            - |
              BEGIN;
              SET lock_timeout = '5s';
              CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                name VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW()
              );
              INSERT INTO users (email, name) VALUES
                ('alice@example.com', 'Alice'),
                ('bob@example.com', 'Bob');
              COMMIT;
```

```bash
k apply -f /tmp/migration-job.yaml
k wait --for=condition=complete job/migration-v1 --timeout=30s
k logs job/migration-v1
```
</details>

**Task 5 — Verify read/write split.** Create a second endpoint Service simulating a read replica and test routing. In production this maps to separate `db-read` and `db-write` Services backed by different managed endpoints; here both point at the same PostgreSQL instance so you focus on DNS wiring rather than replication lag.

<details>
<summary>Task 5 Solution</summary>

```bash
# Create read-only Service (same PostgreSQL in this lab, but separate Service)
cat <<'EOF' | k apply -f -
apiVersion: v1
kind: Service
metadata:
  name: db-read
spec:
  clusterIP: None
  ports:
    - port: 5432
EOF

# Create Endpoints pointing to same PG (simulating a read replica)
cat <<EOF | k apply -f -
apiVersion: v1
kind: Endpoints
metadata:
  name: db-read
subsets:
  - addresses:
      - ip: "$PG_IP"
    ports:
      - port: 5432
EOF

# Test reading from the "replica"
k run read-test --rm -it --image=postgres:16 --restart=Never -- \
  psql "postgresql://appadmin:lab-secret-123@db-read:5432/appdb" \
  -c "SELECT * FROM users;"
```
</details>

**Task 6 — Simulate credential rotation.** Implement a manual credential rotation to observe how workloads behave when Secrets change. Kubernetes does not hot-reload Secret env vars; you will see why Reloader or explicit rollouts are mandatory in production rotation runbooks.

<details>
<summary>Task 6 Solution</summary>

```bash
# 1. Create a dummy Deployment using the secret
cat <<EOF | k apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-worker
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api-worker
  template:
    metadata:
      labels:
        app: api-worker
    spec:
      containers:
        - name: worker
          image: postgres:16
          command: ["sleep", "3600"]
          env:
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: password
EOF

k wait --for=condition=available deployment/api-worker --timeout=30s

# 2. Update the secret in Kubernetes (simulating an external rotation)
k create secret generic db-credentials \
  --from-literal=username=appadmin \
  --from-literal=password=new-rotated-secret-456 \
  --dry-run=client -o yaml | k apply -f -

# 3. Notice the pod doesn't automatically get the new password
# In a real environment, you need Reloader to trigger this automatically
k rollout restart deployment api-worker
k rollout status deployment api-worker

# 4. Verify the new pod has the new password
k exec deploy/api-worker -- env | grep DB_PASSWORD
```
</details>

Before you close the hands-on lab, audit the four operational claims below. Each open card states a hypothesis that sounds operationally plausible during managed database integrations and Kubernetes cloud architectures. Treat the claim as a prediction, then open the details only after you have an answer.

**Card A: Cross-AZ queries to RDS inside a VPC are free because the traffic never leaves AWS.** An infrastructure engineering team provisions an Amazon EKS cluster across three availability zones and connects application pods to an Amazon RDS PostgreSQL instance in a dedicated private subnet. Because all network traffic stays within the boundaries of a single virtual private cloud, the team assumes queries are completely free. They believe cross-zone traffic costs apply only to public internet egress or NAT gateways.

<details>
<summary>Check your prediction</summary>

Failure layer: VPC network billing and inter-zone transit metering. Next action: recognize that cross-AZ private traffic is still billed data transfer, whereas only same-AZ private IP communication incurs zero inter-zone bandwidth fees; major cloud providers meter and bill all traffic that crosses an Availability Zone boundary in both ingress and egress directions; when pods in availability zone A query a primary database in availability zone B, every gigabyte of request and response data incurs cross-zone transfer charges; co-locate latency-sensitive and data-intensive workloads in the same availability zone as the primary database or utilize read replicas in matching zones.
</details>

**Card B: PgBouncer session pooling multiplexes thousands of short-lived HTTP-request connections onto a small PostgreSQL `max_connections` budget.** A web platform team deploys a fleet of containerized microservices where each incoming HTTP request opens a new database connection and closes it immediately after serving the request. To prevent connection exhaustion on a database with a low connection ceiling, the team deploys PgBouncer configured in session pooling mode. They expect the pooler to multiplex these transient client connections across a tiny pool of persistent backend database connections.

<details>
<summary>Check your prediction</summary>

Failure layer: Connection pool multiplexing semantics and lifecycle binding. Next action: understand that session pooling assigns a backend server connection for the entire duration of a client session; rapid connect and disconnect cycles do not multiplex connections onto few backends because PgBouncer ties the server connection to the client until that client completely terminates its socket; when hundreds of microservice pods connect simultaneously, session pooling requests an equal number of backend connections and exhausts PostgreSQL limits; configure transaction pooling mode for stateless web workloads so server connections are released back to the shared pool immediately after each transaction commits.
</details>

**Card C: External Secrets Operator needs a long-lived IAM user access key stored in a Kubernetes Secret to read AWS Secrets Manager.** A security operations team configures External Secrets Operator to synchronize credentials from AWS Secrets Manager into application namespaces. To authenticate the operator controller with the cloud provider, the team generates an IAM user access key and secret access key in the AWS console. They store these long-lived credentials in a standard Kubernetes Secret referenced by a ClusterSecretStore resource.

<details>
<summary>Check your prediction</summary>

Failure layer: Cloud workload identity federation and credential lifecycle management. Next action: recognize that External Secrets Operator does not require static IAM user keys and should authenticate using native cloud workload identity; on AWS EKS, configure IAM Roles for Service Accounts (IRSA) or EKS Pod Identity to bind the operator service account to an IAM role via OpenID Connect federation; on GCP, use Workload Identity Federation, and on Azure, use Microsoft Entra Workload ID; static IAM credentials represent an unnecessary exfiltration risk, violate compliance policies, and require manual rotation overhead.
</details>

**Card D: Running the schema migration as a Deployment initContainer is safe because Kubernetes runs it only once per rollout.** A delivery team packages database schema migration scripts directly into an application container image and executes them inside an initContainer within their Deployment manifest. The team assumes that Kubernetes runs the migration safely once during a rolling update before launching new application containers. They believe this pattern prevents version mismatches between application code and database tables.

<details>
<summary>Check your prediction</summary>

Failure layer: Container lifecycle execution and horizontal replica scaling concurrency. Next action: recognize that init containers run on every pod replica during startup rather than executing once per deployment rollout; when a deployment scales up or undergoes an uncoordinated rollout, multiple init containers execute identical schema migration commands in parallel; concurrent migrations cause database deadlocks, table lock contention, and schema corruption; execute schema migrations using an isolated Kubernetes Job configured with Argo CD PreSync hooks or Helm pre-upgrade hooks to ensure strictly serialized, single-execution guarantees.
</details>

**Success Criteria**:

- [ ] ExternalName/headless Service resolves to PostgreSQL container
- [ ] PgBouncer Deployment has 2 ready replicas
- [ ] Test pod connects through PgBouncer successfully
- [ ] Migration Job completes and creates the `users` table
- [ ] Read endpoint returns data from the simulated replica
- [ ] Credential rotation successfully triggers new pod creation via rollout

### Cleanup

```bash
kind delete cluster --name db-lab
docker rm -f lab-postgres
docker network rm db-lab
```

---

## Next Module

[Module 9.2: Managed Message Brokers & Event-Driven Kubernetes](../module-9.2-message-brokers/) — Learn how to integrate SQS, Pub/Sub, and Service Bus with Kubernetes workloads, and use KEDA to autoscale consumers based on queue depth.

## Sources

- [docs.aws.amazon.com: USER VPC.WorkingWithRDSInstanceinaVPC.html](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.WorkingWithRDSInstanceinaVPC.html) — AWS documents that RDS instances in a VPC have private IPs and can be hidden from the public internet.
- [docs.aws.amazon.com: rds secrets manager.html](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html) — The RDS Secrets Manager documentation explicitly ties this CLI flag to automatic password generation and lifecycle management in Secrets Manager.
- [github.com: external secrets](https://github.com/external-secrets/external-secrets) — The upstream project README explicitly states this core ESO behavior.
- [docs.aws.amazon.com: tutorials rotation alternating.html](https://docs.aws.amazon.com/secretsmanager/latest/userguide/tutorials_rotation-alternating.html) — AWS explicitly recommends alternating-users rotation when high availability is required.
- [github.com: Reloader](https://github.com/stakater/Reloader) — The upstream README documents automatic rollout behavior on Secret and ConfigMap updates.
- [argo-cd.readthedocs.io: sync waves](https://argo-cd.readthedocs.io/en/latest/user-guide/sync-waves/) — Argo CD's sync phases documentation explicitly defines `PreSync` as executing prior to manifest application.
- [docs.aws.amazon.com: Concepts.MultiAZ.html](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html) — AWS explicitly distinguishes single-standby Multi-AZ DB instances from Multi-AZ DB clusters that can serve reads.
- [cloud.google.com: cross region replicas](https://cloud.google.com/sql/docs/postgres/replication/cross-region-replicas) — Google Cloud documents cross-region replicas as a Cloud SQL feature for migration and DR.
- [learn.microsoft.com: concepts read replicas geo](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-read-replicas-geo) — Microsoft documents geo-replication as cross-region replica support for Flexible Server.
- [aws.amazon.com: optimizing data transfer costs when using aws network load balancer](https://aws.amazon.com/blogs/networking-and-content-delivery/optimizing-data-transfer-costs-when-using-aws-network-load-balancer/) — An official AWS networking post states the current inter-zone charge as $0.01 per GB in each direction.
- [cloud.google.com: pricing](https://cloud.google.com/vpc/pricing) — Google's VPC pricing page lists same-region inter-zone VM traffic at $0.01 per GiB and states Cloud SQL same-region pricing follows VM-to-VM rates.
- [azure.microsoft.com: bandwidth](https://azure.microsoft.com/en-us/pricing/details/bandwidth) — Azure's bandwidth pricing FAQ says data transfer between Azure services in the same region is not charged.
- [kubernetes.io: storage classes](https://kubernetes.io/docs/concepts/storage/storage-classes/) — The Kubernetes StorageClass documentation directly defines both the default and the purpose of `WaitForFirstConsumer`.
- [docs.aws.amazon.com: reboot db instance.html](https://docs.aws.amazon.com/cli/v1/reference/rds/reboot-db-instance.html) — The AWS CLI command reference explicitly documents the `--force-failover` option.
- [Service | Kubernetes](https://kubernetes.io/docs/concepts/services-networking/service/) — Explains `ExternalName`, headless Services, and the DNS behavior the module relies on for stable database hostnames.
- [Learn about using private IP | Cloud SQL](https://cloud.google.com/sql/docs/sqlserver/private-ip) — Clarifies Cloud SQL private IP connectivity and helps separate private services access from Private Service Connect.
- [docs.aws.amazon.com: Aurora Serverless v2](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html) — Documents ACU-based autoscaling for Aurora Serverless v2.
- [docs.aws.amazon.com: aurora global database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html) — Defines Global Database topology, secondary region limits, and failover/switchover semantics.
- [cloud.google.com: spanner true-time external consistency](https://cloud.google.com/spanner/docs/true-time-external-consistency) — Explains TrueTime and external consistency guarantees for global transactions.
- [learn.microsoft.com: cosmos db consistency levels](https://learn.microsoft.com/en-us/azure/cosmos-db/consistency-levels) — Lists the five consistency levels and their latency/availability tradeoffs.
- [learn.microsoft.com: cosmos db conflict resolution policies](https://learn.microsoft.com/en-us/azure/cosmos-db/conflict-resolution-policies) — States that conflict resolution policy is set at container creation and cannot be changed later.
- [docs.aws.amazon.com: rds proxy](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.html) — Describes connection pooling, failover preservation, and IAM authentication for RDS Proxy.
- [docs.aws.amazon.com: dynamodb global tables](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GlobalTables.html) — Documents multi-region replication behavior for DynamoDB global tables.
- [cloud.google.com: alloydb overview](https://cloud.google.com/alloydb/docs/overview) — Summarizes AlloyDB architecture and PostgreSQL compatibility positioning.
- [learn.microsoft.com: azure sql hyperscale](https://learn.microsoft.com/en-us/azure/azure-sql/database/service-tier-hyperscale) — Explains Hyperscale tier storage/compute separation and read scale-out.
- [cloudnative-pg.io](https://cloudnative-pg.io/) — Reference for the CloudNativePG operator when comparing in-cluster PostgreSQL to managed services.
