---
title: "Module 0.7: What is Networking?"
slug: prerequisites/zero-to-terminal/module-0.7-what-is-networking
sidebar:
  order: 8
revision_pending: false
---
> **Complexity**: `[MEDIUM]` - Long-form foundational read for absolute beginners
>
> **Time to Complete**: 90–120 minutes (long-form beginner read)
>
> **Prerequisites**: [Module 0.4: Files and Directories](../module-0.4-files-and-directories/), [Module 0.5: Editing Files](../module-0.5-editing-files/), and [Module 0.6: Git Basics](../module-0.6-git-basics/) - You should be comfortable navigating directories, editing and redirecting files, and working with terminal command workflows.

---

## What You'll Be Able to Do

After this module, you will be able to:

- **Diagnose** basic connectivity failures by separating DNS resolution, IP reachability, ports, and HTTP response status.
- **Compare** private and public IP addresses and decide when NAT, router forwarding, or a public endpoint matters.
- **Implement** terminal checks with `ping`, `curl`, and `nslookup` so you gather evidence before changing configuration.
- **Evaluate** how beginner networking ideas show up in Kubernetes Services, Pods, and the Kubernetes 1.35 API server.

---

## Why This Module Matters

Hypothetical scenario: you have just started helping with a small internal app, and someone says, "The site is down." One teammate can open it from their laptop, another sees a browser error, and a third person pastes a screenshot that only says the page was not found. If every one of those reports goes into the same mental bucket, troubleshooting becomes guessing; if you can separate name lookup, network reachability, service ports, and application responses, the same messy report becomes a sequence of checks.

Kubernetes makes this skill useful because workloads need to find each other across machines. Pods have IP addresses, and a normal Service provides a stable cluster IP and port. Cluster DNS can resolve Service names, and `kubectl` contacts the API server over HTTPS. Headless Services use a different DNS pattern. You will learn those details later.

This module builds that model from the terminal upward. You will distinguish IP addresses from ports and use DNS and HTTP responses as evidence. Then you will practice with `ping`, `curl`, and `nslookup`. An HTTP response proves that a responder answered the request, not that the intended application received it.

---

## What a Network Really Connects

A **network** is two or more computers connected so they can exchange information. That definition is deliberately plain because the essential idea is not a special cloud term; it is the same idea whether the computers are your laptop and printer on home Wi-Fi, two servers in a data center rack, or thousands of containers spread across a Kubernetes cluster. The difference is scale, reliability, and the number of systems helping messages move, not the basic goal.

Home Wi-Fi is a local network, often called a LAN. Devices on it may be able to talk to one another, depending on the network's configuration. The internet connects many networks. When you visit a website, packets can pass through several networks before a server sends a response.

Think of a large restaurant chain with an intercom system connecting kitchens. Each kitchen is a computer, each intercom endpoint is a network connection, and the wiring between locations is the network. A cook does not need to know every wire route to ask another kitchen about supplies, but someone responsible for operations needs enough vocabulary to tell the difference between a broken intercom, a wrong extension number, and a kitchen that received the call but cannot fulfill the request.

| Type | What It Is | Example |
|------|-----------|---------|
| **Local Network (LAN)** | Devices connected within a local area | Your laptop and printer on home Wi-Fi |
| **Internet (WAN)** | Computers anywhere in the world, connected through infrastructure | Your laptop talking to a server in Tokyo |

That distinction matters because a command can succeed in one network context and fail in another. Your laptop may reach a printer at home because both devices are on the same LAN, while a friend across town cannot reach that same printer because private home addresses are not routed across the public internet. In Kubernetes, the same pattern appears when one Pod can reach another inside the cluster, but a browser outside the cluster needs a Service, Ingress, LoadBalancer, or other published path.

A practical troubleshooting habit starts here: ask **which network path** you are testing. If you run a command from your laptop, you are testing the path from your laptop. If a Pod inside Kubernetes fails to reach a database, your laptop's success may not prove the Pod's path works. This is why engineers are careful about where they run a test, because the source of the request is part of the evidence.

In this diagram, `203.0.113.55` is a documentation address, not a live public server.

```text
Laptop on Wi-Fi       Home router          Internet           Public server
192.168.1.42     ->   public gateway   ->   many networks  ->  203.0.113.55
     |                    |                                      |
local address       public address                         destination address
```

Pause and predict: if your laptop can reach your router's settings page at `192.168.1.1` while the internet is disconnected, what does that prove, and what does it not prove? Take a moment to separate your local physical or wireless link from the rest of the network path before reading on.

<details><summary>Check your prediction</summary>

It proves your local network path to the router works. It does not prove that DNS, your internet provider, or any public website is reachable, because those destinations sit farther along a different path beyond the router.

</details>

The goal is not to memorize every network layer today. A **firewall** is a device or program that controls network traffic between hosts or networks. Describe the path in pieces and use terminal checks to investigate addressing, DNS, ports, firewall behavior, or an application response.

Describe the expected path before you run the command. For example, resolve the name, then expect the request to leave your laptop over Wi-Fi and cross the internet to an HTTPS service. Each test can confirm or challenge one part of that expectation.

The same idea helps when two people report different results. One person may be testing from a corporate VPN, another from a home network, and another from inside a cloud environment. Those are not duplicate tests, because each one starts from a different source and may use different DNS resolvers, routes, and firewall rules. Good troubleshooting does not erase those differences; it names them so the team can compare evidence honestly.

---

## IP Addresses: Finding the Right Computer

Every computer on a network needs an **IP address**, which is a numeric label that helps other systems send traffic to the right place. The most familiar form is IPv4, written as four numbers separated by dots. Each number can range from 0 to 255, so an address like the one below is a compact way to identify a network destination.

```text
192.168.1.42
```

An IP address is easiest to understand as a street address for a computer. If the network is a city, the IP address tells delivery systems which building should receive a message. That analogy is imperfect because networks route packets rather than mail, but it is strong enough for beginner troubleshooting: before a program can speak to another program, the network needs a destination address.

