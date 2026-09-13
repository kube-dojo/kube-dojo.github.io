---
title: "Module 0.7: What is Networking?"
slug: prerequisites/zero-to-terminal/module-0.7-what-is-networking
sidebar:
  order: 8
revision_pending: false
---
> **Complexity**: `[QUICK]` - Absolute beginner
>
> **Time to Complete**: 90–120 minutes (long-form beginner read)
>
> **Prerequisites**: [Module 0.4: Files and Directories](../module-0.4-files-and-directories/) - You should be comfortable running commands and navigating directories.

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

Kubernetes makes this skill more important because it runs many pieces of software across many machines, then asks those pieces to find each other by name. A Pod receives an IP address, a Service gives a stable address and port, DNS maps names to Services, and `kubectl` talks to the API server over a secure port. You do not need to master cluster networking today, but you do need a reliable first model for what it means when one computer talks to another.

This module gives you that model from the terminal upward. You will learn what a network is, why IP addresses are not the same as ports, why DNS is useful but also a frequent failure point, and how HTTP status codes prove that a request reached an application. Then you will practice with `ping`, `curl`, and `nslookup`, which are ordinary tools that working engineers use when a dashboard is noisy and the fastest path forward is a small, careful test.

---

## What a Network Really Connects

A **network** is two or more computers connected so they can exchange information. That definition is deliberately plain because the essential idea is not a special cloud term; it is the same idea whether the computers are your laptop and printer on home Wi-Fi, two servers in a data center rack, or thousands of containers spread across a Kubernetes cluster. The difference is scale, reliability, and the number of systems helping messages move, not the basic goal.

Your home Wi-Fi is a local network, often called a LAN, where nearby devices share a router and can usually talk to one another directly. The internet is a much larger network of networks, where your router, your internet service provider, backbone networks, domain name systems, and destination servers all participate. When you visit `google.com`, your computer is not magically touching a website; it is sending packets through a chain of networking equipment until a server receives the request and sends a response.

Think of a large restaurant chain with an intercom system connecting kitchens. Each kitchen is a computer, each intercom endpoint is a network connection, and the wiring between locations is the network. A cook does not need to know every wire route to ask another kitchen about supplies, but someone responsible for operations needs enough vocabulary to tell the difference between a broken intercom, a wrong extension number, and a kitchen that received the call but cannot fulfill the request.

| Type | What It Is | Example |
|------|-----------|---------|
| **Local Network (LAN)** | Computers near each other, connected directly | Your laptop and printer on home Wi-Fi |
| **Internet (WAN)** | Computers anywhere in the world, connected through infrastructure | Your laptop talking to a server in Tokyo |

That distinction matters because a command can succeed in one network context and fail in another. Your laptop may reach a printer at home because both devices are on the same LAN, while a friend across town cannot reach that same printer because private home addresses are not routed across the public internet. In Kubernetes, the same pattern appears when one Pod can reach another inside the cluster, but a browser outside the cluster needs a Service, Ingress, LoadBalancer, or other published path.

A practical troubleshooting habit starts here: ask **which network path** you are testing. If you run a command from your laptop, you are testing the path from your laptop. If a Pod inside Kubernetes fails to reach a database, your laptop's success may not prove the Pod's path works. This is why engineers are careful about where they run a test, because the source of the request is part of the evidence.

```text
Laptop on Wi-Fi       Home router          Internet           Public server
192.168.1.42     ->   public gateway   ->   many networks  ->  203.0.113.55
     |                    |                                      |
local address       public address                         destination address
```

The diagram keeps the most important beginner idea visible: several addresses and systems are involved in one request. Your laptop may know its local address, your router may present a different public address to the internet, and the destination server has its own address. When troubleshooting, treating all of those as "the IP" hides the exact place where the request is failing.

Pause and predict: if your laptop can reach your router's settings page at `192.168.1.1` while the internet is disconnected, what does that prove, and what does it not prove? It proves your local network path to the router works. It does not prove that DNS, your internet provider, or any public website is reachable, because those are farther along a different path.

The goal is not to memorize every network layer today. The goal is to stop flattening every connectivity issue into "the network is broken." Once you can describe the path in pieces, you can use small terminal checks to learn whether the failure is local addressing, DNS name translation, port selection, firewall behavior, or an application response.

