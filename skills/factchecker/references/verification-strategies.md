# Verification Strategies by Agent

This reference documents verification approaches for each specialized agent.

---

## SecurityAgent

Responsible for: XSS, injection, authentication, sanitization, hashing, encryption claims.

### Claim: "Input is sanitized"

**Shallow:**
- Check for sanitization function calls near the claim
- Look for known libraries (DOMPurify, sanitize-html, bleach)

**Medium:**
- Trace input from entry point to usage
- Verify sanitization happens BEFORE any dangerous operations
- Check sanitization function implementation

**Deep:**
- Test with known XSS payloads
- Run static analysis tools (semgrep, eslint-plugin-security)
- Check for bypass patterns

**Evidence sources:**
- OWASP XSS Prevention Cheat Sheet
- OWASP Input Validation Cheat Sheet
- CWE-79 documentation

### Claim: "SQL injection safe" / "parameterized queries"

**Shallow:**
- Look for parameterized query syntax (`$1`, `?`, `:param`)
- Check for ORM usage (Prisma, SQLAlchemy, ActiveRecord)

**Medium:**
- Trace all database queries in the function
- Verify no string concatenation in queries
- Check for raw query escapes

**Deep:**
- Run sqlmap or similar tools against test endpoints
- Static analysis for SQL injection patterns
- Review all query builders

**Evidence sources:**
- OWASP SQL Injection Prevention
- CWE-89 documentation

### Claim: "Passwords hashed with bcrypt/argon2/scrypt"

**Shallow:**
- Check imports for hashing libraries
- Look for hash function calls

**Medium:**
- Trace password from input to storage
- Verify cost factor/work factor settings
- Check no plaintext storage paths

**Deep:**
- Inspect actual database records (if accessible)
- Verify password verification uses timing-safe comparison
- Check for password in logs

**Evidence sources:**
- OWASP Password Storage Cheat Sheet
- Have I Been Pwned API for known weak hash detection

### Claim: "Cryptographically random" / "secure random"

**Shallow:**
- Check for crypto.randomBytes, secrets module, SecureRandom
- Flag Math.random(), random.random() as insecure

**Medium:**
- Trace random value generation to usage
- Verify sufficient entropy (token length)

**Deep:**
- Statistical randomness tests on generated values
- Check seeding mechanism

---

## CorrectnessAgent

Responsible for: Behavior claims, return values, exceptions, invariants, state, side effects.

### Claim: "Returns X when Y"

**Shallow:**
- Find the code path for condition Y
- Check return statement matches X

**Medium:**
- Trace all code paths that could trigger condition Y
- Verify no early returns or exceptions bypass expected return
- Check for async/promise handling

**Deep:**
- Write and execute test case
- Fuzz inputs around boundary conditions
- Check error handling paths

### Claim: "Throws/raises when X"

**Shallow:**
- Find throw/raise statement for condition X
- Verify exception type matches claim

**Medium:**
- Trace all paths to the throw
- Check exception isn't caught and swallowed
- Verify error message accuracy

**Deep:**
- Execute with condition X, verify exception
- Test boundary conditions
- Check exception propagation

### Claim: "Never null after initialization"

**Shallow:**
- Check constructor/initializer sets the field
- Look for nullability annotations

**Medium:**
- Trace all assignments to the field
- Check for conditional initialization
- Verify no methods set to null

**Deep:**
- Add runtime assertions
- Test with various initialization paths
- Check serialization/deserialization

### Claim: "Pure function" / "No side effects"

**Shallow:**
- Check function modifies no external state
- Look for I/O, global variables, mutations

**Medium:**
- Trace all function calls within
- Verify memoization compatibility
- Check for hidden state (closures)

**Deep:**
- Call function multiple times, verify same output
- Check no external state changes
- Verify referential transparency

### Claim: "Idempotent"

**Shallow:**
- Check function can be called multiple times safely
- Look for guards against repeat operations

