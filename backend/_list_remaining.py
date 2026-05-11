import json
from collections import Counter

data = json.load(open("reports/test-quality-local.json"))
for rule_id in ("TQA012", "TQA004", "STG007", "META001", "TQA020", "STG006", "TQA021"):
    issues = [i for i in data["issues"] if i["rule_id"] == rule_id]
    if issues:
        print(f"\n=== {rule_id} ({len(issues)}x) ===")
        for i in issues:
            print(f"  {i['file']}:{i['line']}  {i['message']}")
