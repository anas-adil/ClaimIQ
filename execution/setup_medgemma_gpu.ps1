param(
    [switch]$InstallDepsOnly
)

$ErrorActionPreference = "Stop"

Write-Host "Setting up local MedGemma environment..."
Write-Host "Working directory: $(Get-Location)"

Write-Host "`n[1/4] Installing Python dependencies from requirements.txt..."
python -m pip install -r requirements.txt

if (-not $InstallDepsOnly) {
    Write-Host "`n[2/4] Installing CUDA-enabled PyTorch (cu124)..."
    python -m pip uninstall -y torch torchvision torchaudio
    python -m pip install --index-url https://download.pytorch.org/whl/cu124 torch torchvision torchaudio
} else {
    Write-Host "`n[2/4] Skipped CUDA PyTorch install (--InstallDepsOnly)."
}

Write-Host "`n[3/4] Verifying torch + CUDA status..."
python -c "import torch; print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available()); print('cuda_count', torch.cuda.device_count())"

Write-Host "`n[4/4] Done."
Write-Host "If model download fails with gated access error, set HF_TOKEN and re-run inference:"
Write-Host '  setx HF_TOKEN "hf_xxx"'
Write-Host "Then open a new terminal and run:"
Write-Host "  python execution/medgemma_infer.py"
