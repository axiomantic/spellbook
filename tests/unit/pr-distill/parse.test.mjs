import { describe, it, expect } from 'vitest';
import { ErrorCode } from '../../../lib/pr-distill/errors.js';
import { parseDiff, parseFileChunk } from '../../../lib/pr-distill/parse.js';

describe('parseFileChunk', () => {
  it('should parse a simple added file', () => {
    const chunk = `diff --git a/src/newfile.js b/src/newfile.js
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/src/newfile.js
@@ -0,0 +1,3 @@
+function hello() {
+  return 'world';
+}`;

    const result = parseFileChunk(chunk);

    expect(result.path).toBe('src/newfile.js');
    expect(result.oldPath).toBeNull();
    expect(result.status).toBe('added');
    expect(result.additions).toBe(3);
    expect(result.deletions).toBe(0);
    expect(result.hunks).toHaveLength(1);
    expect(result.hunks[0].oldStart).toBe(0);
    expect(result.hunks[0].oldCount).toBe(0);
    expect(result.hunks[0].newStart).toBe(1);
    expect(result.hunks[0].newCount).toBe(3);
  });

  it('should parse a modified file', () => {
    const chunk = `diff --git a/src/index.js b/src/index.js
index abc123..def456 100644
--- a/src/index.js
+++ b/src/index.js
@@ -1,3 +1,5 @@
+// New comment
 function test() {
-  return 1;
+  return 2;
 }`;

    const result = parseFileChunk(chunk);

    expect(result.path).toBe('src/index.js');
    expect(result.oldPath).toBeNull();
    expect(result.status).toBe('modified');
    expect(result.additions).toBe(2);
    expect(result.deletions).toBe(1);
    expect(result.hunks).toHaveLength(1);
    expect(result.hunks[0].oldStart).toBe(1);
    expect(result.hunks[0].oldCount).toBe(3);
    expect(result.hunks[0].newStart).toBe(1);
    expect(result.hunks[0].newCount).toBe(5);
  });

  it('should parse a deleted file', () => {
    const chunk = `diff --git a/src/oldfile.js b/src/oldfile.js
deleted file mode 100644
index abc123..0000000
--- a/src/oldfile.js
+++ /dev/null
@@ -1,2 +0,0 @@
-function old() {
-}`;

    const result = parseFileChunk(chunk);

    expect(result.path).toBe('src/oldfile.js');
    expect(result.status).toBe('deleted');
    expect(result.additions).toBe(0);
    expect(result.deletions).toBe(2);
  });

  it('should parse a renamed file', () => {
    const chunk = `diff --git a/src/old-name.js b/src/new-name.js
similarity index 95%
rename from src/old-name.js
rename to src/new-name.js
index abc123..def456 100644
--- a/src/old-name.js
+++ b/src/new-name.js
@@ -1,3 +1,3 @@
 function test() {
-  return 'old';
+  return 'new';
 }`;

    const result = parseFileChunk(chunk);

    expect(result.path).toBe('src/new-name.js');
    expect(result.oldPath).toBe('src/old-name.js');
    expect(result.status).toBe('renamed');
    expect(result.additions).toBe(1);
    expect(result.deletions).toBe(1);
  });

  it('should parse hunk lines with correct line numbers', () => {
    const chunk = `diff --git a/src/index.js b/src/index.js
index abc123..def456 100644
--- a/src/index.js
+++ b/src/index.js
@@ -10,4 +10,5 @@
 function existing() {
   return true;
 }
+// new line
`;

    const result = parseFileChunk(chunk);

    const hunk = result.hunks[0];
    expect(hunk.lines).toHaveLength(4);

    // Context line
    expect(hunk.lines[0].type).toBe('context');
    expect(hunk.lines[0].content).toBe('function existing() {');
    expect(hunk.lines[0].oldLineNum).toBe(10);
    expect(hunk.lines[0].newLineNum).toBe(10);

    // More context
    expect(hunk.lines[1].type).toBe('context');
    expect(hunk.lines[1].oldLineNum).toBe(11);
    expect(hunk.lines[1].newLineNum).toBe(11);

    // Context
    expect(hunk.lines[2].type).toBe('context');
    expect(hunk.lines[2].oldLineNum).toBe(12);
    expect(hunk.lines[2].newLineNum).toBe(12);

    // Added line
    expect(hunk.lines[3].type).toBe('add');
    expect(hunk.lines[3].content).toBe('// new line');
    expect(hunk.lines[3].oldLineNum).toBeNull();
    expect(hunk.lines[3].newLineNum).toBe(13);
  });

  it('should parse removed lines with correct line numbers', () => {
    const chunk = `diff --git a/src/index.js b/src/index.js
index abc123..def456 100644
--- a/src/index.js
+++ b/src/index.js
@@ -5,4 +5,3 @@
 function test() {
   return 1;
-  // removed comment
 }`;

    const result = parseFileChunk(chunk);
    const hunk = result.hunks[0];

    const removedLine = hunk.lines.find(l => l.type === 'remove');
    expect(removedLine).toBeDefined();
    expect(removedLine.content).toBe('  // removed comment');
    expect(removedLine.oldLineNum).toBe(7);
    expect(removedLine.newLineNum).toBeNull();
  });

  it('should detect binary files', () => {
    const chunk = `diff --git a/image.png b/image.png
new file mode 100644
index 0000000..abc1234
Binary files /dev/null and b/image.png differ`;

    const result = parseFileChunk(chunk);

    expect(result.path).toBe('image.png');
    expect(result.status).toBe('added');
    expect(result.hunks).toHaveLength(0);
    // Binary files should have 0 additions/deletions since we can't count lines
    expect(result.additions).toBe(0);
    expect(result.deletions).toBe(0);
  });

  it('should handle multiple hunks in one file', () => {
    const chunk = `diff --git a/src/large.js b/src/large.js
index abc123..def456 100644
--- a/src/large.js
+++ b/src/large.js
@@ -1,3 +1,4 @@
+// header comment
 function one() {
   return 1;
 }
@@ -50,4 +51,5 @@
 function fifty() {
   return 50;
 }
+// footer comment`;

    const result = parseFileChunk(chunk);

    expect(result.hunks).toHaveLength(2);

    expect(result.hunks[0].oldStart).toBe(1);
    expect(result.hunks[0].newStart).toBe(1);

    expect(result.hunks[1].oldStart).toBe(50);
    expect(result.hunks[1].newStart).toBe(51);
  });
});