| Concept | Network | Real World |
|---------|---------|-----------|
| IP Address | `192.168.1.42` | 123 Main Street |
| What it does | Identifies a network endpoint | Identifies a building |
| Who assigns it | Depends on the network configuration | The city planning office |

Not every IP address is meant for the whole internet. RFC 1918 reserves these private IPv4 ranges for private networks; their routing information should not be propagated across the public internet.

```text
192.168.x.x    (192.168.0.0/16)
10.x.x.x       (10.0.0.0/8)
172.16-31.x.x  (172.16.0.0/12)
```

Private addresses are like apartment numbers that need a building context. `192.168.1.42` may identify your laptop within your home network, but the same address can be used elsewhere. A remote user needs an appropriate route, such as a VPN, or a public endpoint that forwards traffic to the laptop.

Public addresses can be routed on the internet, but an address alone does not guarantee reachability. In a common home setup, devices use private IPv4 addresses and a router uses Network Address Translation (NAT) to share a public IPv4 address for outbound connections. Other arrangements, including provider-side NAT, are possible.

A service bound to your laptop's private address may work from another device on the same Wi-Fi network without being reachable by a colleague elsewhere. The colleague needs an authorized route to it, such as a VPN or a public endpoint configured to forward the traffic.

The command outputs in this section are synthetic examples, not recordings from this host. On macOS, the local Wi-Fi address is often available through `ipconfig`. Your interface name may differ if you are using Ethernet, a VPN, or a newer network setup.

```bash
$ ipconfig getifaddr en0
192.168.1.42
```

On Linux, `hostname -I` prints the IP addresses assigned to the host. Some systems show more than one address because they have multiple interfaces, VPNs, bridges, or container networks. For this beginner module, notice whether any returned address sits inside the private ranges above.

```bash
$ hostname -I
192.168.1.42
```

A public IP check asks an internet service what address it sees for your request. The output below uses documentation-style example space for the public address, so your real result will differ. The important observation is that the public address is usually not the same as your laptop's private LAN address.

```bash
$ curl -s ifconfig.me
203.0.113.55
```

Pause and predict: before running `curl -s ifconfig.me`, what output do you expect to see: the same `192.168...` address your laptop uses on your local Wi-Fi, or a different address visible to the public internet? Think about what device connects directly to your internet service provider before checking your prediction.

<details><summary>Check your prediction</summary>

In a network using NAT, the external service may see a different address from your private IPv4 address. A directly assigned public address or IPv6 connection can produce a different result.

</details>

IPv6 changes the address format and greatly expands the available address space, but it does not remove the need for the same reasoning habits. A destination still needs an address, routers still move traffic between networks, and a working local path still does not prove every remote path works. Kubernetes clusters may use IPv4, IPv6, or dual-stack networking, so the beginner concept is more important than one particular address style.

When you later see a Pod IP, a Service IP, a node IP, and an external load balancer IP in Kubernetes, do not treat them as interchangeable. Each address answers a different question: which workload instance, which stable service, which machine, or which outside entry point? Module 0.7 is about building the reflex to ask that question before changing configuration.

Address scope is also why documentation examples often use special ranges rather than random real addresses. Addresses such as `203.0.113.55` and `198.51.100.22` belong to ranges reserved for examples, so they are safe for teaching without pointing learners at somebody's live system. When you write notes for yourself, borrow that habit: mark whether an address is private, public, example-only, or internal to a lab so future readers do not mistake a placeholder for a production endpoint.

In day-to-day work, the practical question is usually not "what is every possible IP address rule?" The practical question is "who can route to this address from where they are standing?" If the answer is "only devices on my LAN," then remote users need a different path. If the answer is "only Pods inside this cluster," then outside clients need a Service exposure pattern. If the answer is "anyone on the internet," then security controls become just as important as reachability.

---

## Ports: Choosing the Right Service on That Computer

An IP address gets traffic to a computer or network endpoint, but a computer runs many programs at once. Your laptop can browse the web, sync files, keep a chat app open, and listen for local development traffic at the same time. The operating system therefore needs a second piece of information that says which program should receive an incoming network connection.

That second piece is a **port**. A port is a number from 0 through 65535 that identifies a specific service or application endpoint on a machine. If the IP address is the street address of a building, the port is the apartment number, office suite, or service desk inside that building.

```text
IP Address:  192.168.1.42     = 123 Main Street
Port:        80               = Apartment 80

Full address: 192.168.1.42:80 = 123 Main Street, Apt 80
```

The colon in `192.168.1.42:80` separates the IPv4 address from the service port. Many tools use this combined form. A request to the right IP on the wrong port is like arriving at the right building and knocking on a storage closet instead of the help desk. TCP (Transmission Control Protocol) delivers an ordered stream of bytes to applications. The transport protocol matters: TCP and UDP have separate port spaces.

| Port | Service | What It Does |
|------|---------|-------------|
| 80 | HTTP | Regular web traffic (when you visit a website) |
| 443 | HTTPS | Secure web traffic (the padlock in your browser) |
| 22 | SSH | Secure remote terminal access |
| 53 | DNS | Domain name lookups |
| 6443 | Kubernetes API | Common secure API server port; the configured port can differ |

Ports also explain why a host can be reachable while an application is unavailable. A machine may reply to basic network probes but have no web server listening on port 80. Another machine may have HTTPS working on port 443 while SSH on port 22 is intentionally blocked by a firewall. The question is not only "can I reach the computer?" but also "can I reach the service I need?"

Hypothetical scenario: an internal dashboard was moved to a new VM, and someone copied the old hostname but forgot that the application now listens on port 8080 behind a reverse proxy, which receives requests and forwards them to a server. Basic ping checks succeed, and the server is not down, yet browsers fail when they try the default HTTPS path. Verify which process is listening on which port, then update the route or proxy configuration.

In Kubernetes, a Service can accept traffic on one port and forward it to a target port on selected Pods. The API server commonly listens securely on port 6443. These mappings let clients use a Service without knowing each Pod's address.

```text
Browser request         Kubernetes Service          Pod container
https://app.example ->  Service port 443      ->    target port 8080
      secure web              stable entry             app process
```

