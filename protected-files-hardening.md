# Protected files hardening

Drafts. Untested. Replace the placeholder paths with your own.

## 1. Hook script

Save as `C:\Program Files\ClaudeCode\hooks\block-protected-files.ps1`.

```powershell
$protected = @('secrets/', '.env', 'prod.tfvars', 'id_rsa')
$norm = ([Console]::In.ReadToEnd()) -replace '\\\\', '/' -replace '\\', '/'
foreach ($p in $protected) {
  if ($norm -match [regex]::Escape($p)) {
    [Console]::Error.WriteLine("Blocked: $p. Stop and ask the user.")
    exit 2
  }
}
exit 0
```

## 2. Managed settings snippet

Save as `C:\Program Files\ClaudeCode\managed-settings.json`. Write it as admin.
Repeat the four deny rules for each protected path.

```json
{
  "permissions": {
    "deny": [
      "Read(secrets/**)",
      "Edit(secrets/**)",
      "Bash(*secrets/*)",
      "PowerShell(*secrets/*)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "powershell -ExecutionPolicy Bypass -File \"C:\\Program Files\\ClaudeCode\\hooks\\block-protected-files.ps1\""
          }
        ]
      }
    ]
  }
}
```

## Limits

- Both layers match text only. A command that builds the path in pieces can pass.
- Native Windows has no OS-level block. WSL2 sandbox `denyRead` is the full fix.
- Unverified: `PowerShell(...)` deny syntax and `matcher: "*"`. Test with a dummy file.
- The hook also blocks edits you ask Claude to make to these files.