There is another habit hidden in this model: describe the expected path before you run the command. If you expect a request to leave your laptop, pass through home Wi-Fi, cross the public internet, resolve a name, and land on an HTTPS service, then each test can confirm or challenge one part of that expectation. Without that path in your head, commands become a pile of output instead of a structured investigation.

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
| What it does | Identifies one specific computer | Identifies one specific building |
| Who assigns it | Your router (for local) or your ISP (for internet) | The city planning office |

The first surprise is that not every IP address is meant for the whole internet. Private addresses are reserved for local networks, and routers do not publish them as globally reachable destinations. That reservation is standardized in RFC 1918, which defines private IPv4 ranges that many home networks, offices, and data centers use internally.

```text
192.168.x.x    (most common for home networks)
10.x.x.x       (common in offices and data centers)
172.16-31.x.x  (less common but valid)
```

Private addresses are like apartment numbers that only make sense inside one building. If you are standing in the lobby, "Apartment 8" may be enough information; if you are across the city, it is not. Similarly, `192.168.1.42` may identify your laptop inside your home, but someone on another network cannot route directly to it without a public address and a router rule that decides where inbound traffic should go.

Public addresses are different because they are routable on the internet. Your home router usually has one public address assigned by your internet service provider, while the devices behind the router use private addresses. The router uses Network Address Translation, or NAT, to keep track of outbound connections so many local devices can share one public address without each device needing a globally unique IPv4 address.

This is one reason "it works on my machine" can be true and still not help another person. A service bound to your laptop's private address may work from another device on the same Wi-Fi network, but it will not automatically work for a colleague elsewhere. The colleague needs a route to a public endpoint, and your router must know whether to forward that traffic to your laptop, which is rarely the default for good security reasons.

On macOS, the local Wi-Fi address is often available through `ipconfig`. Your interface name may differ if you are using Ethernet, a VPN, or a newer network setup, but `en0` is common enough for a first check on many Macs.

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

Before running this, what output do you expect: the same `192.168...` address your laptop uses locally, or a different address visible to the public internet? Most home and office networks return a different public address because NAT sits between your machine and the rest of the internet. If you are on a cloud VM or a specialized network, the answer can differ, which is exactly why evidence beats assumption.

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

The colon in `192.168.1.42:80` is not decoration. It separates the host address from the service port, and many tools use this combined form when you need to be precise. A request to the right IP on the wrong port is like arriving at the right building and knocking on a storage closet instead of the help desk.

| Port | Service | What It Does |
|------|---------|-------------|
| 80 | HTTP | Regular web traffic (when you visit a website) |
| 443 | HTTPS | Secure web traffic (the padlock in your browser) |
| 22 | SSH | Secure remote terminal access |
| 53 | DNS | Domain name lookups |
| 6443 | Kubernetes API | How `kubectl` talks to your cluster |

Ports also explain why a host can be reachable while an application is unavailable. A machine may reply to basic network probes but have no web server listening on port 80. Another machine may have HTTPS working on port 443 while SSH on port 22 is intentionally blocked by a firewall. The question is not only "can I reach the computer?" but also "can I reach the service I need?"

Hypothetical scenario: an internal dashboard was moved to a new VM, and someone copied the old hostname but forgot that the application now listens on port 8080 behind a reverse proxy. Basic ping checks succeed, and the server is not down, yet browsers fail when they try the default HTTPS path. The fix is not to reboot the network; the fix is to verify which process is listening on which port, then update the route or proxy configuration.

In Kubernetes, ports appear everywhere. Containers expose container ports, Services accept traffic on service ports, Services forward to target ports, and the API server commonly listens securely on port 6443. Those names will make more sense later, but the core idea is already here: Kubernetes does a lot of careful port mapping so callers do not need to know every container's changing details.

```text
Browser request         Kubernetes Service          Pod container
https://app.example ->  Service port 443      ->    target port 8080
      secure web              stable entry             app process
```

Pause and predict: imagine a server at `203.0.113.55` replies to `ping`, but `curl http://203.0.113.55` times out. Which fact did `ping` prove, and which fact remains unproven? It proved some network path to the host responds to ICMP traffic. It did not prove that an HTTP service is listening on port 80 or that a firewall allows that port.

