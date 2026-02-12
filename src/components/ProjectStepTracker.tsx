import React, {
  useEffect,
  useMemo,
  useState,
  useCallback,
} from "react";
import {
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
  LayoutAnimation,
  Platform,
  UIManager,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { supabase } from "@/lib/supabase";
import { logger } from "@/lib/logger";

if (Platform.OS === "android" && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

export type Step = {
  id: string;
  label: string;
  done: boolean;
};

const DEFAULT_STEPS: Step[] = [
  { id: "plan", label: "Planning & references gathered", done: false },
  { id: "assembly", label: "Assembly / build completed", done: false },
  { id: "prime", label: "Primed / surface prepared", done: false },
  { id: "basecoat", label: "Base layer / basecoat finished", done: false },
  { id: "shading", label: "Shading / washes done", done: false },
  { id: "details", label: "Details & highlights finished", done: false },
  { id: "finish", label: "Final touches & sealing / display ready", done: false },
];

type Props = {
  projectId?: string | null;
};

/** Return the real Supabase client, or null when it's a mock without .from(). */
function getSafeSupabase() {
  try {
    if (!supabase || typeof supabase.from !== "function") {
      logger.warn(
        "[ProjectStepTracker] Supabase client not ready; running in local-only mode."
      );
      return null;
    }
    return supabase;
  } catch {
    logger.warn(
      "[ProjectStepTracker] Supabase client threw; running in local-only mode."
    );
    return null;
  }
}

export const ProjectStepTracker: React.FC<Props> = ({ projectId }) => {
  const [steps, setSteps] = useState<Step[]>(DEFAULT_STEPS);
  const [notes, setNotes] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(!!projectId);
  const [saving, setSaving] = useState<boolean>(false);
  const [lastError, setLastError] = useState<string | null>(null);

  const completionPct = useMemo(() => {
    if (!steps.length) return 0;
    const done = steps.filter((s) => s.done).length;
    return Math.round((done / steps.length) * 100);
  }, [steps]);

  const safeSupabase = getSafeSupabase();
  const canPersist = !!projectId && !!safeSupabase;

  // Load from Supabase when projectId is provided and supabase is healthy
  useEffect(() => {
    if (!canPersist) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    const load = async () => {
      try {
        setLoading(true);
        setLastError(null);

        const { data, error } = await safeSupabase!
          .from("build_paint_projects")
          .select("notes, steps")
          .eq("id", projectId)
          .maybeSingle();

        if (error) {
          logger.error("[ProjectStepTracker] load error", error);
          if (!cancelled) {
            setLastError("Could not load project progress.");
          }
          return;
        }

        if (!data) {
          return;
        }

        if (!cancelled) {
          const dataRow = data as Record<string, unknown>;
          const remoteNotes = (dataRow.notes as string | undefined) ?? "";
          const remoteSteps = dataRow.steps as Step[] | null;

          setNotes(typeof remoteNotes === "string" ? remoteNotes : "");
          if (Array.isArray(remoteSteps) && remoteSteps.length) {
            setSteps(
              remoteSteps.map((s) => ({
                id: String(s.id),
                label: String(s.label),
                done: !!s.done,
              }))
            );
          }
        }
      } catch (err) {
        logger.error("[ProjectStepTracker] load exception", err);
        if (!cancelled) {
          setLastError("Could not load project progress.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [canPersist, projectId, safeSupabase]);

  const saveToSupabase = useCallback(
    async (nextNotes: string, nextSteps: Step[]) => {
      if (!canPersist) return;
      try {
        setSaving(true);
        setLastError(null);

        const progressPct = (() => {
          if (!nextSteps.length) return 0;
          const done = nextSteps.filter((s) => s.done).length;
          return Math.round((done / nextSteps.length) * 100);
        })();

        const { error } = await safeSupabase!
          .from("build_paint_projects")
          .update({
            notes: nextNotes,
            steps: nextSteps,
            progress_pct: progressPct,
            updated_at: new Date().toISOString(),
          })
          .eq("id", projectId);

        if (error) {
          logger.error("[ProjectStepTracker] save error", error);
          setLastError("Could not save progress. Will retry on next change.");
        }
      } catch (err) {
        logger.error("[ProjectStepTracker] save exception", err);
        setLastError("Could not save progress. Will retry on next change.");
      } finally {
        setSaving(false);
      }
    },
    [canPersist, projectId, safeSupabase]
  );

  const toggleStep = (id: string) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setSteps((prev) => {
      const next = prev.map((step) =>
        step.id === id ? { ...step, done: !step.done } : step
      );
      // Fire-and-forget save (no await to keep UI snappy)
      saveToSupabase(notes, next);
      return next;
    });
  };

  const handleNotesChange = (value: string) => {
    setNotes(value);
    saveToSupabase(value, steps);
  };

  const effectiveCompletionPct = completionPct;

  return (
    <View style={styles.card}>
      {/* Header */}
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.title}>Build & paint tracker</Text>
          <Text style={styles.subtitle}>
            Log your progress for paint jobs, Gunpla kits, or LEGO builds.
          </Text>
        </View>

        <View style={styles.progressPill}>
          <View style={styles.progressDot} />
          <Text style={styles.progressPillText}>
            {effectiveCompletionPct}% done
          </Text>
        </View>
      </View>

      {loading && (
        <Text style={styles.loadingText}>Loading project progress…</Text>
      )}

      {lastError && (
        <Text style={styles.errorText}>{lastError}</Text>
      )}

      {/* Notes */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Notes</Text>
        <Text style={styles.sectionSubtitle}>
          Capture decisions, color recipes, or anything that will help you pick this
          project back up later.
        </Text>
        <TextInput
          value={notes}
          onChangeText={handleNotesChange}
          placeholder="Example: Warm off-white armor, purple OSL on the blade, oils for the face..."
          placeholderTextColor="#A0AEC0"
          multiline
          textAlignVertical="top"
          style={styles.notesInput}
          accessibilityLabel="Project notes"
        />
        {saving && (
          <Text style={styles.savingText}>Saving…</Text>
        )}
      </View>

      {/* Steps */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Progress steps</Text>
        <Text style={styles.sectionSubtitle}>
          Mark each stage as you complete it. Works for Warhammer, Gunpla, or LEGO builds.
        </Text>

        <View style={{ marginTop: 10 }}>
          {steps.map((step) => (
            <Pressable
              key={step.id}
              onPress={() => toggleStep(step.id)}
              accessibilityRole="checkbox"
              accessibilityState={{ checked: step.done }}
              accessibilityLabel={step.label}
              style={({ pressed }) => [
                styles.stepRow,
                step.done && styles.stepRowDone,
                pressed && styles.stepRowPressed,
              ]}
            >
              <View style={styles.stepIconCircle}>
                <Ionicons
                  name={step.done ? "checkmark-circle" : "ellipse-outline"}
                  size={20}
                  color={step.done ? "#02B5C4" : "#A0AEC0"}
                />
              </View>
              <Text
                style={[styles.stepLabel, step.done && styles.stepLabelDone]}
                numberOfLines={2}
              >
                {step.label}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>

      <Text style={styles.footerText}>
        Linked to your project when available. If no project is set or Supabase is offline,
        this tracker stays local to this screen.
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    marginTop: 16,
    marginBottom: 24,
    padding: 16,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    shadowColor: "#000000",
    shadowOpacity: 0.04,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
  },
  title: {
    fontSize: 16,
    fontWeight: "600",
    color: "#1A202C",
  },
  subtitle: {
    marginTop: 4,
    fontSize: 13,
    color: "#4A5568",
  },
  progressPill: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: "#E6FFFA",
  },
  progressDot: {
    width: 8,
    height: 8,
    borderRadius: 999,
    backgroundColor: "#38A169",
    marginRight: 6,
  },
  progressPillText: {
    fontSize: 12,
    fontWeight: "500",
    color: "#22543D",
  },
  loadingText: {
    marginTop: 8,
    fontSize: 12,
    color: "#718096",
  },
  errorText: {
    marginTop: 4,
    fontSize: 12,
    color: "#C53030",
  },
  section: {
    marginTop: 16,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: "#1A202C",
  },
  sectionSubtitle: {
    marginTop: 2,
    fontSize: 12,
    color: "#718096",
  },
  notesInput: {
    marginTop: 8,
    minHeight: 80,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
    color: "#1A202C",
  },
  savingText: {
    marginTop: 4,
    fontSize: 11,
    color: "#A0AEC0",
  },
  stepRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    paddingHorizontal: 4,
    borderRadius: 10,
  },
  stepRowDone: {
    backgroundColor: "#F0FFF4",
  },
  stepRowPressed: {
    opacity: 0.7,
  },
  stepIconCircle: {
    width: 28,
    alignItems: "center",
  },
  stepLabel: {
    flex: 1,
    fontSize: 13,
    color: "#2D3748",
  },
  stepLabelDone: {
    color: "#718096",
    textDecorationLine: "line-through",
  },
  footerText: {
    marginTop: 12,
    fontSize: 11,
    color: "#A0AEC0",
  },
});
