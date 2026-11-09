<!-- Bu dosya scripts/dokuman_uret.py ile üretilir; elle düzenleme. -->

# Hook'lar

Kaynak: `hooks/hooks.json`; hepsi `scripts/hook_giris.py <Olay>` çağırır (bayt kodu önbelleğini açıp hook.py'yi modül olarak çalıştırır).

| Olay | Eşleyici | Komut sayısı |
|---|---|---|
| SessionStart | `—` | 2 |
| UserPromptSubmit | `—` | 1 |
| UserPromptSubmit | `—` | 1 |
| PreToolUse | `.*` | 1 |
| PostToolUse | `Skill|Agent|Task|Workflow|AskUserQuestion|mcp__ccd_session__start_session` | 1 |
| PostToolUse | `Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell` | 1 |
| PostToolUseFailure | `—` | 1 |
| SubagentStart | `—` | 1 |
| SubagentStop | `—` | 1 |
| Stop | `—` | 1 |
| Notification | `—` | 1 |
| PreCompact | `—` | 1 |
| SessionEnd | `—` | 1 |
| ConfigChange | `—` | 1 |
