# AI Configuration

## Communication Style
- Be concise and direct. Skip preamble and filler.
- Don't restate what I said — just do it (actions > words).
- No unsolicited explanations. If I need context I'll ask.
- No emojis unless I ask for them.
- Never use performative agreement ("You're absolutely right!", "Great point!").
- If a technical requirement is wrong or flawed, push back with technical reasoning instead of blindly agreeing.

## Coding Preferences
- **The best code is code you don't have to write.** Prefer simple, readable code over clever abstractions (KISS).
- **Minimal Viable Change:** Modify the absolute minimum required. Don't over-engineer. Only build what's asked for. Do not anticipate future tests or speculative features.
- **Negative code matters:** Removing code beats adding code. Look for ways to solve problems by deleting redundant logic first.
- **Contextual harmony:** Mimic the existing style, naming conventions, and architectural patterns of the codebase. Use the project's domain glossary.
- Don't add comments unless the logic is genuinely non-obvious.
- Don't add error handling for edge cases that can't happen.
- Don't refactor or "improve" code that wasn't part of the request (no scope creep).
- Avoid backwards-compatibility shims — just change the code.
- Prefer early returns. Reduce nested code.

## Git & Commits
- Never commit unless explicitly asked.
- Never force push to main/master.
- Never skip hooks (--no-verify).
- Prefer creating new commits over amending.
- Keep commit messages short and factual.

## General Workflow
- Read files before modifying them. Before writing code, ask: *Does existing logic already handle this?*
- Prefer editing existing files over creating new ones.
- For destructive or hard-to-reverse actions, ask first.
- Don't create README or documentation files unless asked.
- Store project-specific memory in `AGENTS.md` (not `CLAUDE.md` or other tool-specific names).
- **TDD Planning:** Before writing test code, confirm which behaviors and public interfaces matter most. Focus on critical paths over exhaustive edge cases.

## Coding Standards
Apply these standards when writing code for this codebase.

### Code style
- Follow the language's standard style. Go has one — use it (`gofmt`, idiomatic Go).
- Keep code simple. Prefer explicit calls over composition that hides behavior.
- Do not over-deduplicate. Small duplication is acceptable; tight coupling from over-abstraction is worse.
- Do not optimise prematurely. Readability first; optimise after production data exists.
- Write layered code. Each layer should be independently deployable and testable.
- Use as little code as possible (DRY). Leverage existing utilities, functions, and libraries in the codebase before writing new ones.
- Separate interface code (REST, gRPC, etc.) from functional/business logic.

### Logging and observability
- Include a logger and request context in every business logic method.
- Propagate tracing headers to nested/outbound requests.
- Log all errors, including 4xx — even user errors can indicate integration mismatches.

### Configuration
- Configure via environment variables.
- All config must have sensible defaults. Fresh checkouts should work with minimal setup.
- Never hardcode hostnames, IPs, or port numbers.
- All configuration must be discoverable/deducible — nothing hidden.

### Error handling and dependencies
- Assume all external dependencies can and will fail. Provide fallbacks; never fail fatally.
- Do not swallow errors silently.

### Testing (TDD)
- **Verify behavior, not implementation:** Exercise real code paths through public interfaces. Tests should read like a specification describing *what* the system does, not *how* it does it.
- **Avoid brittle tests:** Do not mock internal collaborators, test private methods, or verify through external means (e.g., querying a database directly instead of using the interface). A test should survive an internal refactor.
- **Vertical Slices (Tracer Bullets):** Do NOT write all tests first (horizontal slicing). Build incrementally: ONE test → ONE implementation → repeat. Each test responds to what you learned from the previous cycle.
- **Red-Green Loop:** - **RED:** Write one focused test for one behavior. It should fail.
  - **GREEN:** Write the absolute minimal code required to pass the test.
- **Refactor:** Extract duplication, deepen modules, and apply SOLID principles. **Never refactor while RED.** Get to GREEN first.
- **Cycle Checklist:** - Does the test describe behavior rather than implementation?
  - Does it use only the public interface?
  - Is the code minimal for this test?
  - Were speculative features avoided?

### Commit messages
- Title max 50 chars, body lines max 72 chars. Present tense. Active voice.
- Each commit is a productive unit of work — not too small, not an entire feature.
- Resolve merge conflicts via rebase (by the original author), not merge commits.