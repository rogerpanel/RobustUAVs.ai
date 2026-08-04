import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { theme } from '../theme';

export default function Card({ title, subtitle, source, children }) {
  return (
    <View style={styles.card}>
      {title ? <Text style={styles.title}>{title}</Text> : null}
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      {children}
      {source ? <Text style={styles.source}>source: {source}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.card, borderColor: theme.border, borderWidth: 1,
    borderRadius: 10, padding: 14, marginBottom: 12,
  },
  title: { color: theme.text, fontSize: 16, fontWeight: '700', marginBottom: 2 },
  subtitle: { color: theme.muted, fontSize: 13, marginBottom: 10, lineHeight: 18 },
  source: { color: theme.muted, fontSize: 10, marginTop: 10, fontStyle: 'italic' },
});