A port can be closed, filtered, or open. Closed usually means the destination actively rejects the connection because no service is listening there. Filtered usually means a firewall drops or blocks the attempt, causing a timeout. Open means something accepted the connection, though the application may still return an error if the request is malformed or the backend is unhealthy.

For a beginner, the operational rule is simple: name the address and the port together when you discuss a network dependency. Saying "the database is at `10.0.5.50`" is incomplete if the application expects PostgreSQL on `5432`. Saying "the database is at `10.0.5.50:5432`" gives a teammate enough information to test the same destination and avoid accidentally checking a web port instead.

Ports also help you avoid blaming the wrong team. If an application is configured to call the right database address on the wrong port, the database team may see no meaningful traffic at all. If a firewall permits the address but denies the service port, the host can look alive while the application path still fails. When you include the port in your report, you give network, platform, and application engineers a shared target to verify.

Kubernetes makes this concrete through Service port mapping. A Service can receive traffic on one port and forward it to a different target port on the selected Pods. That is not a trick; it is a convenience that lets callers use a stable contract while the application process listens where it needs to listen. The tradeoff is that troubleshooters must check both sides of the mapping, because a mismatch can make the Service look correct while traffic lands on the wrong container port.

---

## DNS: Turning Names into Addresses

Humans are good at remembering names like `google.com`, `github.com`, and `api.example.com`. Computers route traffic using addresses, not friendly names, so there must be a translation step between what you type and where packets go. The **Domain Name System**, or DNS, performs that translation by answering questions such as "which IP address should I use for this name?"

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

A simplified DNS lookup has several steps. Your computer may first check local cache, then ask a configured resolver, often provided by your router, internet provider, operating system, or corporate network. That resolver may already know the answer from cache, or it may ask other DNS systems until it gets the address record it needs.

```text
1. You type: google.com
2. Your computer asks your router: "What's the IP for google.com?"
3. Your router asks a DNS server: "What's the IP for google.com?"
4. The DNS server responds: "142.250.80.46"
5. Your computer connects to 142.250.80.46
```

This usually happens so quickly that it feels invisible. That invisibility is convenient until DNS is the broken piece, because the visible symptom may look like a website or API outage. A browser saying it cannot find a server may mean the application is down, but it may also mean the name never resolved to an address.

The most useful beginner distinction is between a **name failure** and an **address failure**. If `nslookup api.example.com` says the name does not exist, you have not yet tested the server; you have tested the phone book entry. If `curl http://203.0.113.100` works against the known IP, you have evidence that the server and network path can work while DNS still needs repair.

DNS also involves caching. Records include a time-to-live, often abbreviated TTL, that tells resolvers how long they may keep an answer before checking again. A low TTL can make planned migrations easier because clients refresh sooner, while a high TTL can reduce lookup load but make stale answers linger after an address changes.

This is why DNS changes can feel inconsistent during cutovers. One user may receive the new address because their resolver refreshed, while another user keeps seeing the old address until cache expires. That does not require an invented outage story; it follows directly from how caching works, and it is one reason engineers plan DNS migrations instead of flipping records casually.

Kubernetes uses DNS heavily inside a cluster. Services receive names that workloads can use instead of chasing individual Pod IPs, and cluster DNS returns the current service address. You will learn the details later, but the beginner lesson transfers cleanly: a name is not the destination itself; it is a lookup that should produce a destination.

DNS failures are especially tempting to misread because they happen before the visible application conversation. If a name does not resolve, there may be no HTTP status code, no server log entry, and no useful application metric, because the request never found a destination. That absence of downstream evidence is itself useful. It tells you to inspect the name, resolver, zone, search suffix, or cache before changing the application.

The reverse mistake is also common: a name resolves successfully, so someone assumes DNS can be ignored. Resolution only tells you that a name produced an address; it does not guarantee the address is current, intended, reachable from every source, or serving the right application. When the result looks suspicious, compare the returned address with deployment notes, load balancer configuration, or the expected public endpoint before moving on.

---

## HTTP Responses and Terminal Evidence

Once DNS produces an address and a port accepts a connection, the application protocol still has to respond. For web traffic, that protocol is HTTP or HTTPS, and the response includes a status code. A status code is not a vague mood indicator; it is structured evidence about what happened after the server received the request.

