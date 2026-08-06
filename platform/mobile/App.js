import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import Shell from './src/layout/Shell';
import EthicsGate, { hasAccepted } from './src/screens/EthicsGate';
import { ThemeProvider, useTheme } from './src/theme';

/**
 * Navigation lives in `src/layout/Shell.js`, which is a responsive
 * three-column layout rather than a tab navigator: left rail, centre, right
 * rail on a desktop, collapsing to centre-plus-bottom-tabs on a phone with
 * both rails reachable as overlays.
 *
 * react-navigation is no longer wired in here. The app has one level of
 * navigation and no history to manage, and the drawer navigator would have
 * pulled in `gesture-handler` and `reanimated` -- the two packages most often
 * responsible for an Expo web export failing. Screens still receive a
 * `navigation` prop with `navigate`, so swapping a real navigator back in
 * would touch this file and Shell.js only.
 */
function Themed() {
  const { mode } = useTheme();
  // The ethical-use notice gates the whole application, not a single page.
  // Checked once on mount so an accepted visitor never sees it again, and
  // re-shown for everyone when ACCEPT_VERSION changes.
  const [accepted, setAccepted] = React.useState(() => hasAccepted());
  return (
    <>
      <StatusBar style={mode === 'dark' ? 'light' : 'dark'} />
      {accepted ? <Shell /> : <EthicsGate onAccept={() => setAccepted(true)} />}
    </>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <Themed />
      </ThemeProvider>
    </SafeAreaProvider>
  );
}