**Medium:**
- Trace state changes
- Verify database operations are idempotent (UPSERT vs INSERT)

**Deep:**
- Execute multiple times, verify same result
- Check side effects don't accumulate

---

## PerformanceAgent

Responsible for: Complexity claims, benchmarks, caching, memory, performance numbers.

### Claim: "O(n)" / "O(log n)" / complexity claims

**Shallow:**
- Analyze loop structures
- Count nested iterations

**Medium:**
- Trace recursive calls
- Analyze data structure operations (hash lookups, tree traversals)
- Check for hidden complexity in function calls

**Deep:**
- Benchmark with varying input sizes
- Plot results to verify complexity curve
- Profile with large datasets

**Evidence sources:**
- Big-O Cheat Sheet
- Algorithm complexity references

### Claim: "Cached for X minutes/seconds"

**Shallow:**
- Find cache implementation
- Check TTL configuration

**Medium:**
- Trace cache key generation
- Verify cache invalidation logic
- Check cache hit/miss paths

**Deep:**
- Measure actual cache duration
- Test cache invalidation
- Monitor cache hit rates

### Claim: "X ms latency" / performance numbers

**Shallow:**
- Look for performance tests/benchmarks
- Check for previous measurements

**Medium:**
- Profile the code path
- Identify bottlenecks

**Deep:**
- Run benchmarks under realistic conditions
- Measure p50, p95, p99 latencies
- Compare to claimed numbers

### Claim: "Lazy loaded" / "Deferred"

**Shallow:**
- Check for lazy initialization patterns
- Look for getter with initialization

**Medium:**
- Trace initialization timing
- Verify no eager initialization paths

**Deep:**
- Profile startup, verify deferred loading
- Measure memory before/after

---

## ConcurrencyAgent

Responsible for: Thread-safety, atomicity, lock-free, wait-free, reentrant claims.

### Claim: "Thread-safe"

**Shallow:**
- Check for synchronization primitives (locks, mutexes)
- Look for atomic operations
- Check for immutable data structures

**Medium:**
- Identify all shared mutable state
- Verify all access is synchronized
- Check for lock ordering (deadlock prevention)

**Deep:**
- Run with thread sanitizer (TSan)
- Stress test with concurrent access
- Check for race conditions with tooling

**Evidence sources:**
- Language memory model documentation
- Concurrency best practices guides

### Claim: "Atomic"

**Shallow:**
- Check for atomic types (AtomicInteger, atomic.Value)
- Look for compare-and-swap operations

**Medium:**
- Verify operation is single atomic instruction or properly synchronized
- Check for ABA problems

**Deep:**
- Test under high contention
- Verify with memory ordering tests

### Claim: "Lock-free"

**Shallow:**
- Verify no locks/mutexes in code path
- Check for CAS-based algorithms

**Medium:**
- Analyze for blocking operations
- Verify progress guarantee

**Deep:**
- Benchmark under contention
- Verify threads make progress independently

### Claim: "Wait-free"

**Shallow:**
- Check algorithm structure
- Look for bounded operations

**Medium:**
- Verify bounded number of steps per operation
- No spinning or retry loops

**Deep:**
- Measure worst-case latency
- Verify constant-time completion

### Claim: "Reentrant"

**Shallow:**
- Check for recursive lock usage
- Verify no global state modification

**Medium:**
- Trace execution for self-calls
- Check signal handler safety

**Deep:**
- Test recursive invocation
- Verify no deadlock on reentry

---

## DocumentationAgent

Responsible for: README accuracy, example code, API docs, external links, test coverage claims.

### Claim: Example code in documentation

**Shallow:**
- Check syntax validity
- Verify imports exist

**Medium:**
- Check API signatures match current code
- Verify function names and parameters

**Deep:**
- Execute example code
- Verify output matches documentation

### Claim: "See tests in test_foo.py"

**Shallow:**
- Verify file exists
- Check for related test functions

**Medium:**
- Read tests, verify they test claimed behavior
- Check test assertions match claims