Pause and predict: imagine a server at `203.0.113.55` replies to `ping`, but `curl http://203.0.113.55` times out. Which fact did `ping` prove, and which fact remains unproven? Consider the difference between network-layer echo requests and transport-layer application ports before revealing the answer.

<details><summary>Check your prediction</summary>

It showed that ICMP (Internet Control Message Protocol) echo replies arrived for that probe. ICMP carries network control messages, including echo probes. The replies did not prove that an HTTP service is listening on port 80 or that a firewall allows traffic on that port.

</details>

A TCP connection can be accepted, refused, or time out. A refusal might mean no process is listening or that a device actively rejected the attempt. A timeout can have several causes, including filtering. Even an accepted connection does not prove that the application is healthy.

For a beginner, the operational rule is simple: name the address and the port together when you discuss a network dependency. Saying "the database is at `10.0.5.50`" is incomplete if the application expects PostgreSQL on `5432`. Saying "the database is at `10.0.5.50:5432`" gives a teammate enough information to test the same destination and avoid accidentally checking a web port instead.

Ports also help you avoid blaming the wrong team. If an application is configured to call the right database address on the wrong port, the database team may see no meaningful traffic at all. If a firewall permits the address but denies the service port, the host can look alive while the application path still fails. When you include the port in your report, you give network, platform, and application engineers a shared target to verify.

Kubernetes makes this concrete through Service port mapping. A Service can receive traffic on one port and forward it to a different target port on the selected Pods. That is not a trick; it is a convenience that lets callers use a stable contract while the application process listens where it needs to listen. The tradeoff is that troubleshooters must check both sides of the mapping, because a mismatch can make the Service look correct while traffic lands on the wrong container port.

---

## DNS: Turning Names into Addresses

Humans use names like `google.com`, `github.com`, and `api.example.com`. Computers route traffic using addresses, so a client needs an address before it can connect. The **Domain Name System**, or DNS, can answer questions such as "which IP address should I use for this name?" The addresses in the following diagrams are illustrative and may not be current answers.

```text
You type:    google.com
DNS returns: 142.250.80.46
Your computer connects to: 142.250.80.46
```

DNS is often described as the phone book of the internet. The analogy works because a name is convenient for a person, while the underlying system needs the numeric destination. It also helps explain a common failure mode: if the phone book entry is missing, stale, or pointing to the wrong place, the server can be perfectly healthy and still unreachable by name.

| Without DNS | With DNS |
|-------------|----------|
| "Call 142.250.80.46" | "Call Google" |
| You need to memorize numbers | You just remember names |
| Like the old days of memorizing phone numbers | Like your phone's contact list |

A simplified DNS lookup has several steps. Your computer may first check a local cache, then ask a configured resolver. That resolver may have a cached answer or ask other DNS servers. The following example assumes the router forwards DNS queries; other networks use different resolvers.

```text
1. You type: google.com
2. Your computer asks your router: "What's the IP for google.com?"
3. Your router asks a DNS server: "What's the IP for google.com?"
4. The DNS server responds: "142.250.80.46"
5. Your computer connects to 142.250.80.46
```

This usually happens so quickly that it feels invisible. That invisibility is convenient until DNS is the broken piece, because the visible symptom may look like a website or API outage. A browser saying it cannot find a server may mean the application is down, but it may also mean the name never resolved to an address.

The useful distinction is between a **name failure** and an **address failure**. `NXDOMAIN` is a resolver's answer that the queried name does not exist. If `nslookup api.example.com` returns it, you have tested that resolver's answer, not the application. One IP can serve several named sites, or **virtual hosts**, selected using the hostname in the request. A direct-IP request may reach a default site or intermediary, so its response does not establish that the named application works.

DNS also involves caching. Records include a time-to-live, often abbreviated TTL, that tells resolvers how long they may keep an answer before checking again. A low TTL can make planned migrations easier because clients refresh sooner, while a high TTL can reduce lookup load but make stale answers linger after an address changes.

This is why DNS changes can feel inconsistent during cutovers. One user may receive the new address because their resolver refreshed, while another user keeps seeing the old address until cache expires. That does not require an invented outage story; it follows directly from how caching works, and it is one reason engineers plan DNS migrations instead of flipping records casually.

In Kubernetes 1.35, cluster DNS can give a normal Service a name that resolves to its cluster IP. A headless Service can instead resolve to backing endpoint addresses; its configuration determines the DNS records. A name is a lookup, not the destination itself.

DNS failures are especially tempting to misread because they happen before the visible application conversation. If a name does not resolve, there may be no HTTP status code, no server log entry, and no useful application metric, because the request never found a destination. That absence of downstream evidence is itself useful. It tells you to inspect the name, resolver, zone, search suffix, or cache before changing the application.

The reverse mistake is also common: a name resolves successfully, so someone assumes DNS can be ignored. Resolution only tells you that a name produced an address; it does not guarantee the address is current, intended, reachable from every source, or serving the right application. When the result looks suspicious, compare the returned address with deployment notes, load balancer configuration, or the expected public endpoint before moving on.

---

## HTTP Responses and Terminal Evidence

For web traffic, HTTP responses include a status code. An HTTP responder might be the intended server or an intermediary, so the status is evidence about the response to this request, not proof of which backend handled it.

`200 OK` reports a successful request. `404 Not Found` means the responding server did not find a current representation or is unwilling to disclose one; it does not prove the resource is absent. `500 Internal Server Error` reports an unexpected server condition.

| Code | Meaning | Analogy |
|------|---------|---------|
| 200 | OK - here's what you asked for | "Order up! Here's your food." |
| 404 | Not found or not disclosed | "That dish is not available on this menu." |
| 500 | Server error - something broke on their end | "The kitchen is on fire." |

Visiting a website is like sending a letter with several pieces of addressing information. You start with a name, look up the numeric destination, choose the service door, send the request, and wait for a response. Each step can fail in a different way, and each failure should change what you test next.

```text
1. You want to send a letter to "Google HQ"
   (You type google.com)

2. You look up the address in the phone book
   (DNS translates google.com -> 142.250.80.46)

3. You write the street address on the envelope
   (IP address: 142.250.80.46)

4. You write the apartment/department number
   (Port: 443 for HTTPS)

5. You put the letter in the mailbox
   (Your computer sends the request over the network)

6. Google receives it and sends a reply
   (The web page comes back to your browser)
```

