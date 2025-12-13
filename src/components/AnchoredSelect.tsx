import React from 'react';
import { View, Text, Pressable, Modal, ScrollView } from 'react-native';
import { theme } from '@/theme';

/**
 * Compact, friendly dropdown:
 * - Trigger auto-sizes to its value (no full-width unless width prop is set)
 * - Rounded corners on trigger & menu
 * - Menu anchors directly under the trigger and matches / exceeds trigger width
 */
export default function AnchoredSelect({
  label,
  value,
  options,
  onChange,
  width,
}: {
  label?: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
  width?: number | string; // set to force specific width; otherwise auto-size to value
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<View>(null);
  const [pos, setPos] = React.useState<{ x: number; y: number; w: number; h: number }>({ x: 0, y: 0, w: 220, h: 40 });
  const [textW, setTextW] = React.useState(0);

  const openMenu = () => {
    setOpen(true);
    // Measure trigger after it opens to get screen coords for anchored menu
    setTimeout(() => {
      ref.current?.measureInWindow?.((x: number, y: number, w: number, h: number) => setPos({ x, y, w, h }));
    }, 0);
  };

  // Rough estimate so menu can accommodate longest option if it's wider than trigger
  const estOptWidth = React.useMemo(() => {
    const charW = 8; // heuristic
    const longest = Math.max(value.length, ...options.map(o => o.length), 8);
    return 16 + longest * charW;
  }, [value, options]);

  // Trigger width (auto unless width prop provided)
  const trigW = typeof width === 'number' || typeof width === 'string'
    ? (width as any)
    : Math.max(60, textW + 24); // value text width + horizontal padding

  const menuW = Math.max(typeof trigW === 'number' ? trigW : pos.w, estOptWidth);

  return (
    <View style={{ width: width ?? undefined, alignSelf: 'flex-start' }}>
      {label ? (
        <Text style={{ color: theme.colors.navy, fontWeight: '800', marginBottom: 6 }}>{label}</Text>
      ) : null}
      <Pressable
        ref={ref}
        onPress={openMenu}
        style={{
          borderWidth: 1,
          borderColor: theme.colors.border,
          backgroundColor: '#fff',
          paddingVertical: 8,
          paddingHorizontal: 12,
          borderRadius: 12,
          alignSelf: 'flex-start',
          ...(typeof trigW === 'number' ? { width: trigW } : {}),
        }}
      >
        <Text
          onLayout={e => setTextW(e.nativeEvent.layout.width)}
          style={{ color: theme.colors.navy }}
          numberOfLines={1}
        >
          {value}
        </Text>
      </Pressable>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable onPress={() => setOpen(false)} style={{ flex: 1 }}>
          <View
            style={{
              position: 'absolute',
              left: pos.x,
              top: pos.y + pos.h,
              width: menuW,
              maxHeight: '70%',
              backgroundColor: '#fff',
              borderWidth: 1,
              borderColor: theme.colors.border,
              borderRadius: 12,
              overflow: 'hidden',
            }}
          >
            <ScrollView>
              {options.map(opt => (
                <Pressable
                  key={opt}
                  onPress={() => { onChange(opt); setOpen(false); }}
                  style={{ paddingVertical: 8, paddingHorizontal: 10 }}
                >
                  <Text style={{ color: theme.colors.navy }}>{opt}</Text>
                </Pressable>
              ))}
            </ScrollView>
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}