`200 OK` means the server received the request and returned the requested resource. `404 Not Found` means the server was reachable, but the specific path did not exist. `500 Internal Server Error` means the server received the request but failed while processing it. Those outcomes point to different owners and different next checks, which is why status codes are so useful.

| Code | Meaning | Analogy |
|------|---------|---------|
| 200 | OK - here's what you asked for | "Order up! Here's your food." |
| 404 | Not found - that page doesn't exist | "Sorry, we don't have that dish on the menu." |
| 500 | Server error - something broke on their end | "The kitchen is on fire." |

The restaurant analogy is helpful if you keep the sequence straight. DNS is finding the restaurant address, the IP route is traveling to the restaurant, the port is choosing the correct counter, and HTTP is the conversation after you arrive. If the kitchen says the dish is not on the menu, your taxi route was not the problem.

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

`ping` sends small diagnostic messages and waits for replies. It is like knocking on a door to see whether anyone responds, but it is not the same as asking the web application for a page. Many systems intentionally ignore ping traffic, so a failed ping is a clue, not a final verdict.

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

The `-s` flag means silent mode, which hides the progress meter so the page content is easier to inspect. If the request succeeds, you may see raw HTML rather than the rendered page a browser would show. That raw output is useful because it proves the server returned content to a terminal client.

```html
<!doctype html>
<html>
<head>
    <title>Example Domain</title>
...
```

Fetching only headers is often cleaner when you only need status and metadata. A header request avoids dumping a full page into your terminal, and it shows the HTTP status line near the top. That makes it a fast check during a troubleshooting conversation.

```bash
$ curl -I example.com
HTTP/1.1 200 OK
Content-Type: text/html; charset=UTF-8
...
```

`nslookup` asks DNS to resolve a name manually. The exact output varies by operating system and resolver, but the shape is consistent: you see which DNS server answered and which address or addresses it returned. If a name fails here, fix the name or DNS record before blaming the web app.

```bash
$ nslookup google.com
Server:    192.168.1.1
Address:   192.168.1.1#53

Non-authoritative answer:
Name:   google.com
Address: 142.250.80.46
```

A careful check usually combines commands rather than relying on one. If DNS fails, use `nslookup` to confirm the name problem. If DNS works but HTTP fails, use `curl -I` to inspect the status or timeout. If ping fails but curl succeeds, remember that ICMP may be blocked while normal web traffic is allowed.

Which approach would you choose here and why: a user reports `api.example.com` is down, but you know the server's IP from deployment notes. Checking DNS first tells you whether the name maps to an address; checking `curl` against the known IP can separate DNS trouble from application trouble. The right sequence depends on the symptom, but the habit is the same: isolate one layer at a time.

There is a useful way to read command output under pressure: translate it into a sentence beginning with "this proves." `nslookup` returning an address proves the resolver has some mapping for the name. `ping` replies prove ICMP traffic received responses from a host or network endpoint. `curl -I` returning `200 OK` proves an HTTP server answered that request successfully. Each proof is narrow, and that narrowness is the point.

The opposite sentence is just as important: "this does not prove." A DNS answer does not prove the web app is healthy. Ping replies do not prove HTTPS works. A `404` does not prove routing is broken. A `500` does not prove the customer typed the wrong URL. Beginners often want one command that declares the whole system healthy or unhealthy, but real troubleshooting is usually a chain of smaller, honest claims.

When you write a handoff note, include both the command and your interpretation. For example, "`nslookup api.example.com` returned `203.0.113.100`, so DNS produced an address from my laptop's resolver; `curl -I` to that name returned `500`, so the request reached an HTTP server that failed internally." That note is more useful than "network checked" because it lets the next engineer see exactly which evidence exists and which questions remain open.

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

Another anti-pattern is treating a `404` as a network outage. A `404` means the server was reached and the application decided the requested path does not exist. That is often a route, URL, deployment, or content problem. If you tell a networking team that DNS is broken when the server is returning `404`, you send the investigation in the wrong direction.

For quick modules, the "when this does not apply" section is intentionally modest, but the habit scales. When later modules introduce SSH, servers, Kubernetes Services, and Ingress controllers, you will keep asking the same sequence of questions with more context. What name did the client use? What address did that name produce? Which port was attempted? Which protocol response came back? The vocabulary expands, but the reasoning pattern stays familiar.

---

