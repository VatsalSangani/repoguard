import os

from config import REPORT_FILENAME


def save_report(report_text: str) -> None:
    try:
        with open(REPORT_FILENAME, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"\n✅ Report saved to: {os.path.abspath(REPORT_FILENAME)}")
    except Exception as e:
        print(f"\n❌ Error saving report: {e}")
