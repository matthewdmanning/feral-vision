param(
    [Parameter(Mandatory = $true)]
    [string]$SourceDir,
    [int]$Port = 8765
)

$escaped = $SourceDir.Replace("'", "''")
uv run python -c "from tools.augmentation_preview_app import start_augmentation_preview_server; start_augmentation_preview_server(r'$escaped', port=$Port)"