The commands in this module give you evidence at different points in that chain. `nslookup` checks whether a name becomes an address. `ping` can show whether a host responds to ICMP probes, though not every host allows them. `curl` tests web protocols and can show response headers, status codes, redirects, and raw content.

`ping` sends ICMP echo requests and waits for replies. It is like knocking on a door to see whether anyone responds, but it is not the same as asking the web application for a page. A failed ping is a clue, not a final verdict. The following outputs in this section are synthetic examples, not live captures.

```bash
$ ping -c 4 google.com
PING google.com (142.250.80.46): 56 data bytes
64 bytes from 142.250.80.46: icmp_seq=0 ttl=118 time=11.4 ms
64 bytes from 142.250.80.46: icmp_seq=1 ttl=118 time=10.8 ms
64 bytes from 142.250.80.46: icmp_seq=2 ttl=118 time=11.2 ms
64 bytes from 142.250.80.46: icmp_seq=3 ttl=118 time=10.9 ms
```

The `-c 4` flag means "send four probes, then stop." Without a count, `ping` on Linux and macOS commonly keeps running until you press **Ctrl+C**. The `time=11.4 ms` value is the round-trip time for one probe, which can help you compare rough latency, but it should not be treated as a complete performance test.

`curl` is a web client for your terminal. It can fetch a page, request only headers, follow redirects when asked, display errors, and send data for API testing. For this module, the key idea is that `curl` exercises HTTP or HTTPS, so it can prove things that `ping` cannot prove.

```bash
$ curl -s example.com
```

The `-s` flag means silent mode, which hides the progress meter so the page content is easier to inspect. If the request succeeds, you may see raw HTML rather than the rendered page a browser would show. That output shows an HTTP responder returned content to a terminal client.

```html
<!doctype html>
<html>
<head>
    <title>Example Domain</title>
...
```

Fetching only headers is often cleaner when you only need status and metadata. `curl -I` sends a HEAD request, which asks for the response headers without the resource body. The HTTP status line appears near the top.

```bash
$ curl -I example.com
HTTP/1.1 200 OK
Content-Type: text/html; charset=UTF-8
...
```

`nslookup` asks a DNS server about a name. In the example below, the first address is the DNS server queried; the address under `Name` is the answer. Output varies by system and query result. If a lookup fails, investigate the name and resolver before changing a record or blaming the web app.

```bash
$ nslookup google.com
Server:    192.168.1.1
Address:   192.168.1.1#53

Non-authoritative answer:
Name:   google.com
Address: 142.250.80.46
```

A careful check usually combines commands rather than relying on one. If DNS fails, use `nslookup` to confirm the name problem. If DNS works but HTTP fails, use `curl -I` to inspect the status or timeout. If ping fails but curl succeeds, remember that ICMP may be blocked while normal web traffic is allowed.

Pause and predict: a user reports that `api.example.com` is down, but you know the server's IP address from your deployment notes. Which approach would you test first—DNS name resolution or a direct HTTP request to the IP—and what would each result prove? Decide your troubleshooting order before checking the explanation.

<details><summary>Check your prediction</summary>

Checking DNS first shows the queried resolver's answer. A direct-IP HTTP response shows that a responder answered that request, but it may be an intermediary or a different virtual host. The right sequence depends on the symptom; compare each result with the expected endpoint.

</details>

Translate command output into a narrow observation. `nslookup` returning an address shows that the queried DNS server supplied an answer for that name. `ping` replies show that ICMP echo responses arrived. `curl -I` returning `200 OK` shows that an HTTP responder reported success for that request.

The opposite sentence is just as important: "this does not prove." A DNS answer does not prove the web app is healthy. Ping replies do not prove HTTPS works. A `404` does not prove routing is broken. A `500` does not prove the customer typed the wrong URL. Beginners often want one command that declares the whole system healthy or unhealthy, but real troubleshooting is usually a chain of smaller, honest claims.

When you write a handoff note, include both the command and your interpretation. For example, "`nslookup api.example.com` returned `203.0.113.100`, so DNS produced an address from my laptop's resolver; `curl -I` to that name returned `500`, so an HTTP responder reported an unexpected condition." That note lets the next engineer see the evidence and the questions that remain open.

---

## When This Doesn't Apply

This beginner model does not replace deeper network engineering. It will not teach you subnet calculations, packet captures, BGP routing, TLS certificate validation, service mesh policy, or Kubernetes Container Network Interface internals. Those topics matter later, but starting with them would hide the more common beginner need: deciding whether a failure belongs to name lookup, address reachability, port selection, or application response.

The model also does not mean every tool is authoritative in every environment. Corporate networks, VPNs, proxies, firewalls, and cloud load balancers can deliberately change what a command sees. A proxy may allow browser traffic while direct `curl` requests fail, or a firewall may allow HTTPS while blocking ping. The lesson is to interpret each command according to what it actually tests.

Use the pattern of layered evidence when you are new to a system. Start with the name, then the address, then the port, then the protocol response, and keep notes about where each test ran. Avoid the anti-pattern of changing DNS records, firewall rules, application code, and Kubernetes manifests all at once, because that destroys the evidence trail and makes the next symptom harder to explain.

| Pattern | Use It When | Why It Works |
|---------|-------------|--------------|
| Test from the failing location | A report comes from one laptop, Pod, or server | The source network path is part of the bug |
| Separate name from address | A hostname fails or returns a surprising endpoint | DNS can fail while the destination server is healthy |
| Name the port explicitly | A service is reachable in one tool but not another | Ports identify the specific program, not just the host |
| Prefer evidence over labels | Someone says "network issue" or "site down" | The same phrase can describe several unrelated failures |

An anti-pattern worth calling out early is treating a successful ping as proof that the application is healthy. Ping can show that one kind of network probe received a reply, but it does not prove HTTP works, the database accepts connections, DNS points at the intended host, or Kubernetes routed traffic to healthy Pods. It is a useful knock, not a full health check.

