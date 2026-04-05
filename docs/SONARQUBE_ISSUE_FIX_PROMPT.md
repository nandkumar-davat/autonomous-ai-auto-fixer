# SonarQube Issue Fix Process - Reusable Prompt

**Purpose**: Systematically analyze and fix high-priority bugs and vulnerabilities from SonarQube scan results, focusing on maintaining code quality and security.

---

## Instructions to Assistant:

Please follow this exact 5-step process for SonarQube issue analysis and fixes:

### Step 1: Access SonarQube Scan File
- Locate the SonarQube scan JSON file (typically matching the pattern `EAR-AA-*_issueStatuses-OPEN-CONFIRMED.json` in the `manual-scan-report` directory)
- Parse the JSON results and focus on the `issues` array
- Identify the project structure and the specific components (files) affected

**Expected JSON Structure** (single issue record from `issues[]`):

    {
      "key": "uuid-here",
      "rule": "csharpsquid:S3649",
      "severity": "CRITICAL",
      "component": "ProjectName:Path/To/File.cs",
      "line": 42,
      "message": "Description of the issue",
      "type": "VULNERABILITY",
      "status": "OPEN",
      "impacts": [{ "softwareQuality": "SECURITY", "severity": "HIGH" }],
      "cleanCodeAttribute": "TRUSTWORTHY",
      "cleanCodeAttributeCategory": "RESPONSIBLE"
    }

### Step 2: Extract High-Priority Issues
Filter the `issues` array for the following criteria (Type = BUG/VULNERABILITY, Severity = BLOCKER/CRITICAL):
- **TYPE**: Only include `BUG` and `VULNERABILITY`
- **SEVERITY**: Focus on `BLOCKER` and `CRITICAL` (process `MAJOR` only if required by the user)

> **Note**: Most issues in SonarQube reports may be `CODE_SMELL` — filter strictly by the type and severity criteria above.

For each relevant issue, document:
- **Key**: Issue unique identifier
- **Rule**: SonarQube Rule ID (e.g., `csharpsquid:S3649` for SQL injection, `csharpsquid:S2092` for cookie security)
- **Component**: The file path
- **Line**: The specific line number
- **Message**: The description of the problem
- **Status**: (OPEN/CONFIRMED)
- **Impacts**: Software quality and severity from the `impacts` array
- **Clean Code Category**: `cleanCodeAttribute` and `cleanCodeAttributeCategory` for additional fix context

### Step 3: Fix Issues One by One (Priority Order: BLOCKER → CRITICAL → MAJOR if requested)
Work through issues in priority order:

For each issue:
1. **Analyze the Problem**:
   - Locate the file identified in `component` (strip the project prefix before the colon to get the relative file path, e.g., `ProjectName:Path/To/File.cs` → `Path/To/File.cs`)
   - Go to the specific `line` mentioned
   - Understand the `message` and the `rule` to determine the correct fix
   
2. **Implement the Fix**:
   - Modify the code to resolve the issue while preserving surrounding logic
   - Ensure the fix follows best practices for the specific language/framework
   - If the fix requires multiple lines (e.g., refactoring), ensure all related code is updated

3. **Document the Change**:
   - Note the issue key and rule addressed
   - Explain what was changed and why
   - Specify the file and line range affected

4. **Verify the Fix**:
   - Ensure the logic remains correct
   - Check for any side effects or breaking changes

### Step 4: Summary of Fixes
After all fixes are implemented, provide a comprehensive summary:

```markdown
## SonarQube Fixes Applied - [Date]

### Blocker/Critical Issues Fixed
- **[Key]**: [Rule] - [File]:[Line] - [Message]
  - Fix: [Brief description of the change]

### Files Modified
- [List all files that were changed]

### Fix Statistics
- Total Blockers fixed: [X]
- Total Criticals fixed: [Y]
- Total Vulnerabilities resolved: [Z]
- Total Bugs resolved: [W]
```

### Step 5: Git Commit Message
Provide a structured git commit message following conventional commit format:

```
fix(security): resolve [X] blocker and [Y] critical SonarQube issues

- [Key]: Fix [Rule] in [filename]
- [Key]: Address vulnerability [Rule] at line [line]

Rules addressed: [List unique Rule IDs]
Files modified:
- [Path/to/file1]
- [Path/to/file2]
```

---

## Key Requirements:

1. **Systematic Approach**: Process issues starting with BLOCKER, then CRITICAL
2. **Precise Edits**: Only modify the lines necessary to fix the issue
3. **Rule Compliance**: Ensure the fix directly addresses the SonarQube rule requirements
4. **Complete Documentation**: Record the key and rule for every fix made
5. **Component Resolution**: Map the `component` path (e.g., `ProjectName:Path/To/File.cs`) to the actual local file path correctly

## Special Considerations:

- **False Positives**: If an issue is clearly a false positive, document the reasoning and mark it as "Will Not Fix"
- **Complex Refactoring**: If a fix requires significant architectural changes, flag it for human review before proceeding
- **QuickFix Available**: Check if the JSON indicates a `quickFixAvailable: true`, but always verify the suggested fix manually
- **Contextual Awareness**: Use the `hash` and `textRange` in the JSON if the file has changed significantly from the scan snapshot
- **Deduplication**: Group identical rule violations across multiple components — apply a consistent fix pattern rather than treating each occurrence independently

## Usage:

To use this prompt:
1. Specify the path to the actual SonarQube scan JSON file
2. Filter for Issues where `type` is BUG/VULNERABILITY and `severity` is BLOCKER/CRITICAL
3. Execute each step methodically
4. Follow the summary and commit formats exactly

---

**Remember**: Code quality and security are critical — take time to understand each issue and implement proper fixes rather than rushing through the process.
