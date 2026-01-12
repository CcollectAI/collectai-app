import { View, ScrollView, Pressable, Text } from "react-native";
import { useRouter } from "expo-router";
import BuildProjectsBanner from "@/components/BuildProjectsBanner";
import ProjectStepTracker from "@/components/ProjectStepTracker";

export default function BuildScreen() {
  const router = useRouter();

  return (
    <ScrollView style={{ flex: 1, backgroundColor: "#fff" }}>
      <View style={{ padding: 16, gap: 16 }}>
        <BuildProjectsBanner />

        <Pressable
          onPress={() => router.push("/build-paint-projects/new")}
          style={{
            padding: 14,
            borderWidth: 1,
            borderColor: "#7C5CFF",
            alignItems: "center",
          }}
        >
          <Text style={{ color: "#7C5CFF", fontWeight: "700" }}>
            + New Build Project
          </Text>
        </Pressable>

        <ProjectStepTracker />
      </View>
    </ScrollView>
  );
}