## When You'd Use This vs Alternatives

Use beginner terminal checks when you need quick, local evidence and the system is simple enough that one command can answer one question. `nslookup`, `ping`, and `curl` are excellent first tools because they are available on many systems, easy to explain, and precise enough to prevent random changes. They are especially useful before escalating an issue, because a short command transcript can show what failed.

Use deeper tools when the first checks narrow the problem but do not explain it. Packet captures can reveal low-level traffic, cloud logs can show load balancer decisions, Kubernetes events can show Service and Endpoint changes, and application logs can explain `500` responses. Those tools are more powerful, but they are not replacements for the first question: what layer are we testing right now?

| Situation | First Tool | What It Can Tell You | Better Follow-Up If Needed |
|-----------|------------|----------------------|----------------------------|
| Hostname looks wrong | `nslookup` | Whether DNS returns an address | Check DNS provider records and TTL |
| Host may be unreachable | `ping -c 4` | Whether ICMP replies arrive | Test the actual application port |
| Website or API misbehaves | `curl -I` | HTTP status and headers | Inspect app logs, proxy logs, or routes |
| Local and public addresses differ | `curl -s ifconfig.me` | What public address the internet sees | Review NAT, firewall, or load balancer rules |
| Kubernetes API is unreachable | Full `kubectl` command output | Whether the client can reach the API server | Check cluster endpoint, credentials, and port 6443 |

For Kubernetes 1.35 and later, keep the same logic in mind when reading cluster documentation. A Service name depends on DNS, a Service port depends on port mapping, and `kubectl` depends on reaching the API server endpoint with the right credentials. Networking problems in Kubernetes can become complex, but they are still easier to approach when you preserve the distinction between name, address, port, and protocol response.

The alternative to this layered approach is usually tool hopping. Someone opens a cloud console, changes a security rule, restarts a deployment, flushes DNS, and reruns a browser test, all without knowing which layer changed the result. That may occasionally stumble into a fix, but it leaves the team with no explanation and no confidence. A short sequence of terminal checks is slower by seconds and faster by hours because it preserves cause and effect.

Use the deeper alternatives when the first evidence points there. If DNS resolves to the expected address and `curl` returns a `500`, application logs are a better next stop than more DNS commands. If the address and port time out from one network but work from another, firewall or routing evidence matters more than code changes. The beginner tools do not solve every issue; they tell you where a sharper tool belongs.

Keep this decision framework in your notes as a small checklist, not as a script you must follow blindly. Real systems sometimes skip a visible symptom, hide behind a proxy, or return a misleading error page, but the checklist still helps you ask one controlled question at a time. That discipline is what turns beginner commands into professional troubleshooting evidence.

---

## Did You Know?

1. **DNS replaced a hand-maintained host list.** Before DNS became standard in 1983, early internet hosts relied on a centrally distributed `HOSTS.TXT` file; as the network grew, that single-file approach stopped scaling. DNS was introduced in 1983, and the familiar hierarchical design most systems use today was documented in 1987 (RFC 1034).
2. **IPv4 has about 4.3 billion possible addresses.** That once sounded enormous, but the public internet, mobile devices, cloud platforms, and always-connected systems made address sharing and IPv6 adoption necessary.
3. **Ports have a standardized registry.** RFC 6335 describes how service names and port numbers are managed, which is why familiar services such as HTTP, HTTPS, DNS, and SSH have widely recognized default ports.
4. **Kubernetes has its own default API port.** The Kubernetes API server commonly uses secure port 6443, so beginner port reasoning applies directly when `kubectl` cannot reach a cluster.

---

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Forgetting `-c` with ping | On Linux and macOS, `ping` often keeps running until interrupted | Use `ping -c 4 host.example` or press **Ctrl+C** to stop a long-running probe |
| Pinging a site that blocks ICMP | Many servers and firewalls drop diagnostic ping traffic while allowing web traffic | Treat ping failure as a clue, then test the real service with `curl -I` |
| Confusing IP address and port | Both appear near each other in connection strings, so beginners merge them mentally | Say the full destination as `address:port`, such as `192.168.1.42:80` |
| Treating a private IP as publicly reachable | Addresses like `192.168.x.x` work inside a local network, not across the internet | Use a public endpoint, VPN, tunnel, or explicit router forwarding when remote access is intended |
| Forgetting the URL scheme with curl | `curl example.com` may not test the same protocol path as a browser using HTTPS | Be explicit with `curl http://example.com` or `curl https://example.com` |
| Assuming DNS failure means the server is down | A missing or stale DNS record can fail before traffic reaches the server | Test the known IP when appropriate, then repair the DNS record or cache plan |
| Calling every `404` a network problem | The server answered, but the requested path was not found | Check the URL path, route configuration, deployment, or application logs |
| Changing multiple layers at once | Pressure during an outage makes random edits feel productive | Change one thing at a time and rerun the same evidence-gathering command |