Another anti-pattern is treating a `404` as proof of a network outage or an absent resource. An HTTP responder answered, but it may not have found a representation or may be withholding disclosure. Check the URL, endpoint, routing, content, and authorization policy rather than assuming either complete network failure or complete network correctness.

---

## When You'd Use This vs Alternatives

Use beginner terminal checks when you need quick, local evidence and the system is simple enough that one command can answer one question. `nslookup`, `ping`, and `curl` are excellent first tools because they are available on many systems, easy to explain, and precise enough to prevent random changes. They are especially useful before escalating an issue, because a short command transcript can show what failed.

Use deeper tools when the first checks narrow the problem but do not explain it. Packet captures can reveal low-level traffic, cloud logs can show load balancer decisions, and application logs can help explain `500` responses. Ask what layer each tool tests.

| Situation | First Tool | What It Can Tell You | Better Follow-Up If Needed |
|-----------|------------|----------------------|----------------------------|
| Hostname looks wrong | `nslookup` | Whether DNS returns an address | Check DNS provider records and TTL |
| Host may be unreachable | `ping -c 4` | Whether ICMP replies arrive | Test the actual application port |
| Website or API misbehaves | `curl -I` | HTTP status and headers | Inspect app logs, proxy logs, or routes |
| Local and public addresses differ | `curl -s ifconfig.me` | What public address the internet sees | Review NAT, firewall, or load balancer rules |
| Kubernetes API is unreachable | Full `kubectl` command output | What error the client reports | Check the configured endpoint and credentials; 6443 is a common API server port |

For Kubernetes 1.35, apply the same logic to cluster documentation. Service names use cluster DNS, Service ports can map to Pod target ports, and `kubectl` needs the API server endpoint and appropriate credentials. Keep name, address, port, and protocol response distinct.

Use the deeper alternatives when the first evidence points there. If DNS resolves to the expected address and `curl` returns a `500`, application logs are a better next stop than more DNS commands. If the address and port time out from one network but work from another, firewall or routing evidence matters more than code changes. The beginner tools do not solve every issue; they tell you where a sharper tool belongs.

---

## Did You Know?

1. **DNS replaced a host list.** RFC 1034 describes how the centrally maintained `HOSTS.TXT` approach became harder to manage as the network grew. DNS specifications appeared in 1983; RFC 1034 documented its concepts in 1987.
2. **IPv4 has about 4.3 billion possible addresses.** Its 32-bit address space contains 2³² possible values, including addresses reserved for special purposes.
3. **Ports have a standardized registry.** RFC 6335 describes how service names and port numbers are managed.
4. **Kubernetes has a default API port.** The API server commonly uses secure port 6443, though its configured port can differ. Check the configured endpoint when `kubectl` cannot reach a cluster.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Forgetting `-c` with ping | On Linux and macOS, `ping` often keeps running until interrupted | Use `ping -c 4 host.example` or press **Ctrl+C** to stop a long-running probe |
| Pinging a site that blocks ICMP | A server or firewall may drop ping traffic while allowing web traffic | Treat ping failure as a clue, then test the real service with `curl -I` |
| Confusing IP address and port | Both appear near each other in connection strings, so beginners merge them mentally | Say the full destination as `address:port`, such as `192.168.1.42:80` |
| Treating a private IP as publicly reachable | Addresses like `192.168.x.x` work inside a local network, not across the internet | Use a public endpoint, VPN, tunnel, or explicit router forwarding when remote access is intended |
| Forgetting the URL scheme with curl | `curl example.com` may not test the same protocol path as a browser using HTTPS | Be explicit with `curl http://example.com` or `curl https://example.com` |
| Assuming DNS failure means the server is down | A missing or stale DNS record can fail before traffic reaches the server | Test the known IP when appropriate, then repair the DNS record or cache plan |
| Calling every `404` a network problem | A responder answered, but did not find or disclose a representation | Check the URL, endpoint, routing, authorization policy, and application logs |
| Changing multiple layers at once | Pressure during an outage makes random edits feel productive | Change one thing at a time and rerun the same evidence-gathering command |

---

## Quiz

<details><summary>Question 1: Your friend says their new laptop's address is `192.168.1.42` and asks you to connect to it from your house. You try, but it fails. Based on the type of address provided, why did this not work?</summary>

`192.168.1.42` is a private IPv4 address and is not globally reachable through the public internet. Separate private networks can be connected by an appropriate route, such as a VPN, or through a public endpoint configured to forward traffic. The failed attempt alone does not prove the laptop is broken.

</details>

<details><summary>Question 2: You can successfully run `ping 203.0.113.55` and receive replies, but `curl http://203.0.113.55` times out. What does each result show, what remains open, and what would you check next?</summary>

The ping result shows echo replies arrived; it does not prove a web service is available. `curl http://203.0.113.55` attempts HTTP on port 80, but the timeout does not identify its cause. A firewall or a service problem is possible. Check the intended endpoint, application port, and path before changing configuration.

</details>

<details><summary>Question 3: A user cannot access `api.example.com`. `nslookup api.example.com` says the name cannot be resolved, but `curl http://203.0.113.100` returns `200 OK`. What should you diagnose first?</summary>

The queried resolver could not resolve the name. The direct-IP response shows an HTTP responder reported success for that request; it may be a different virtual host or intermediary and does not establish that the named application works. Check the resolver's answer and compare it with the expected DNS records and endpoint.

</details>

<details><summary>Question 4: A customer says the website is down. You run `curl -I https://example.com` and receive `500 Internal Server Error`. What does the response show, what remains open, and what would you check next?</summary>

An HTTP responder reported an unexpected condition for this request. It could be a gateway or another intermediary, so the response alone does not prove that the intended application was reached or that DNS selected the expected endpoint. Compare the destination with the expected endpoint and inspect gateway and application logs.

</details>

<details><summary>Question 5: A junior developer runs `ping -c 4 api.example.com`, sees only request timeouts, and declares the API server completely down. You run `curl -I https://api.example.com` and get `HTTP/1.1 200 OK`. Why was the conclusion wrong?</summary>

