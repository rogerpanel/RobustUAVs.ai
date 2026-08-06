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
    // flexGrow 0 is the load-bearing part. `flex: 1` here meant "grow to fill",
    // which inside the row container overrode the width entirely and produced
    // three equal columns -- the rail rendered at ~450 px on a 1360 px screen
    // no matter what RAIL_W said. Width alone is not enough in a flex row:
    // growth has to be refused explicitly.
    width: compact ? '100%' : RAIL_W,
    flexGrow: 0,
    flexShrink: 0,
    flexBasis: compact ? 'auto' : RAIL_W,
    alignSelf: 'stretch',
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