describe('parseDiff', () => {
  it('should parse empty diff', () => {
    const result = parseDiff('');
    expect(result).toEqual({ files: [], warnings: [] });
  });

  it('should parse diff with single file', () => {
    const diff = `diff --git a/src/index.js b/src/index.js
index abc123..def456 100644
--- a/src/index.js
+++ b/src/index.js
@@ -1,3 +1,4 @@
+// comment
 function test() {
   return 1;
 }`;

    const result = parseDiff(diff);

    expect(result.files).toHaveLength(1);
    expect(result.files[0].path).toBe('src/index.js');
    expect(result.files[0].status).toBe('modified');
    expect(result.warnings).toHaveLength(0);
  });

  it('should parse diff with multiple files', () => {
    const diff = `diff --git a/src/one.js b/src/one.js
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/src/one.js
@@ -0,0 +1,2 @@
+function one() {
+}
diff --git a/src/two.js b/src/two.js
index abc123..def456 100644
--- a/src/two.js
+++ b/src/two.js
@@ -1,2 +1,3 @@
 function two() {
+  return 2;
 }
diff --git a/src/three.js b/src/three.js
deleted file mode 100644
index xyz789..0000000
--- a/src/three.js
+++ /dev/null
@@ -1,2 +0,0 @@
-function three() {
-}`;

    const result = parseDiff(diff);

    expect(result.files).toHaveLength(3);

    expect(result.files[0].path).toBe('src/one.js');
    expect(result.files[0].status).toBe('added');

    expect(result.files[1].path).toBe('src/two.js');
    expect(result.files[1].status).toBe('modified');

    expect(result.files[2].path).toBe('src/three.js');
    expect(result.files[2].status).toBe('deleted');

    expect(result.warnings).toHaveLength(0);
  });

  it('should correctly count total additions and deletions', () => {
    const diff = `diff --git a/src/file.js b/src/file.js
index abc123..def456 100644
--- a/src/file.js
+++ b/src/file.js
@@ -1,5 +1,6 @@
+// new
 function test() {
-  return 1;
+  return 2;
+  // another
 }`;

    const result = parseDiff(diff);

    expect(result.files[0].additions).toBe(3);
    expect(result.files[0].deletions).toBe(1);
  });

  it('should handle files with spaces in path', () => {
    const diff = `diff --git a/src/my file.js b/src/my file.js
index abc123..def456 100644
--- a/src/my file.js
+++ b/src/my file.js
@@ -1 +1,2 @@
 test
+added`;

    const result = parseDiff(diff);

    expect(result.files).toHaveLength(1);
    expect(result.files[0].path).toBe('src/my file.js');
  });

  it('should handle diff with only binary files', () => {
    const diff = `diff --git a/image1.png b/image1.png
new file mode 100644
index 0000000..abc1234
Binary files /dev/null and b/image1.png differ
diff --git a/image2.jpg b/image2.jpg
index abc123..def456 100644
Binary files a/image2.jpg and b/image2.jpg differ`;

    const result = parseDiff(diff);

    expect(result.files).toHaveLength(2);
    expect(result.files[0].path).toBe('image1.png');
    expect(result.files[0].status).toBe('added');
    expect(result.files[1].path).toBe('image2.jpg');
    expect(result.files[1].status).toBe('modified');
  });
});
