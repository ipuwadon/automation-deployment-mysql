import subprocess
from pathlib import Path

repository_root = Path(__file__).resolve().parents[2]
sql_file = repository_root / "procedures" / "customer_product_summary.sql"
sql_code = sql_file.read_text(encoding="utf-8")
prompt = f"Analyze this SQL procedure and generate unit test:\n{sql_code}"

result = subprocess.run(
    ["ollama", "run", "qwen2.5-coder:1.5b"],
    input=prompt.encode(),
    capture_output=True
)
print(result.stdout.decode())