The conclusion treated ping as a complete application health check. The HTTPS request received a successful response, while the echo probes received no replies. Filtering or ignored ICMP is one hypothesis; destination selection, timing, and other path differences also need checking. These observations do not establish complete API health or the cause of the missing echo replies.

</details>

<details><summary>Question 6: An application should connect to a database at `10.0.5.50:5432`, but the logs say `Connection refused to 10.0.5.50 on port 80`. What is the most likely configuration error?</summary>

The logged attempt uses the expected address but the wrong port. Port 80 is the conventional HTTP port, while the scenario specifies port 5432 for the database. A refusal can result from a missing listener or an active rejection. Check the connection configuration and verify the intended database endpoint before changing it.

</details>

<details><summary>Question 7: Your team launched `promo.company.com`, but `nslookup promo.company.com` returns `NXDOMAIN`. The lead engineer says the server is running at `198.51.100.22`. What system needs attention?</summary>

The queried resolver reported that the name does not exist. Check the spelling, resolver and authoritative DNS records (the records held by the servers responsible for the zone) before changing them; a cached or resolver-specific answer does not establish what every client sees. The response says nothing about the health of the server at `198.51.100.22`.

</details>

---

## Hands-On Exercise: Exploring the Network

### Objective

Use networking commands to explore connections, look up addresses, fetch web content, and record what each command proves. The point is not to memorize output perfectly, because networks differ. The point is to practice reading each result as evidence about DNS, address reachability, ports, or HTTP response behavior.

### Setup

Create a fresh disposable workspace under your exclusive control. Run one line at a time; stop on any `mkdir` or `cd` error before later commands or redirects. If the name already exists as a file, directory, or symlink, leave it untouched, choose an unused name, and substitute that name in every later workspace path. Do not use `mkdir -p` for this root. Continue only when `pwd` identifies the new workspace and `ls -a` shows only `.` and `..`; uncertain ownership means start fresh.

```bash
$ mkdir ~/kubedojo-practice
$ cd ~/kubedojo-practice
$ pwd
$ ls -a
```

### Tasks

1. **Verify network connectivity to a popular website.** Use the terminal tool that sends small messages to a server to see if it responds. Send exactly four messages to `google.com` so the command does not run forever, then note the IP address it resolves to and the response times.

```bash
$ ping -c 4 google.com
```

<details><summary>Solution notes</summary>

Look for a line that starts with `PING` and includes an address in parentheses, then look for reply lines with `time=` values. If every probe times out, do not immediately conclude that Google is down; your network, DNS resolver, or ICMP policy may be affecting the test. You will gather stronger HTTP evidence in a later step.

</details>

2. **Compare latency with another service.** Run the same style of check against `cloudflare.com`. The response times may be faster or slower depending on your location, routing, Wi-Fi quality, and whether ICMP traffic is handled similarly by both destinations.

```bash
$ ping -c 4 cloudflare.com
```

<details><summary>Solution notes</summary>

Compare the `time=` values, but avoid over-interpreting a single short sample. A few ping replies can show rough reachability and latency, not full application performance. If one host replies and another does not, continue with DNS and HTTP checks before deciding why.

</details>

3. **Find your local IP address.** Use the command that matches your operating system, then decide whether the result looks private. A private address commonly starts with `192.168.`, `10.`, or a `172.16` through `172.31` range.

On macOS, run this command first if your active network interface is the usual Wi-Fi interface:

```bash
$ ipconfig getifaddr en0
```

On Linux, run this command and then choose the address associated with your normal network path:

```bash
$ hostname -I
```

<details><summary>Solution notes</summary>

Write down the address and determine whether it is private or public. If you see multiple addresses, you may have multiple network interfaces, a VPN, or container networking on the machine. For this exercise, identify the address associated with your normal internet connection.

</details>

4. **Discover your public IP address.** Use `curl` in silent mode to fetch the page at `ifconfig.me`. Compare this result with your local address and consider how NAT, a proxy, or the address family can affect the comparison.

```bash
$ curl -s ifconfig.me
```

<details><summary>Solution notes</summary>

The public result is the address an external service sees for your request. On many networks, this is your router, firewall, VPN, or provider edge address rather than your laptop's private address. If the value matches your local address, you may be on a network that gives your machine a public address directly.

</details>

5. **Manually resolve a domain name.** Use `nslookup` to find an address for `github.com`. Locate the answer section and write down one returned IP address, knowing that large sites can return different valid answers depending on geography and resolver behavior.

If `nslookup` is unavailable, use `host github.com` if installed; otherwise skip this check until a DNS lookup tool is available.

```bash
$ nslookup github.com
```

<details><summary>Solution notes</summary>

The important outcome is not a specific GitHub address; it is seeing DNS translate a human-readable name into one or more addresses. If the lookup fails, check your internet connection or resolver configuration before trying to debug GitHub itself.

</details>

6. **Fetch a web page.** Use `curl` to request `example.com` and observe the raw HTML. This proves that a terminal web client can retrieve content, even though it does not render the page like a browser.

```bash
$ curl -s example.com
```

<details><summary>Solution notes</summary>

You should see HTML that includes a page title for Example Domain. If you see a redirect, proxy message, or security product page, record what your environment returned. The evidence still matters because it describes your actual path.

</details>

7. **Examine server response headers.** Ask for only the response metadata from `example.com`. Look for the HTTP status line, then decide whether the result proves DNS, the network path, and the HTTP service all worked for this request.

```bash
$ curl -I example.com
```

<details><summary>Solution notes</summary>

A `200 OK` status means the responder reports success for the request. With `-I`, the request is HEAD and returns headers rather than the resource body. A redirect is also HTTP evidence; inspect its headers for the next location.

</details>

8. **Trigger a specific HTTP error code.** Request headers for a path that should not exist on `example.com`. Your goal is to see that a `404` is an application-level response, not a DNS failure.

```bash
$ curl -I example.com/this-page-does-not-exist
```

<details><summary>Solution notes</summary>

A `404` demonstrates an HTTP response, but not necessarily resource absence: the responder may withhold disclosure. That differs from a name lookup failure or connection timeout; verify the endpoint, path, and access policy before deciding why this request returned `404`.