---

## Quiz

<details><summary>Question 1: Your friend says their new laptop's address is `192.168.1.42` and asks you to connect to it from your house. You try, but it fails. Based on the type of address provided, why did this not work?</summary>

`192.168.1.42` is a private IPv4 address, so it is meaningful only inside the local network where it was assigned. Your house and your friend's house are separate networks, and the public internet will not route directly to that private address. To make the laptop reachable remotely, your friend would need a public endpoint such as a VPN, tunnel, cloud host, or router forwarding rule that maps public traffic to the laptop. This diagnoses an address scope problem, not proof that the laptop itself is broken.

</details>

<details><summary>Question 2: You can successfully run `ping 203.0.113.55` and receive replies, but `curl http://203.0.113.55` times out. What layer is most likely still failing?</summary>

The ping result suggests that at least one network path to the host responds to ICMP traffic, but it does not prove a web service is available. `curl http://203.0.113.55` attempts HTTP on port 80, so the remaining failure is likely at the port, firewall, or web server layer. The host may be online while no process listens on port 80, or a firewall may allow ping while dropping HTTP. The next check should focus on the intended application port and service configuration.

</details>

<details><summary>Question 3: A user cannot access `api.example.com`. `nslookup api.example.com` says the name cannot be resolved, but `curl http://203.0.113.100` returns `200 OK`. What should you diagnose first?</summary>

The evidence points first to DNS resolution. The direct IP request proves that the server can respond over HTTP, so the application and at least one network path are working. The failed name lookup means clients cannot translate `api.example.com` into the address they need before connecting. You should inspect the DNS record, DNS zone, recent changes, and cache behavior before changing application code.

</details>

<details><summary>Question 4: A customer says the website is down. You run `curl -I https://example.com` and receive `500 Internal Server Error`. Is the first suspect DNS, the customer's internet, or the server-side application path?</summary>

The first suspect is the server-side application path. A `500` response means DNS resolved, the network connection reached the server or gateway, and the HTTP request was processed far enough for the server to return an error status. That does not guarantee every customer path is perfect, but it does show this test reached the application side. The next evidence should come from application logs, upstream dependency checks, or gateway logs rather than DNS records.

</details>

<details><summary>Question 5: A junior developer runs `ping -c 4 api.example.com`, sees only request timeouts, and declares the API server completely down. You run `curl -I https://api.example.com` and get `HTTP/1.1 200 OK`. Why was the conclusion wrong?</summary>

The conclusion treated ping as a complete application health check, which it is not. Ping uses ICMP, and many production systems ignore or block ICMP while still allowing HTTPS on port 443. The successful `curl` result proves the API hostname resolved, the HTTPS path reached a server, and the server returned a successful HTTP response. The accurate diagnosis is that ping traffic is blocked or ignored, not that the API is down.

</details>

<details><summary>Question 6: An application should connect to a database at `10.0.5.50:5432`, but the logs say `Connection refused to 10.0.5.50 on port 80`. What is the most likely configuration error?</summary>

The application is using the correct host address but the wrong port. Port 80 is the conventional HTTP port, while the expected database endpoint in the scenario is port 5432. A connection refused error often means the destination rejected the attempt because no service is listening on that port. Fix the connection string or environment configuration so the application targets `10.0.5.50:5432`.

</details>

<details><summary>Question 7: Your team launched `promo.company.com`, but `nslookup promo.company.com` returns `NXDOMAIN`. The lead engineer says the server is running at `198.51.100.22`. What system needs attention?</summary>

The DNS records for the domain need attention. `NXDOMAIN` means the requested name does not exist in DNS from the resolver's point of view, so clients cannot discover the server address by using the hostname. The server may be healthy at `198.51.100.22`, but the public name has no usable mapping yet. Create or correct the DNS record, then account for TTL and resolver cache timing.

