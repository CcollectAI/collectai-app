import pathlib

project_root = pathlib.Path("/home/ubuntu/collectors-merge-recovered")
path = project_root / "app" / "(tabs)" / "items.tsx"
backup = path.with_suffix(".tsx.bak_calendar_banner")

text = path.read_text(encoding="utf-8")

if "UpcomingEventsBanner" in text:
    print("ℹ️ Items already references UpcomingEventsBanner. Skipping injection.")
else:
    # Backup first
    backup.write_text(text, encoding="utf-8")
    print(f"📦 Backed up items.tsx to {backup}")

    # Add import near top
    if "from \"@/components/UpcomingEventsBanner\"" not in text:
        import_line = 'import UpcomingEventsBanner from "@/components/UpcomingEventsBanner";\n'
        if "from \"expo-router\"" in text:
            marker = "from \"expo-router\""
            idx = text.find(marker)
            if idx != -1:
                end_line = text.find("\n", idx)
                text = text[: end_line + 1] + import_line + text[end_line + 1 :]
            else:
                text = import_line + text
        else:
            text = import_line + text

    # Inject banner before last </ScrollView>
    marker = "</ScrollView>"
    idx = text.rfind(marker)
    if idx == -1:
        print("⚠️ Could not find </ScrollView> in items.tsx. "
              "Please manually place <UpcomingEventsBanner context=\"items\" /> "
              "near the bottom of the main content.")
    else:
        injection = '      <UpcomingEventsBanner context="items" />\n'
        text = text[:idx] + injection + text[idx:]
        path.write_text(text, encoding="utf-8")
        print("✅ Injected UpcomingEventsBanner into items.tsx before </ScrollView>.")
