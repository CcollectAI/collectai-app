/**
 * ProjectNotesCard — Progress notes list with add-note form.
 */

import React from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable } from "@/motion";
import type { BuildPaintNote } from "@/data";

function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export interface ProjectNotesCardProps {
  notes: BuildPaintNote[];
  accentColor: string;
  newNoteBody: string;
  addingNote: boolean;
  onChangeNoteBody: (text: string) => void;
  onAddNote: () => void;
}

export const ProjectNotesCard = React.memo(function ProjectNotesCard({
  notes,
  accentColor,
  newNoteBody,
  addingNote,
  onChangeNoteBody,
  onAddNote,
}: ProjectNotesCardProps) {
  const { colors } = useAppTheme();

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.cardHeader}>
        <Text style={[styles.cardTitle, { color: colors.text }]}>Progress Notes</Text>
        <Text style={[styles.cardSubtitle, { color: colors.muted }]}>{notes.length} entries</Text>
      </View>

      {notes.length === 0 ? (
        <Text style={[styles.emptyText, { color: colors.muted }]}>No notes added yet</Text>
      ) : (
        <View style={styles.notesList}>
          {notes.map((note, idx) => (
            <View
              key={note.id}
              style={[
                styles.noteItem,
                idx < notes.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.border },
              ]}
            >
              <Text style={[styles.noteDate, { color: colors.muted }]}>
                {formatDate(note.createdAt)}
              </Text>
              <Text style={[styles.noteBody, { color: colors.text }]}>{note.body}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Add note input */}
      <View style={styles.addNoteRow}>
        <TextInput
          value={newNoteBody}
          onChangeText={onChangeNoteBody}
          placeholder="Add a note..."
          placeholderTextColor={colors.muted}
          multiline
          accessibilityLabel="New note"
          style={[
            styles.addNoteInput,
            { color: colors.text, borderColor: colors.border, backgroundColor: colors.background },
          ]}
        />
        <AnimatedPressable
          style={[
            styles.addNoteBtn,
            {
              backgroundColor: newNoteBody.trim() ? accentColor : colors.border,
              opacity: addingNote ? 0.7 : 1,
            },
          ]}
          onPress={onAddNote}
          disabled={!newNoteBody.trim() || addingNote}
          accessibilityRole="button"
          accessibilityLabel={addingNote ? "Adding note" : "Add note"}
        >
          {addingNote ? (
            <ActivityIndicator size="small" color={colors.accentText} />
          ) : (
            <Text style={[styles.addNoteBtnText, { color: colors.accentText }]}>Add Note</Text>
          )}
        </AnimatedPressable>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: "700",
  },
  cardSubtitle: {
    fontSize: 12,
  },
  emptyText: {
    fontSize: 13,
    fontStyle: "italic",
    marginBottom: 12,
  },
  notesList: {
    marginBottom: 12,
  },
  noteItem: {
    paddingVertical: 12,
  },
  noteDate: {
    fontSize: 11,
    marginBottom: 4,
  },
  noteBody: {
    fontSize: 14,
    lineHeight: 20,
  },
  addNoteRow: {
    gap: 8,
  },
  addNoteInput: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    minHeight: 60,
    textAlignVertical: "top",
  },
  addNoteBtn: {
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  addNoteBtnText: {
    fontSize: 14,
    fontWeight: "600",
  },
});
