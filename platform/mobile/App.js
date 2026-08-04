import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer, DarkTheme, DefaultTheme } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text } from 'react-native';

import CoverScreen from './src/screens/CoverScreen';
import OverviewScreen from './src/screens/OverviewScreen';
import CompositionScreen from './src/screens/CompositionScreen';
import RunsScreen from './src/screens/RunsScreen';
import ModelsScreen from './src/screens/ModelsScreen';
import CopilotScreen from './src/screens/CopilotScreen';
import { ThemeProvider, useTheme } from './src/theme';

const Tab = createBottomTabNavigator();
const icon = (glyph) => ({ color }) => <Text style={{ color, fontSize: 17 }}>{glyph}</Text>;

function Shell() {
  const { t, mode } = useTheme();
  const base = mode === 'dark' ? DarkTheme : DefaultTheme;
  const navTheme = {
    ...base,
    colors: { ...base.colors, background: t.bg, card: t.panel, border: t.border,
              text: t.text, primary: t.accent },
  };
  return (
    <NavigationContainer theme={navTheme}>
      <StatusBar style={mode === 'dark' ? 'light' : 'dark'} />
      <Tab.Navigator
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: t.accent,
          tabBarInactiveTintColor: t.muted,
          tabBarStyle: { backgroundColor: t.panel, borderTopColor: t.border },
          tabBarLabelStyle: { fontSize: 10 },
        }}>
        <Tab.Screen name="Home" component={CoverScreen} options={{ tabBarIcon: icon('◆') }} />
        <Tab.Screen name="Overview" component={OverviewScreen} options={{ tabBarIcon: icon('◈') }} />
        <Tab.Screen name="Composition" component={CompositionScreen} options={{ tabBarIcon: icon('⟶') }} />
        <Tab.Screen name="Runs" component={RunsScreen} options={{ tabBarIcon: icon('▶') }} />
        <Tab.Screen name="Registry" component={ModelsScreen} options={{ tabBarIcon: icon('▤') }} />
        <Tab.Screen name="Copilot" component={CopilotScreen} options={{ tabBarIcon: icon('✦') }} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <Shell />
    </ThemeProvider>
  );
}