</details>

9. **Combine networking with file skills.** Fetch the raw HTML of `example.com` silently, redirect it into a file called `my-first-webpage.html`, and then print the file to confirm it contains the response body.

```bash
$ curl -s example.com > my-first-webpage.html
$ cat my-first-webpage.html
```

<details><summary>Solution notes</summary>

This step connects terminal networking with file redirection. The command writes the response body into a local file, and `cat` displays what was received. It might be HTML, a redirect, or an error response. If the file is empty, rerun the command without `-s` or inspect the exit status and network response.

</details>

When finished, if this is the disposable directory you created and you no longer need its contents, leave it and remove it with `cd ~ && rm -r ~/kubedojo-practice`. If you chose another name, substitute that exact path.

### Diagnostic Challenge: Four Network Incidents, No Recipe

The cookbook tasks above guided you through exact arguments. The four transcripts below are synthetic examples, not captures of real incidents. For each, distinguish the observed symptom from possible causes, identify which layers deserve investigation, and choose a justified next check. State what remains unknown; do not invent a single failing device, layer, or configuration. Write down your reasoning before each reveal.

```text
$ nslookup api.example.com
Server:    192.168.1.1
Address:   192.168.1.1#53

** server can't find api.example.com: NXDOMAIN

$ curl -I http://203.0.113.100
HTTP/1.1 200 OK
Content-Type: application/json
Date: Thu, 17 Sep 2026 11:20:00 GMT
```

**Incident A: The disappearing API endpoint.** A developer files an urgent ticket stating that the staging API is completely offline because their local test suite cannot connect to `api.example.com`. You gather the two terminal checks above from the developer's workstation. Which layer has failed, what does the evidence prove, and what is the immediate next check or corrective action? Commit to your analysis before revealing the diagnosis below.

<details><summary>Hint 1: Which kind of evidence?</summary>

Which command tests the name, and which sends an HTTP request to an address?
</details>

<details><summary>Hint 2: Narrow the conclusion</summary>

Does the direct-IP response identify the site that would answer the named request?
</details>

<details><summary>Diagnosis and layer analysis for Incident A</summary>

**Observed Layer:** The queried resolver reported NXDOMAIN.

**Evidence:** The queried DNS resolver reported `NXDOMAIN`, while the direct-IP HTTP request received `200`. Investigate the name and resolver response, but do not call the API fully healthy: an IP request can reach a different virtual host, and one response does not verify every application function or the intended name mapping.

**Next Check or Action:** Verify the intended endpoint and compare the resolver's answer with the authoritative DNS zone and recent changes. Check cache behavior before changing a record; the direct-IP response alone does not prove that address is the correct target for the name.

</details>

```text
$ ping -c 4 payment-gateway.example.com
PING payment-gateway.example.com (198.51.100.75): 56 data bytes
Request timeout for icmp_seq 0
Request timeout for icmp_seq 1
Request timeout for icmp_seq 2
Request timeout for icmp_seq 3
--- payment-gateway.example.com ping statistics ---
4 packets transmitted, 0 packets received, 100.0% packet loss

$ curl -I https://payment-gateway.example.com
HTTP/2 200
content-type: application/json
date: Thu, 17 Sep 2026 11:22:00 GMT
```

**Incident B: The silent ping probe.** An automated ping alert reports total packet loss for `payment-gateway.example.com`, while `curl -I` receives `200` over HTTPS. What does each probe establish, which causes remain hypotheses, and what should you check next? Consider protocol differences before opening the solution.

<details><summary>Hint 1: Which kind of evidence?</summary>

Which protocol does each probe test?
</details>

<details><summary>Hint 2: Narrow the conclusion</summary>

Does a missing echo reply explain why it is missing, or rule out an HTTPS response?
</details>

<details><summary>Diagnosis and layer analysis for Incident B</summary>

**Observed Layer:** ICMP echo replies were not received; HTTPS returned a response for this probe.

**Evidence:** No echo replies arrived, while the HTTPS request received `200`. ICMP filtering is one hypothesis, not a demonstrated cause. Different protocols, resolved addresses, intermediaries, and timing can produce different results. The HTTP response demonstrates success for that request, not the health of every application function.

**Next Check or Action:** Compare probe destinations and timing, then check ICMP policy with the network owner. Use an application-appropriate health check for service availability; neither a restart nor a declaration of complete health follows from these two probes alone.

</details>

```text
$ curl -I https://internal-docs.example.com/team/runbooks/networking
HTTP/1.1 404 Not Found
Content-Type: text/html; charset=UTF-8
Server: nginx/1.24.0
Date: Thu, 17 Sep 2026 11:24:00 GMT
Content-Length: 162
```

**Incident C: The missing runbook.** A colleague reports: "The internal docs server is down; nobody can access the networking runbook at `https://internal-docs.example.com/team/runbooks/networking`." You run `curl -I` against the URL and receive the output above. Which layer is failing, what does the evidence prove about the lower layers, and what should you investigate next? Separate web server availability from page routing before reading on.

<details><summary>Hint 1: Which kind of evidence?</summary>

Did the command receive an HTTP response or fail before one arrived?
</details>

<details><summary>Hint 2: Narrow the conclusion</summary>

Does a 404 identify the responding backend or prove that the document is absent?
</details>

<details><summary>Diagnosis and layer analysis for Incident C</summary>

**Observed Layer:** An HTTP responder returned an application-level status; content, authorization, endpoint selection and routing need investigation. The status alone does not rule out a wrong DNS destination or intermediary.

**Evidence:** An HTTP responder returned `404` for the requested URL. That narrows the investigation toward content, routing, authorization, or the selected endpoint, but does not prove the document is absent or that the response came from the intended backend. The `Server` header is a response claim, not independent verification of the server software.

**Next Check or Action:** Verify the URL, expected endpoint, access policy, and moved or renamed files; inspect routing with the service owner. Escalate according to the evidence rather than declaring a complete server outage or ruling out infrastructure involvement from one response.

</details>

