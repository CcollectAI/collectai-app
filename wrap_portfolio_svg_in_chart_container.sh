#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

FILE="app/(tabs)/index.tsx"

echo "=== Wrapping Portfolio SVG chart in a responsive container ==="

if [ ! -f "$FILE" ]; then
  echo "❌ $FILE not found."
  exit 1
fi

python3 <<'PYCODE'
from pathlib import Path

path = Path("app/(tabs)/index.tsx")
text = path.read_text(encoding="utf-8")

backup = path.with_suffix(path.suffix + ".bak_chartWrap")
backup.write_text(text, encoding="utf-8")
print("📦 Backed up index.tsx to", backup)

# 1) Find the <Svg height={90} width={260}> ... </Svg> block
start_marker = "<Svg height={90} width={260}>"
start = text.find(start_marker)
if start == -1:
    # Maybe you've already changed width; try the width=\"100%\" version as fallback.
    start_marker = '<Svg height={90} width="100%" preserveAspectRatio="none">'
    start = text.find(start_marker)

if start == -1:
    print("ℹ️ Could not find the SVG opening tag with height 90; no changes applied.")
else:
    end = text.find("</Svg>", start)
    if end == -1:
        print("⚠️ Found SVG start but no closing </Svg>; not touching file.")
    else:
        end += len("</Svg>")
        block = text[start:end]

        # Normalize opening tag to responsive style
        if "width={260}" in block:
            block = block.replace(
                "<Svg height={90} width={260}>",
                '<Svg height={90} width="100%" viewBox="0 0 260 90" preserveAspectRatio="none">'
            )
        elif 'width="100%"' in block and "viewBox" not in block:
            # If we already changed width earlier, just add viewBox/preserveAspectRatio
            block = block.replace(
                'width="100%"',
                'width="100%" viewBox="0 0 260 90" preserveAspectRatio="none"'
            )

        # Wrap the SVG block in a View with a dedicated style.
        wrapped = (
            "        <View style={styles.portfolioChartWrapper}>\n"
            + block.replace("\n", "\n        ")
            + "\n        </View>"
        )

        text = text[:start] + wrapped + text[end:]
        path.write_text(text, encoding="utf-8")
        print("✅ Wrapped SVG block in <View style={styles.portfolioChartWrapper}> and made width responsive.")

# 2) Inject portfolioChartWrapper style if not present
text = path.read_text(encoding="utf-8")
if "portfolioChartWrapper" in text:
    print("ℹ️ styles.portfolioChartWrapper already defined; skipping style injection.")
else:
    marker = "const styles = StyleSheet.create({"
    idx = text.find(marker)
    if idx == -1:
        print("⚠️ Could not find 'const styles = StyleSheet.create({' to inject style; leaving layout as-is.")
    else:
        insert_pos = idx + len(marker)
        style_snippet = """
  portfolioChartWrapper: {
    width: "100%",
    marginTop: 8,
    marginBottom: 16,
    alignSelf: "stretch",
  },"""
        new_text = text[:insert_pos] + style_snippet + text[insert_pos:]
        path.write_text(new_text, encoding="utf-8")
        print("✅ Injected styles.portfolioChartWrapper into StyleSheet.")
PYCODE
