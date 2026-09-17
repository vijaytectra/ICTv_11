import subprocess
import sys

log_file = r"c:\personal\ICT_v11\scratch\quality_audit.log"
with open(log_file, "w") as out:
    proc = subprocess.run([sys.executable, "-u", r"c:\personal\ICT_v11\audit\validation\run_quality_optimization_validation.py"], stdout=out, stderr=out, text=True)

print(f"Runner completed with exit code {proc.returncode}")
