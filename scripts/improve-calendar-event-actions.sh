#!/usr/bin/env bash
set -euo pipefail

FILE="app/calendar-event-detail-demo.tsx"

if [ ! -f "$FILE" ]; then
  echo "calendar-event-detail-demo.tsx not found at $FILE"
  exit 1
fi

cp "$FILE" "$FILE.bak.actions-$(date +%s)" || true

python << 'PY'
from pathlib import Path
import textwrap

path = Path("app/calendar-event-detail-demo.tsx")
text = path.read_text()

# Ensure router is imported (we already had it, but be safe)
if "router" not in text:
    if "from 'expo-router'" in text and "useLocalSearchParams" in text:
        text = text.replace(
            "from 'expo-router';",
            "from 'expo-router';",
        )
    # We won't overdo this; existing file already imports router in your last version.

# Replace the Actions section with a richer version
old_actions_block = """        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
            gap: spacing.sm,
          }}
        >
          <Text
            style={{
              fontSize: 16,
              fontWeight: '700',
              color: colors.text,
              marginBottom: spacing.sm,
            }}
          >
            Actions
          </Text>

          {isMyEvent ? (
            <Text
              style={{
                fontSize: 13,
                color: colors.mutedText,
                marginBottom: spacing.sm,
              }}
            >
              Later you&apos;ll be able to enable reminders for this event:
              e.g. 3 days before, or same-day morning.
            </Text>
          ) : (
            <Text
              style={{
                fontSize: 13,
                color: colors.mutedText,
                marginBottom: spacing.sm,
              }}
            >
              This is a major drop or release. In the real app you could
              jump to signup, preorders, or add a personal reminder.
            </Text>
          )}

          {isMyEvent ? (
            <TouchableOpacity
              activeOpacity={0.9}
              onPress={handleAddToMyEvents}
              style={{
                borderRadius: 999,
                paddingHorizontal: spacing.lg,
                paddingVertical: 10,
                backgroundColor: colors.primary,
                alignSelf: 'flex-start',
              }}
            >
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: '600',
                  color: colors.onPrimary,
                }}
              >
                Back to my events
              </Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              activeOpacity={0.9}
              onPress={handleOpenSignup}
              style={{
                borderRadius: 999,
                paddingHorizontal: spacing.lg,
                paddingVertical: 10,
                backgroundColor: colors.primary,
                alignSelf: 'flex-start',
              }}
            >
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: '600',
                  color: colors.onPrimary,
                }}
              >
                Back to calendar
              </Text>
            </TouchableOpacity>
          )}
        </View>"""

new_actions_block = """        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
            gap: spacing.sm,
          }}
        >
          <Text
            style={{
              fontSize: 16,
              fontWeight: '700',
              color: colors.text,
              marginBottom: spacing.sm,
            }}
          >
            Actions
          </Text>

          {isMyEvent ? (
            <Text
              style={{
                fontSize: 13,
                color: colors.mutedText,
                marginBottom: spacing.sm,
              }}
            >
              Later you&apos;ll be able to enable reminders for this event:
              e.g. 3 days before, or same-day morning, and attach items
              from your collection or watchlist.
            </Text>
          ) : (
            <Text
              style={{
                fontSize: 13,
                color: colors.mutedText,
                marginBottom: spacing.sm,
              }}
            >
              This is a major drop or release. In the real app you could
              jump to signup/preorders or add key cards and figures from
              this drop straight into your watchlist.
            </Text>
          )}

          {isMyEvent ? (
            <TouchableOpacity
              activeOpacity={0.9}
              onPress={handleAddToMyEvents}
              style={{
                borderRadius: 999,
                paddingHorizontal: spacing.lg,
                paddingVertical: 10,
                backgroundColor: colors.primary,
                alignSelf: 'flex-start',
                marginBottom: 8,
              }}
            >
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: '600',
                  color: colors.onPrimary,
                }}
              >
                Back to my events
              </Text>
            </TouchableOpacity>
          ) : (
            <>
              <TouchableOpacity
                activeOpacity={0.9}
                onPress={handleOpenSignup}
                style={{
                  borderRadius: 999,
                  paddingHorizontal: spacing.lg,
                  paddingVertical: 10,
                  backgroundColor: colors.primary,
                  alignSelf: 'flex-start',
                  marginBottom: 8,
                }}
              >
                <Text
                  style={{
                    fontSize: 14,
                    fontWeight: '600',
                    color: colors.onPrimary,
                  }}
                >
                  Back to calendar
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                activeOpacity={0.9}
                onPress={() => {
                  try {
                    router.push('/watchlist-v1-demo');
                  } catch {
                    // no-op
                  }
                }}
                style={{
                  borderRadius: 999,
                  paddingHorizontal: spacing.lg,
                  paddingVertical: 10,
                  backgroundColor: colors.card,
                  borderWidth: 1,
                  borderColor: colors.border,
                  alignSelf: 'flex-start',
                }}
              >
                <Text
                  style={{
                    fontSize: 14,
                    fontWeight: '600',
                    color: colors.text,
                  }}
                >
                  View related watchlist (demo)
                </Text>
              </TouchableOpacity>
            </>
          )}
        </View>"""

if old_actions_block in text:
    text = text.replace(old_actions_block, new_actions_block)
    print("Replaced Actions block in calendar-event-detail-demo.tsx.")
else:
    print("Could not find original Actions block; no replacement applied.")

path.write_text(text)
PY

echo "Improved calendar-event-detail-demo.tsx actions (backup created)."
