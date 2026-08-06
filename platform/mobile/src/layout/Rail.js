import React from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { useTheme } from '../theme';
import { RAIL_W } from './useLayout';

/**
 * The scroll chrome both rails share.
 *
 * Nested ScrollViews, vertical outer and horizontal inner, so a rail scrolls
 * up/down through its sections *and* left/right when a label is longer than
 * 196 px. The alternative -- truncating with an ellipsis -- hides exactly the
 * end of the string that distinguishes "GNSS Spoof Monitor" from "GNSS Spoof
 * Monitor (live)", so the content is reachable rather than clipped.
 *
 * The horizontal scroller must NOT be `flex: 1`: a horizontal ScrollView sizes
 * its content along x, and a flexed child collapses the cross-axis to zero on
 * web, which renders an empty rail. `alignSelf: flex-start` with an explicit
 * minWidth is what keeps rows their natural height.
 */
export default function Rail({ side = 'left', compact = false, header, footer, children }) {
  const { t } = useTheme();
  const s = styles(t, side, compact);

  return (
    <View style={s.rail}>
      {header}
      <ScrollView
        style={s.vertical}
        contentContainerStyle={s.verticalBody}
        showsVerticalScrollIndicator={false}
      >
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={s.horizontalBody}
        >
          <View style={s.column}>{children}</View>
        </ScrollView>
      </ScrollView>
      {footer}
    </View>
  );
}

const styles = (t, side, compact) => StyleSheet.create({
  rail: {
    width: compact ? '100%' : RAIL_W,
    flex: 1,
    backgroundColor: t.panel,
    borderRightWidth: side === 'left' && !compact ? 1 : 0,
    borderLeftWidth: side === 'right' && !compact ? 1 : 0,
    borderColor: t.border,
  },
  vertical: { flex: 1 },
  verticalBody: { paddingVertical: 8 },
  horizontalBody: { minWidth: '100%' },
  column: { minWidth: compact ? 260 : RAIL_W - 1, flexShrink: 0 },
});
