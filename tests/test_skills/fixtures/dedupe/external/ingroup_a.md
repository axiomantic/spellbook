---
name: ingroup-a
description: "External-caller fixture: in-group file A holding the EXTRACT candidate."
---

The deployment runbook instructs the operator to drain the connection pool, flip
the load balancer to the standby fleet, and confirm health checks are green
before promoting the new release across every regional cluster.
