#!/usr/bin/env bash
set -euo pipefail

FILE="app/projects.tsx"

if [ ! -f "$FILE" ]; then
  echo "Projects screen not found at $FILE"
  exit 1
fi

cp "$FILE" "${FILE}.bak.linkable-$(date +%s)" || true

python << 'PY'
from pathlib import Path

path = Path("app/projects.tsx")
text = path.read_text()

# 1) Update react-native import to include TouchableOpacity
text = text.replace(
    "import { ScrollView, Text, View } from 'react-native';",
    "import { ScrollView, Text, View, TouchableOpacity } from 'react-native';"
)

# 2) Update expo-router import to include Link
text = text.replace(
    "import { Stack } from 'expo-router';",
    "import { Stack, Link } from 'expo-router';"
)

# 3) Replace the projects.map block to wrap ProjectCard in Link + TouchableOpacity
old_block = """          <View style={{ gap: spacing.md }}>
            {projects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                colors={colors}
                spacing={spacing}
                radii={radii}
              />
            ))}
          </View>"""

new_block = """          <View style={{ gap: spacing.md }}>
            {projects.map((project) => (
              <Link
                key={project.id}
                href={{ pathname: '/projects/[id]', params: { id: project.id } }}
                asChild
              >
                <TouchableOpacity activeOpacity={0.85}>
                  <ProjectCard
                    project={project}
                    colors={colors}
                    spacing={spacing}
                    radii={radii}
                  />
                </TouchableOpacity>
              </Link>
            ))}
          </View>"""

if old_block not in text:
    raise SystemExit("Expected projects.map block not found in app/projects.tsx")

text = text.replace(old_block, new_block, 1)

path.write_text(text)
PY

echo "Updated app/projects.tsx to make project cards tappable links. Backup created."
