import React from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { useTheme } from '../theme';
import { RAIL_W } from './useLayout';

/**
 * The scroll chrome both rails share.
 *
 * Nested ScrollViews, vertical outer and horizontal inner. On the pinned rail
 * the column has a fixed width, so a label longer than the rail wraps to a
 * second line and is read in full; truncating with an ellipsis would hide
 * exactly the end that tells two entries apart (e.g. "Paper II - AirworthinessSoK").
 * The horizontal scroller stays as a fallback for an unbreakable token.
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
  // A fixed width on the pinned rail makes a long label wrap to a second line,
  // so it is read in full without scrolling sideways.
  column: compact ? { minWidth: 260, flexShrink: 0 } : { width: RAIL_W - 1, flexShrink: 0 },
});