```text
$ curl http://10.0.5.50:80
curl: (7) Failed to connect to 10.0.5.50 port 80 after 12 ms: Connection refused

$ ping -c 2 10.0.5.50
PING 10.0.5.50 (10.0.5.50): 56 data bytes
64 bytes from 10.0.5.50: icmp_seq=0 ttl=64 time=0.824 ms
64 bytes from 10.0.5.50: icmp_seq=1 ttl=64 time=0.791 ms
```

**Incident D: Connection refused on the database host.** A microservice reports a database connectivity error at `10.0.5.50`. An operator's HTTP probe to port 80 is refused while ping receives replies. What do those tests establish, and what endpoint information is missing before anyone can justify a configuration change? Verify the intended service role before checking the answer.

<details><summary>Hint 1: Which kind of evidence?</summary>

Which probe tests a port, and which tests ICMP echo?
</details>

<details><summary>Hint 2: Narrow the conclusion</summary>

Does a refusal on port 80 identify the database's configured port?
</details>

<details><summary>Diagnosis and layer analysis for Incident D</summary>

**Observed Layer:** The TCP connection to port 80 was refused; ICMP echo received replies.

**Evidence:** The address answered echo probes, while the TCP attempt was actively refused. A missing listener or an active firewall rejection could explain it; this transcript does not identify the rejecting device, database product, configured port, or the microservice's actual connection settings.

**Next Check or Action:** Confirm the intended database endpoint and protocol from its owner or configuration, then inspect its listener and access policy. Test that authorized endpoint with a suitable client before changing the microservice connection string; an HTTP probe to port 80 does not establish which database port to use.

</details>

### Kubernetes transfer

In a hypothetical cluster with domain `cluster.local`, a normal Service named `web` in namespace `shop` has cluster IP `10.96.0.10`, TCP port `80`, and target port `8080`. A Pod looks up `web.shop.svc.cluster.local`, then requests `http://web.shop.svc.cluster.local` and receives `500`. Identify the name, address, Service port, target port, and response. What should you check next?

<details><summary>Worked answer</summary>

The name is `web.shop.svc.cluster.local` and the Service address is `10.96.0.10`. The request uses Service port 80; the Service maps it to port 8080 on a selected Pod. The HTTP responder reported `500`; that alone does not identify the backend or prove why it failed. Compare the resolved address and Service mapping with the expected configuration, then inspect the relevant gateway and application logs.

</details>

### Success Criteria

You have completed this exercise when you can explain the evidence from each command without treating every failure as the same kind of outage:

- [ ] Ping a website and identify whether replies include response times.
- [ ] Find your local IP address and label it as private or public.
- [ ] Find your public IP address as seen by an external service.
- [ ] Look up a domain name with `nslookup` and identify the returned address.
- [ ] Fetch a web page with `curl` and recognize raw HTML output.
- [ ] Identify `200 OK` and `404 Not Found` as different HTTP responses.
- [ ] Save a web page to a file and read that file from the terminal.
- [ ] Explain whether each command tested DNS, address reachability, a port, or HTTP behavior.
- [ ] Explain what each diagnostic transcript shows, what remains uncertain, and what to check next.
- [ ] Explain how Kubernetes Service names, Pod IPs, and API server port 6443 map to DNS, address, port, and protocol response.

---

## Sources

- [RFC 1918: Address Allocation for Private Internets](https://www.rfc-editor.org/rfc/rfc1918)
- [RFC 3022: Traditional IP Network Address Translator](https://www.rfc-editor.org/rfc/rfc3022)
- [RFC 5737: IPv4 Address Blocks Reserved for Documentation](https://www.rfc-editor.org/rfc/rfc5737)
- [RFC 6335: Service Name and Transport Protocol Port Number Registry Procedures](https://www.rfc-editor.org/rfc/rfc6335)
- [Kubernetes 1.35: Service](https://v1-35.docs.kubernetes.io/docs/concepts/services-networking/service/)
- [Kubernetes 1.35: DNS for Services and Pods](https://v1-35.docs.kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
- [Kubernetes 1.35: Pods](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/pods/)
- [RFC 1034: Domain Names - Concepts and Facilities](https://www.rfc-editor.org/rfc/rfc1034)
- [RFC 1035: Domain Names - Implementation and Specification](https://www.rfc-editor.org/rfc/rfc1035)
- [RFC 883: Domain Names - Implementation and Specification](https://www.rfc-editor.org/rfc/rfc883)
- [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110)
- [Kubernetes 1.35: Ports and Protocols](https://v1-35.docs.kubernetes.io/docs/reference/networking/ports-and-protocols/)
- [RFC 8200: Internet Protocol, Version 6 Specification](https://www.rfc-editor.org/rfc/rfc8200)
- [RFC 9293: Transmission Control Protocol](https://www.rfc-editor.org/rfc/rfc9293)
- [RFC 768: User Datagram Protocol](https://www.rfc-editor.org/rfc/rfc768)
- [IANA Service Name and Transport Protocol Port Number Registry](https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml)
- [curl command line tool manual](https://curl.se/docs/manpage.html)
- [Linux ping manual](https://man7.org/linux/man-pages/man8/ping.8.html)
- [Kubernetes 1.35: Controlling Access to the Kubernetes API](https://v1-35.docs.kubernetes.io/docs/concepts/security/controlling-access/)
- [Debian nslookup manual](https://manpages.debian.org/bookworm/bind9-dnsutils/nslookup.1.en.html)
- [Apache: Name-based Virtual Host Support](https://httpd.apache.org/docs/2.4/vhosts/name-based.html)
- [RFC 9499: DNS Terminology](https://www.rfc-editor.org/rfc/rfc9499.html)
- [RFC 792: Internet Control Message Protocol](https://www.rfc-editor.org/rfc/rfc792.html)
- [NIST: Firewall](https://csrc.nist.gov/glossary/term/firewall)
- [MDN: Proxy server](https://developer.mozilla.org/en-US/docs/Glossary/Proxy_server)
- [MDN: HEAD request method](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/HEAD)

## Next Module

**Next Module**: [Module 0.8: Servers and SSH](../module-0.8-servers-and-ssh/) - Learn what a server is, where servers live, and how to connect to them remotely.
