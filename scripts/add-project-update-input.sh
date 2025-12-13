#!/usr/bin/env bash
set -euo pipefail

FILE="app/projects/[id].tsx"

if [ ! -f "$FILE" ]; then
  echo "Project detail screen not found at $FILE"
  exit 1
fi

cp "$FILE" "${FILE}.bak.add-update-$(date +%s)" || true

python << 'PY'
from pathlib import Path

path = Path("app/projects/[id].tsx")
text = path.read_text()

# 1) Upgrade React import to include useState
text = text.replace(
    "import React from 'react';",
    "import React, { useState } from 'react';"
)

# 2) Extend react-native import to include TextInput, TouchableOpacity
text = text.replace(
    "import { ScrollView, Text, View } from 'react-native';",
    "import { ScrollView, Text, View, TextInput, TouchableOpacity } from 'react-native';"
)

# 3) Import addProjectUpdate from projectsStore
if "addProjectUpdate" not in text:
    text = text.replace(
        "import { useProject } from '@/state/projectsStore';",
        "import { useProject, addProjectUpdate } from '@/state/projectsStore';"
    )

# 4) Add local state hooks inside component
marker = "  const { colors, spacing, radii } = useAppTheme();"
insert = """  const { colors, spacing, radii } = useAppTheme();
  const [newNote, setNewNote] = useState('');
  const [saving, setSaving] = useState(false);
"""
if marker not in text:
    raise SystemExit("Could not find theme destructuring line in project detail file")
text = text.replace(marker, insert, 1)

# 5) Inject input + button at bottom of updates card

old_block = """              {updates.length === 0 ? (
                <Text
                  style={{
                    fontSize: 13,
                    color: colors.mutedText,
                  }}
                >
                  No updates yet for this project. Later, adding photos and
                  notes from your build sessions will create a full history
                  here.
                </Text>
              ) : (
                <View style={{ marginTop: spacing.sm }}>
                  {updates.map((u, idx) => (
                    <View
                      key={u.id}
                      style={{
                        paddingVertical: spacing.sm,
                        borderBottomWidth:
                          idx === updates.length - 1 ? 0 : 1,
                        borderBottomColor: colors.border,
                      }}
                    >
                      <Text
                        style={{
                          fontSize: 12,
                          color: colors.mutedText,
                          marginBottom: 2,
                        }}
                      >
                        {formatDateTime(u.createdAt)}
                      </Text>
                      {u.note ? (
                        <Text
                          style={{
                            fontSize: 13,
                            color: colors.text,
                          }}
                        >
                          {u.note}
                        </Text>
                      ) : (
                        <Text
                          style={{
                            fontSize: 13,
                            color: colors.mutedText,
                          }}
                        >
                          (No note added)
                        </Text>
                      )}
                      {u.timeSpentMinutes != null ? (
                        <Text
                          style={{
                            fontSize: 11,
                            color: colors.mutedText,
                            marginTop: 2,
                          }}
                        >
                          Session: {u.timeSpentMinutes} minutes
                        </Text>
                      ) : null}
                    </View>
                  ))}
                </View>
              )}
            </View>"""

new_block = """              {updates.length === 0 ? (
                <Text
                  style={{
                    fontSize: 13,
                    color: colors.mutedText,
                  }}
                >
                  No updates yet for this project. Later, adding photos and
                  notes from your build sessions will create a full history
                  here.
                </Text>
              ) : (
                <View style={{ marginTop: spacing.sm }}>
                  {updates.map((u, idx) => (
                    <View
                      key={u.id}
                      style={{
                        paddingVertical: spacing.sm,
                        borderBottomWidth:
                          idx === updates.length - 1 ? 0 : 1,
                        borderBottomColor: colors.border,
                      }}
                    >
                      <Text
                        style={{
                          fontSize: 12,
                          color: colors.mutedText,
                          marginBottom: 2,
                        }}
                      >
                        {formatDateTime(u.createdAt)}
                      </Text>
                      {u.note ? (
                        <Text
                          style={{
                            fontSize: 13,
                            color: colors.text,
                          }}
                        >
                          {u.note}
                        </Text>
                      ) : (
                        <Text
                          style={{
                            fontSize: 13,
                            color: colors.mutedText,
                          }}
                        >
                          (No note added)
                        </Text>
                      )}
                      {u.timeSpentMinutes != null ? (
                        <Text
                          style={{
                            fontSize: 11,
                            color: colors.mutedText,
                            marginTop: 2,
                          }}
                        >
                          Session: {u.timeSpentMinutes} minutes
                        </Text>
                      ) : null}
                    </View>
                  ))}
                </View>
              )}

              {/* Add update input */}
              <View
                style={{
                  marginTop: spacing.md,
                  paddingTop: spacing.sm,
                  borderTopWidth: 1,
                  borderTopColor: colors.border,
                }}
              >
                <Text
                  style={{
                    fontSize: 12,
                    fontWeight: '600',
                    color: colors.text,
                    marginBottom: 4,
                  }}
                >
                  Add progress update
                </Text>
                <TextInput
                  value={newNote}
                  onChangeText={setNewNote}
                  placeholder="What did you do this session?"
                  placeholderTextColor={colors.mutedText}
                  multiline
                  style={{
                    minHeight: 60,
                    paddingHorizontal: 10,
                    paddingVertical: 8,
                    borderRadius: radii.md,
                    borderWidth: 1,
                    borderColor: colors.border,
                    color: colors.text,
                    fontSize: 13,
                    textAlignVertical: 'top',
                  }}
                />
                <View
                  style={{
                    flexDirection: 'row',
                    justifyContent: 'flex-end',
                    marginTop: spacing.sm,
                  }}
                >
                  <TouchableOpacity
                    activeOpacity={0.8}
                    onPress={async () => {
                      if (!project || !newNote.trim() || saving) return;
                      try {
                        setSaving(true);
                        addProjectUpdate({
                          projectId: project.id,
                          note: newNote.trim(),
                          timeSpentMinutes: null,
                        });
                        setNewNote('');
                      } finally {
                        setSaving(false);
                      }
                    }}
                    style={{
                      paddingHorizontal: spacing.md,
                      paddingVertical: 8,
                      borderRadius: radii.full,
                      backgroundColor: newNote.trim()
                        ? colors.primary
                        : colors.surface,
                    }}
                  >
                    <Text
                      style={{
                        fontSize: 13,
                        fontWeight: '600',
                        color: newNote.trim()
                          ? colors.onPrimary
                          : colors.mutedText,
                      }}
                    >
                      {saving ? 'Saving…' : 'Add update'}
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>
            </View>"""

if old_block not in text:
    raise SystemExit("Expected updates block not found in app/projects/[id].tsx")

text = text.replace(old_block, new_block, 1)

path.write_text(text)
PY

echo "Added 'Add update' input to project detail screen. Backup created."
