import React, { useState } from 'react';
import { ProjectStepTracker } from "@/components/ProjectStepTracker";
import { ScrollView, Text, View, TextInput, TouchableOpacity } from 'react-native';
import { Stack, useLocalSearchParams } from 'expo-router';

import { useAppTheme } from '@/hooks/useAppTheme';
import { useProject, addProjectUpdate } from '@/state/projectsStore';

function formatDateTime(iso: string | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  try {
    return new Intl.DateTimeFormat('de-DE', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d);
  } catch {
    return iso;
  }
}

export default function ProjectDetailScreen() {
  const { colors, spacing, radii } = useAppTheme();
  const [newNote, setNewNote] = useState('');
  const [saving, setSaving] = useState(false);

  const params = useLocalSearchParams<{ id?: string }>();
  const id = params.id ?? '';
  const { project, updates } = useProject(id);

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: project?.title ?? 'Project',
        }}
      />
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.background }}
        contentInsetAdjustmentBehavior="automatic"
        contentContainerStyle={{
          paddingTop: spacing.lg * 1.5,
          paddingHorizontal: spacing.lg,
          paddingBottom: spacing.xl * 2,
          gap: spacing.md,
        }}
      >
        {!project ? (
          <View
            style={{
              borderRadius: radii.lg,
              backgroundColor: colors.card,
              padding: spacing.md,
            }}
          >
            <Text
              style={{
                fontSize: 16,
                fontWeight: '600',
                color: colors.text,
                marginBottom: spacing.xs,
              }}
            >
              Project not found
            </Text>
            <Text
              style={{
                fontSize: 13,
                color: colors.mutedText,
              }}
            >
              This project id could not be loaded. It may be a demo id or has
              not been seeded.
            </Text>
          </View>
        ) : (
          <>
            {/* Header card */}
            <View
              style={{
                borderRadius: radii.lg,
                backgroundColor: colors.card,
                padding: spacing.md,
              }}
            >
              <Text
                style={{
                  fontSize: 18,
                  fontWeight: '700',
                  color: colors.text,
                  marginBottom: spacing.xs,
                }}
              >
                {project.title}
              </Text>

              {project.category ? (
                <Text
                  style={{
                    fontSize: 12,
                    color: colors.mutedText,
                    marginBottom: spacing.xs,
                  }}
                >
                  {project.category}
                </Text>
              ) : null}

              <View
                style={{
                  flexDirection: 'row',
                  justifyContent: 'space-between',
                  marginTop: spacing.sm,
                }}
              >
                <View style={{ flex: 1, paddingRight: spacing.sm }}>
                  <Text
                    style={{
                      fontSize: 12,
                      color: colors.mutedText,
                      marginBottom: 2,
                    }}
                  >
                    Status
                  </Text>
                  <Text
                    style={{
                      fontSize: 14,
                      fontWeight: '600',
                      color: colors.text,
                    }}
                  >
                    {project.status}
                  </Text>
                </View>
                <View style={{ flex: 1, alignItems: 'flex-end' }}>
                  <Text
                    style={{
                      fontSize: 12,
                      color: colors.mutedText,
                      marginBottom: 2,
                    }}
                  >
                    Progress
                  </Text>
                  <Text
                    style={{
                      fontSize: 14,
                      fontWeight: '600',
                      color: colors.text,
                    }}
                  >
                    {project.percentComplete.toFixed(0)}%
                  </Text>
                </View>
              </View>

              {/* Progress bar */}
              <View
                style={{
                  marginTop: spacing.sm,
                }}
              >
                <View
                  style={{
                    width: '100%',
                    height: 10,
                    borderRadius: 999,
                    backgroundColor: colors.surface,
                    overflow: 'hidden',
                  }}
                >
                  <View
                    style={{
                      height: '100%',
                      width: `${Math.min(
                        Math.max(project.percentComplete, 0),
                        100,
                      )}%`,
                      backgroundColor:
                        project.status === 'completed'
                          ? colors.success ?? '#16a34a'
                          : colors.primary,
                    }}
                  />
                </View>
              </View>

              {/* Notes */}
              {project.notes ? (
                <View
                  style={{
                    marginTop: spacing.sm,
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
                      marginBottom: 2,
                    }}
                  >
                    Notes
                  </Text>
                  <Text
                    style={{
                      fontSize: 13,
                      color: colors.mutedText,
                    }}
                  >
                    {project.notes}
                  </Text>
                </View>
              ) : null}
            </View>

            {/* Updates timeline */}
            <View
              style={{
                borderRadius: radii.lg,
                backgroundColor: colors.card,
                padding: spacing.md,
              }}
            >
              <Text
                style={{
                  fontSize: 16,
                  fontWeight: '700',
                  color: colors.text,
                  marginBottom: spacing.xs,
                }}
              >
                Progress log
              </Text>
              <Text
                style={{
                  fontSize: 13,
                  color: colors.mutedText,
                  marginBottom: spacing.sm,
                }}
              >
                Every check-in you make on this project will show up here as a
                timeline of your build or paint progress.
              </Text>

              {updates.length === 0 ? (
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
            </View>
          </>
        )}
              <ProjectStepTracker projectId={project?.id} />
      </ScrollView>
    </>
  );
}
