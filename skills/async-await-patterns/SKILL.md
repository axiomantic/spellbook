---
name: async-await-patterns
description: Use when writing JavaScript or TypeScript code with asynchronous operations
---

# Async/Await Patterns

Use async/await for ALL asynchronous operations instead of raw promises, callbacks, or blocking patterns.

## Standard Pattern

```typescript
async function operationName(): Promise<ReturnType> {
  try {
    const result = await asynchronousOperation();
    return result;
  } catch (error) {
    // Proper error handling
    throw error;
  }
}
```

## Before Writing Async Code

1. Is this operation asynchronous? (API calls, file I/O, timers, database queries)
2. Did I mark the containing function as `async`?
3. Did I use `await` for every promise-returning operation?
4. Did I add proper try-catch error handling?
5. Did I avoid mixing async/await with `.then()/.catch()`?

## Core Rules

- ALWAYS mark functions containing asynchronous operations as `async`
- ALWAYS use `await` for promise-returning operations
- ALWAYS wrap await operations in try-catch blocks
- NEVER mix async/await with .then()/.catch() chains in the same function
- NEVER use callbacks when async/await is available

## Forbidden Patterns

### 1. Raw Promise Chains

```typescript
// BAD
function fetchData() {
  return fetch('/api/data')
    .then(response => response.json())
    .then(data => processData(data))
    .catch(error => handleError(error));
}

// CORRECT
async function fetchData() {
  try {
    const response = await fetch('/api/data');
    const data = await response.json();
    return processData(data);
  } catch (error) {
    handleError(error);
    throw error;
  }
}
```

### 2. Missing await

```typescript
// BAD - returns Promise instead of value
async function getData() {
  const data = fetchFromDatabase(); // Forgot await!
  return data.id;
}

// CORRECT
async function getData() {
  const data = await fetchFromDatabase();
  return data.id;
}
```

### 3. Missing async Keyword

```typescript
// BAD - SyntaxError
function loadUser() {
  const user = await database.getUser();
  return user;
}

// CORRECT
async function loadUser() {
  const user = await database.getUser();
  return user;
}
```

### 4. Missing Error Handling

```typescript
// BAD - unhandled promise rejection if save fails
async function saveData(data) {
  const result = await database.save(data);
  return result;
}

// CORRECT
async function saveData(data) {
  try {
    const result = await database.save(data);
    return result;
  } catch (error) {
    console.error('Save failed:', error);
    throw new Error('Failed to save data');
  }
}
```

### 5. Mixing Patterns

```typescript
// BAD - inconsistent
async function processUser() {
  const user = await getUser();
  return updateUser(user)
    .then(result => result.data)
    .catch(error => console.error(error));
}

// CORRECT - consistent async/await
async function processUser() {
  try {
    const user = await getUser();
    const result = await updateUser(user);
    return result.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}
```

## Advanced Patterns

### Parallel Operations

```typescript
async function loadDashboard() {
  const [user, stats, notifications] = await Promise.all([
    fetchUser(),
    fetchStats(),
    fetchNotifications()
  ]);
  return { user, stats, notifications };
}
```

### Sequential Operations

```typescript
async function checkout() {
  const inventory = await checkInventory();
  const payment = await processPayment(inventory);
  const order = await createOrder(payment);
  return order;
}
```

### When Some Operations May Fail

```typescript
const results = await Promise.allSettled([op1(), op2(), op3()]);
// Each result has { status: 'fulfilled', value } or { status: 'rejected', reason }
```

## Self-Check Before Submitting

- [ ] Did I mark the function as `async`?
- [ ] Did I use `await` for EVERY promise-returning operation?
- [ ] Did I wrap await operations in try-catch blocks?
- [ ] Did I avoid using .then()/.catch() chains?
- [ ] Did I avoid using callbacks when async/await is available?
- [ ] Did I consider whether operations can run in parallel with Promise.all()?
- [ ] Did I provide meaningful error messages in catch blocks?
