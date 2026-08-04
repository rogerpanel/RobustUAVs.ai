import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../theme';

/** A provenance / status chip. Always rendered, never hidden: a number without
 *  its evidence class is the thing this project refuses to ship. */
export default function Chip({ label, color }) {
  const { t } = useTheme();
  const c = color || t.muted;
  return (
    <View style={[styles.chip, { borderColor: c }]}>
      <Text style={[styles.text, { color: c }]} numberOfLines={1}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    borderWidth: 1, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2,
    marginRight: 6, marginTop: 4, alignSelf: 'flex-start',
  },
  text: { fontSize: 11, fontWeight: '600' },
});