**Deep:**
- Run the tests
- Verify coverage of claimed functionality

### Claim: External URL references

**Shallow:**
- Check URL format validity

**Medium:**
- Fetch URL, verify it's accessible
- Check content is relevant

**Deep:**
- Verify linked content supports the claim
- Check for outdated information

---

## HistoricalAgent

Responsible for: TODOs, FIXMEs, issue references, deprecation, workaround rationale.

### Claim: "TODO: remove after #123"

**Shallow:**
- Check issue/PR exists

**Medium:**
- Check issue status (open/closed)
- Check age of the TODO

**Deep:**
- Review issue resolution
- Determine if workaround is still needed

### Claim: "Workaround for X bug"

**Shallow:**
- Search for bug reference

**Medium:**
- Check if bug is fixed in current versions
- Verify workaround is still necessary

**Deep:**
- Test without workaround
- Verify bug status in issue tracker

### Claim: "Deprecated since vX.Y"

**Shallow:**
- Check version history
- Verify deprecation notice

**Medium:**
- Find replacement recommendation
- Check usage in codebase

**Deep:**
- Verify deprecation warnings are emitted
- Check migration path exists

---

## ConfigurationAgent

Responsible for: Defaults, environment variables, config files, version requirements.

### Claim: "Defaults to X"

**Shallow:**
- Find default value in code
- Check matches claimed value

**Medium:**
- Trace configuration loading
- Verify no overrides change default

**Deep:**
- Run without configuration, verify behavior
- Test default in various environments

### Claim: "Env var X controls Y"

**Shallow:**
- Find environment variable usage
- Check variable name matches

**Medium:**
- Trace from env var to behavior Y
- Verify parsing and validation

**Deep:**
- Set env var, verify behavior change
- Test with invalid values

### Claim: "Requires Node 18+" / version requirements

**Shallow:**
- Check package.json engines field
- Look for version-specific APIs

**Medium:**
- Identify version-specific features used
- Check compatibility tables

**Deep:**
- Test on specified minimum version
- Test on older version (should fail)

---

## DocumentationAgent: Missing Facts Verification

### Strategy: Context Gap Detection

**Shallow:** Read 3-7 lines around claim, check for required context keywords

**Medium:** Semantic search within section, verify claim accuracy first

**Deep:** Analyze implementation, identify specific missing information

### Strategy: Completeness Gap Detection

**Shallow:** Count documented vs actual params, check for @returns/@throws

**Medium:** Parse function signature vs docs, check for error documentation

**Deep:** Execute examples, test edge cases mentioned in code but not docs

**INCOMPLETE verdict:** Base claim accurate but missing critical context

---

## CorrectnessAgent: Extraneous Information Verification

### Strategy: Code-Restating Comment Detection

**Shallow:** Compare comment to adjacent code, check for operation keywords

**Medium:** Analyze comment for WHY vs WHAT, check for non-obvious details

**Deep:** Contextual analysis of code complexity, determine if comment adds understanding

### Strategy: LLM Pattern Detection

**Shallow:** Pattern match against known LLM phrases

**Medium:** Verify if comment provides actionable information

### Strategy: Verbose Text Detection

**Shallow:** Calculate repetition score (30% threshold) and hedging score (20% threshold)

**Medium:** Generate simplified version preserving meaning

**EXTRANEOUS verdict:** Content adds no value, can be removed/simplified
**REFUTED verdict:** Content appears extraneous but has hidden value

---

## Web Search Guidelines

For all agents, when searching the web:

1. **Prefer authoritative sources:**
   - Official documentation
   - OWASP, CWE, NIST for security
   - RFCs for protocol claims
   - Peer-reviewed papers

2. **Verify currency:**
   - Check publication/update date
   - Cross-reference multiple sources

3. **Document source:**
   - Full URL
   - Relevant excerpt
   - Access date

4. **Avoid:**
   - Stack Overflow answers without verification
   - Outdated blog posts
   - Unattributed claims