</details>

---

## Hands-On Exercise: Exploring the Network

### Objective

Use networking commands to explore connections, look up addresses, fetch web content, and record what each command proves. The point is not to memorize output perfectly, because networks differ. The point is to practice reading each result as evidence about DNS, address reachability, ports, or HTTP response behavior.

### Setup

Create a small practice directory so any files from the exercise are easy to find later. The command below is intentionally ordinary shell practice rather than Kubernetes practice, because this module is about network basics from your terminal.

```bash
$ mkdir -p ~/kubedojo-practice
$ cd ~/kubedojo-practice
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

Write down the local address and label it as local, not public. If you see multiple addresses, you may have multiple network interfaces, a VPN, or container networking on the machine. For this exercise, identify the address associated with your normal internet connection.

</details>

4. **Discover your public IP address.** Use `curl` in silent mode to fetch the page at `ifconfig.me`. Compare this result with your local address and explain why they are usually different on a home or office network.

```bash
$ curl -s ifconfig.me
```

<details><summary>Solution notes</summary>

The public result is the address an external service sees for your request. On many networks, this is your router, firewall, VPN, or provider edge address rather than your laptop's private address. If the value matches your local address, you may be on a network that gives your machine a public address directly.

</details>

5. **Manually resolve a domain name.** Use `nslookup` to find an address for `github.com`. Locate the answer section and write down one returned IP address, knowing that large sites can return different valid answers depending on geography and resolver behavior.

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

A `200 OK` status means the request reached a server that returned the requested resource successfully. If you see a redirect status instead, that is still useful HTTP evidence; it means the server responded with instructions to use a different location.

</details>

8. **Trigger a specific HTTP error code.** Request headers for a path that should not exist on `example.com`. Your goal is to see that a `404` is an application-level response, not a DNS failure.

```bash
$ curl -I example.com/this-page-does-not-exist
```

<details><summary>Solution notes</summary>

A `404` proves the server was reachable enough to answer the request, but the requested path did not exist. That is a very different diagnosis from a name lookup failure or a connection timeout.

</details>

9. **Combine networking with file skills.** Fetch the raw HTML of `example.com` silently, redirect it into a file called `my-first-webpage.html`, and then print the file to confirm it contains the response body.

```bash
$ curl -s example.com > my-first-webpage.html
$ cat my-first-webpage.html
```

<details><summary>Solution notes</summary>

This step connects terminal networking with file redirection. The command writes the HTTP response body into a local file, and `cat` confirms that the file contains HTML. If the file is empty, rerun the command without `-s` or inspect the exit status and network response.

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
- [ ] Explain how Kubernetes Service names, Pod IPs, and API server port 6443 map to DNS, address, port, and protocol response.

---

## Sources

- [RFC 1918: Address Allocation for Private Internets](https://www.rfc-editor.org/rfc/rfc1918)
- [RFC 6335: Service Name and Transport Protocol Port Number Registry Procedures](https://www.rfc-editor.org/rfc/rfc6335)
- [Kubernetes API Access Control](https://kubernetes.io/docs/reference/access-authn-authz/controlling-access/)
- [RFC 1034: Domain Names - Concepts and Facilities](https://www.rfc-editor.org/rfc/rfc1034)
- [RFC 883: Domain Names - Implementation and Specification](https://www.rfc-editor.org/rfc/rfc883)
- [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110)
- [Kubernetes Ports and Protocols](https://kubernetes.io/docs/reference/ports-and-protocols/)
- [RFC 8200: Internet Protocol, Version 6 Specification](https://www.rfc-editor.org/rfc/rfc8200)
- [RFC 9293: Transmission Control Protocol](https://www.rfc-editor.org/rfc/rfc9293)
- [RFC 768: User Datagram Protocol](https://www.rfc-editor.org/rfc/rfc768)
- [IANA Service Name and Transport Protocol Port Number Registry](https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml)
- [curl command line tool manual](https://curl.se/docs/manpage.html)

## Next Module

**Next Module**: [Module 0.8: Servers and SSH](../module-0.8-servers-and-ssh/) - Learn what a server is, where servers live, and how to connect to them remotely.
