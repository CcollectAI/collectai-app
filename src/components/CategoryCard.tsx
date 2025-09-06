import React from "react";
import { View, Text, TouchableOpacity } from "react-native";
import { theme } from "../theme";
import { Category } from "../constants/categories";
import { useRouter } from "expo-router";
// ...
export default function CategoryCard({ item, onPress }: { item: Category; onPress?: () => void }) {
  const router = useRouter();
  const go = onPress ?? (() => router.push(`/categories/${item.slug}`));
  // ...
  <TouchableOpacity onPress={go} /* ... */>
    {/* ... */}
  </TouchableOpacity>
}


        }}
      >
        <View
          style={{
            backgroundColor: item.tint,
            borderRadius: theme.radius.lg,
            alignSelf: "flex-start",
            paddingHorizontal: 10,
            paddingVertical: 6,
            marginBottom: 10,
            opacity: 0.9,
          }}
        >
          <Text style={{ fontWeight: "800", color: "#0F172A" }}>{item.emoji ?? "★"}</Text>
        </View>
        <Text style={{ fontSize: 15, fontWeight: "700", color: theme.colors.text }}>
          {item.name}
        </Text>
      </View>
    </TouchableOpacity>
  );
}
