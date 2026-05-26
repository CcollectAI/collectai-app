import React, { useEffect, useState } from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { subscribeDebugLog, clearDebugLog } from "@/lib/debugLog";

export function DebugOverlay() {
  const [lines, setLines] = useState<string[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const insets = useSafeAreaInsets();

  useEffect(() => subscribeDebugLog(setLines), []);

  return (
    <View
      pointerEvents="box-none"
      style={[styles.wrap, { top: insets.top + 50 }]}
    >
      <View style={styles.row} pointerEvents="box-none">
        {collapsed ? (
          <Pressable
            onPress={() => setCollapsed(false)}
            style={styles.btnSmall}
            hitSlop={8}
          >
            <Text style={styles.btnText}>DBG·{lines.length}</Text>
          </Pressable>
        ) : (
          <>
            <Pressable onPress={() => setCollapsed(true)} style={styles.btn} hitSlop={8}>
              <Text style={styles.btnText}>▲</Text>
            </Pressable>
            <Pressable onPress={() => clearDebugLog()} style={styles.btn} hitSlop={8}>
              <Text style={styles.btnText}>CLR</Text>
            </Pressable>
          </>
        )}
      </View>
      {!collapsed && (
        <View style={styles.box}>
          {lines.length === 0 ? (
            <Text style={styles.line}>(no events yet — tap a tab)</Text>
          ) : (
            lines.slice(-14).map((line, i) => (
              <Text key={`${i}-${line}`} style={styles.line} numberOfLines={1}>
                {line}
              </Text>
            ))
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: "absolute",
    right: 4,
    width: 220,
    zIndex: 9999,
    elevation: 9999,
    alignItems: "flex-end",
  },
  row: {
    flexDirection: "row",
    gap: 4,
  },
  btn: {
    backgroundColor: "rgba(0,0,0,0.78)",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  btnSmall: {
    backgroundColor: "rgba(0,0,0,0.78)",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  btnText: {
    color: "#0f0",
    fontSize: 10,
    fontWeight: "700",
  },
  box: {
    backgroundColor: "rgba(0,0,0,0.78)",
    padding: 5,
    marginTop: 2,
    borderRadius: 4,
    alignSelf: "stretch",
  },
  line: {
    color: "#0f0",
    fontSize: 9,
    lineHeight: 11,
  },
});
