import { useState } from "react";
import { View, Text, Pressable, Alert, ScrollView } from "react-native";
import { supabase } from "@/lib/supabaseClient";

const CATEGORY_TEMPLATES: Record<string, string[]> = {
  gunpla: ["Planning","Assembly","Panel lining","Painting","Decals","Top coat","Finished"],
  minis: ["Priming","Base colors","Shading","Highlights","Details","Finished"],
  kitbash: ["Concept","Parts prep","Assembly","Painting","Weathering","Finished"],
};

export default function NewBuildProject() {
  const [category, setCategory] = useState<string | null>(null);
  const [stage, setStage] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const stages = category ? CATEGORY_TEMPLATES[category] : [];

  const create = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const uid = session?.user?.id;
      if (!uid) throw new Error("Not logged in");
      if (!category || !stage) throw new Error("Pick category and stage");

      const { error } = await supabase.from("build_paint_projects").insert({
        user_id: uid,
        name: `${category} project`,
        category,
        stage,
        progress_pct: progress,
        status: "active",
      });
      if (error) throw error;

      Alert.alert("Project created");
    } catch (e: any) {
      Alert.alert("Error", e?.message || String(e));
    }
  };

  return (
    <ScrollView style={{ flex: 1, padding: 24 }}>
      <Text style={{ fontSize: 18, fontWeight: "800" }}>New Build & Paint Project</Text>

      {!category ? (
        <View style={{ marginTop: 16, gap: 10 }}>
          <Text style={{ fontWeight: "700" }}>Choose category</Text>
          {Object.keys(CATEGORY_TEMPLATES).map((c) => (
            <Pressable
              key={c}
              onPress={() => setCategory(c)}
              style={{ padding: 14, borderWidth: 1, marginTop: 10 }}
            >
              <Text style={{ fontWeight: "700" }}>{c}</Text>
            </Pressable>
          ))}
        </View>
      ) : (
        <View style={{ marginTop: 16, gap: 10 }}>
          <Text style={{ fontWeight: "700" }}>Current stage</Text>

          {stages.map((s, i) => (
            <Pressable
              key={s}
              onPress={() => {
                setStage(s);
                setProgress(stages.length > 1 ? Math.round((i / (stages.length - 1)) * 100) : 0);
              }}
              style={{
                padding: 14,
                borderWidth: 1,
                marginTop: 10,
                backgroundColor: stage === s ? "rgba(0,0,0,0.06)" : "transparent",
              }}
            >
              <Text>{s}</Text>
            </Pressable>
          ))}

          <View style={{ marginTop: 14 }}>
            <Text style={{ fontWeight: "700" }}>Progress</Text>
            <View style={{ height: 8, backgroundColor: "rgba(0,0,0,0.08)", marginTop: 8 }}>
              <View style={{ height: 8, width: `${progress}%`, backgroundColor: "#7C5CFF" }} />
            </View>
            <Text style={{ marginTop: 6, opacity: 0.7 }}>{progress}%</Text>
          </View>

          <Pressable
            onPress={create}
            disabled={!stage}
            style={{
              padding: 16,
              backgroundColor: "#7C5CFF",
              marginTop: 18,
              opacity: stage ? 1 : 0.5,
            }}
          >
            <Text style={{ color: "white", textAlign: "center", fontWeight: "700" }}>
              Create project
            </Text>
          </Pressable>

          <Pressable
            onPress={() => {
              setCategory(null);
              setStage(null);
              setProgress(0);
            }}
            style={{ padding: 14, borderWidth: 1, marginTop: 12 }}
          >
            <Text style={{ textAlign: "center", fontWeight: "700" }}>Change category</Text>
          </Pressable>
        </View>
      )}
    </ScrollView>
  );
}
