import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme, fonts } from '../theme';

export default function Card({ title, subtitle, source, children }) {
  const { t } = useTheme();
  const s = styles(t);
  return (
    <View style={s.card}>
      {title ? <Text style={s.title}>{title}</Text> : null}
      {subtitle ? <Text style={s.subtitle}>{subtitle}</Text> : null}
      {children}
      {source ? <Text style={s.source}>source: {source}</Text> : null}
    </View>
  );
}

const styles = (t) => StyleSheet.create({
  card: {
    backgroundColor: t.panel, borderColor: t.border, borderWidth: 1,
    borderRadius: 10, padding: 14, marginBottom: 12,
  },
  title: { color: t.text, fontSize: 15, fontWeight: '700', marginBottom: 2, fontFamily: fonts.display },
  subtitle: { color: t.muted, fontSize: 12, marginBottom: 10, lineHeight: 17 },
  source: { color: t.muted, fontSize: 10, marginTop: 10, fontStyle: 'italic', fontFamily: fonts.mono },
});
