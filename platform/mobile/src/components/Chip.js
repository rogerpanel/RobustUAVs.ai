import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { theme } from '../theme';

/** A provenance / status chip. Deliberately always rendered, never hidden:
 *  a number without its evidence class is the thing this project refuses to
 *  ship. */
export default function Chip({ label, color = theme.muted }) {
  return (
    <View style={[styles.chip, { borderColor: color }]}>
      <Text style={[styles.text, { color }]} numberOfLines={1}>{label}</Text>
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
