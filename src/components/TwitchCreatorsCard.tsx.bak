import React from "react";
import { View, Text, TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Link } from "expo-router";

type TwitchCreator = {
  id: string;
  displayName: string;
  initials: string;
  category: string;
  title: string;
  isLive: boolean;
  viewers?: number;
  nextStreamLabel?: string;
};

const MOCK_TWITCH_CREATORS: TwitchCreator[] = [
  {
    id: "1",
    displayName: "CardCastleTV",
    initials: "CC",
    category: "Pokémon TCG",
    title: "Vintage Japanese box break",
    isLive: true,
    viewers: 842,
  },
  {
    id: "2",
    displayName: "MiniForge",
    initials: "MF",
    category: "Warhammer · painting",
    title: "Lumineth army build log",
    isLive: true,
    viewers: 312,
  },
  {
    id: "3",
    displayName: "BrickLayers",
    initials: "BL",
    category: "LEGO",
    title: "Modular city night stream",
    isLive: false,
    nextStreamLabel: "Tonight · 21:00",
  },
];

export const TwitchCreatorsCard: React.FC = () => {
  const live = MOCK_TWITCH_CREATORS.filter((c) => c.isLive);
  const upcoming = MOCK_TWITCH_CREATORS.filter((c) => !c.isLive);
  const rows = [...live, ...upcoming].slice(0, 3);

  return (
    <View
      style={{
        marginTop: 16,
        padding: 16,
        borderRadius: 16,
        backgroundColor: "#FFFFFF",
        shadowColor: "#000000",
        shadowOpacity: 0.04,
        shadowOffset: { width: 0, height: 3 },
        shadowRadius: 10,
        elevation: 2,
      }}
    >
      {/* Header */}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <View>
          <Text
            style={{
              fontSize: 16,
              fontWeight: "600",
              color: "#1A202C",
            }}
          >
            Twitch creators
          </Text>
          <Text
            style={{
              marginTop: 2,
              fontSize: 13,
              color: "#4A5568",
            }}
          >
            Live breaks, paint logs, and collection flex streams.
          </Text>
        </View>

        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            paddingVertical: 4,
            paddingHorizontal: 10,
            borderRadius: 999,
            backgroundColor: "#E6FFFA",
          }}
        >
          <View
            style={{
              width: 8,
              height: 8,
              borderRadius: 999,
              backgroundColor: "#38A169",
              marginRight: 6,
            }}
          />
          <Text
            style={{
              fontSize: 12,
              fontWeight: "500",
              color: "#22543D",
            }}
          >
            {live.length} live now
          </Text>
        </View>
      </View>

      {/* Creator rows */}
      <View style={{ marginTop: 12 }}>
        {rows.map((creator) => (
          <View
            key={creator.id}
            style={{
              flexDirection: "row",
              alignItems: "center",
              marginBottom: 10,
            }}
          >
            {/* Avatar */}
            <View
              style={{
                width: 40,
                height: 40,
                borderRadius: 12,
                backgroundColor: "#EDF2F7",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Text
                style={{
                  fontSize: 16,
                  fontWeight: "700",
                  color: "#2D3748",
                }}
              >
                {creator.initials}
              </Text>
            </View>

            {/* Text */}
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text
                numberOfLines={1}
                style={{
                  fontSize: 14,
                  fontWeight: "600",
                  color: "#1A202C",
                }}
              >
                {creator.displayName}
              </Text>
              <Text
                numberOfLines={1}
                style={{
                  fontSize: 12,
                  color: "#718096",
                  marginTop: 2,
                }}
              >
                {creator.category} · {creator.title}
              </Text>
            </View>

            {/* Status */}
            <View style={{ alignItems: "flex-end" }}>
              {creator.isLive ? (
                <>
                  <Text
                    style={{
                      fontSize: 12,
                      fontWeight: "500",
                      color: "#1A202C",
                    }}
                  >
                    {creator.viewers?.toLocaleString() ?? 0} watching
                  </Text>
                  <View
                    style={{
                      marginTop: 4,
                      paddingHorizontal: 8,
                      paddingVertical: 3,
                      borderRadius: 999,
                      backgroundColor: "#E53E3E",
                    }}
                  >
                    <Text
                      style={{
                        fontSize: 11,
                        fontWeight: "600",
                        color: "#FFFFFF",
                      }}
                    >
                      LIVE
                    </Text>
                  </View>
                </>
              ) : (
                <Text
                  style={{
                    fontSize: 12,
                    color: "#4A5568",
                  }}
                >
                  Next: {creator.nextStreamLabel ?? "TBD"}
                </Text>
              )}
            </View>
          </View>
        ))}
      </View>

      {/* CTA */}
      <Link href="/twitch-leaderboard" asChild>
        <TouchableOpacity
          style={{
            marginTop: 12,
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "center",
            paddingVertical: 10,
            borderRadius: 999,
            backgroundColor: "#02B5C4",
          }}
          activeOpacity={0.9}
        >
          <Ionicons name="logo-twitch" size={18} color="#FFFFFF" />
          <Text
            style={{
              marginLeft: 8,
              marginRight: 4,
              fontSize: 14,
              fontWeight: "600",
              color: "#FFFFFF",
            }}
          >
            Open Twitch hub
          </Text>
          <Ionicons name="chevron-forward" size={16} color="#FFFFFF" />
        </TouchableOpacity>
      </Link>

      {/* Helper text */}
      <Text
        style={{
          marginTop: 6,
          fontSize: 11,
          color: "#A0AEC0",
        }}
      >
        Mock data for now — later this will pull live status and viewer counts from Twitch.
      </Text>
    </View>
  );
};
